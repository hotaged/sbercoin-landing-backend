import asyncio
import logging
import fastapi

from pydantic import EmailStr

from api import models
from api.config import settings
from api.timing import seconds_remains
from api.transactions import TransactionManager
from api.templates import (
    GIVE_WINNER_TEMPLATE,
    GIVE_COMPLETE_TEMPLATE,
    BID_ACCEPTED_TEMPLATE
)

from fastapi import Request, BackgroundTasks
from fastapi.responses import JSONResponse

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from tortoise import Tortoise, connections
from tortoise.exceptions import DoesNotExist, IntegrityError
from fastapi.middleware.cors import CORSMiddleware

DEBUG = settings.default.debug

SBERCOIN_ADDRESS = settings.sbercoin.host
SBERCOIN_USER = settings.sbercoin.user
SBERCOIN_PASSWORD = settings.sbercoin.password
SBERCOIN_PORT = settings.sbercoin.port
SBERCOIN_WALLET = settings.sbercoin.wallet
SBERCOIN_PRIVATE_KEY = settings.sbercoin.wallet_pk

PRIZE_REGISTER = settings.prize.register
PRIZE_REFERRAL = settings.prize.referral
PRIZE_MASTER = settings.prize.master
PRIZE_REF_MASTER = settings.prize.ref_master

app = fastapi.FastAPI()

sbercoin = TransactionManager(
    f"http://{SBERCOIN_ADDRESS}:{SBERCOIN_PORT}",
    (SBERCOIN_USER, SBERCOIN_PASSWORD),
    SBERCOIN_WALLET, SBERCOIN_PRIVATE_KEY
)


mail = FastMail(ConnectionConfig(
    MAIL_USERNAME=settings.email.username,
    MAIL_PASSWORD=settings.email.password,
    MAIL_FROM=EmailStr(settings.email.from_),
    MAIL_PORT=settings.email.port,
    MAIL_SERVER=settings.email.server,
    MAIL_FROM_NAME=settings.email.from_,
    MAIL_SSL_TLS=settings.email.tls,
    MAIL_STARTTLS=settings.email.starttls,
    USE_CREDENTIALS=settings.email.use_credentials,
    VALIDATE_CERTS=settings.email.validate_certs
))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)


async def give_sbercoin():
    logging.info(f"Starting give.")

    def randint_from_sbercoin(hashed: str, min_value: int, max_value: int) -> int:
        result = int(hashed[:13], base=16) / (16 ** 13)
        return round(result * (max_value - min_value) + min_value)

    logging.info("Getting sbercoin last block hash.")
    block_hash = await sbercoin.get_last_block_hash()
    logging.info(f"Got block hash: {block_hash}")

    users_count = await models.UserBid.all().count()
    users_queryset = await models.UserBid.all()

    if users_count == 0:
        logging.info("No users to give to.")
        return

    logging.info(f"Calculating a winner from {users_count} of users.")
    winner_id = randint_from_sbercoin(block_hash, 1, users_count)
    logging.info(f"A winner is: {winner_id}")

    users_history_queryset = []

    for i, model in enumerate(users_queryset):
        is_winner = ((i + 1) == winner_id)
        users_history_queryset.append(
            models.UserBidHistory(
                email=model.email,
                sbercoin_address=model.sbercoin_address,
                created_at=model.created_at,
                modified_at=model.modified_at,

                is_winner=is_winner,
                calculated_hash=block_hash,
                bids_count=users_count,
                number=(i + 1)
            )
        )

        if is_winner:
            message = MessageSchema(
                subject="Sbercoin: Give completed.",
                subtype=MessageType.html,
                recipients=[model.email],
                body=GIVE_WINNER_TEMPLATE.format(
                    address=model.sbercoin_address
                ),
            )
        else:
            message = MessageSchema(
                subject="Sbercoin: Give completed.",
                subtype=MessageType.html,
                recipients=[model.email],
                body=GIVE_COMPLETE_TEMPLATE
            )

        asyncio.create_task(mail.send_message(message))

    logging.info("Calculating payments.")

    wallet_address = users_queryset[winner_id - 1].sbercoin_address
    referral_address = users_queryset[winner_id - 1].ref_address

    payable = [{wallet_address: PRIZE_MASTER}]

    if referral_address is not None:
        payable += [{referral_address: PRIZE_MASTER * PRIZE_REF_MASTER}]

    logging.info(f"Payments: {payable}")

    await models.UserBid.all().delete()
    await models.UserBidHistory.bulk_create(users_history_queryset)

    logging.info("Sending coins...")

    await send(payable)

    logging.info("Complete")


async def start():
    logging.info("Starting giver.")

    while True:
        logging.info(f"Giver wil sleep for {seconds_remains()}")

        await asyncio.sleep(seconds_remains())
        await give_sbercoin()


async def send(payable: list, fee: float = 0.01):
    while True:
        await asyncio.sleep(3)

        logging.info(f"Trying to send coins: {payable}")
        result = await sbercoin.send_coins(payable, fee)

        if result['error'] is None:
            logging.info("Complete.")
            break

        logging.info(f"Blockchain responded with: {result['error']}.")
        logging.info("Retrying after 3 seconds.")


if DEBUG:
    @app.post("/debug-start-give")
    async def start_give(background: BackgroundTasks) -> models.JsonMessage:
        background.add_task(give_sbercoin)
        return models.JsonMessage(message="OK")


@app.get("/time-remain", response_model=models.TimeRemain)
async def time_remain() -> models.TimeRemain:
    total_seconds = seconds_remain = seconds_remains()

    total_seconds %= 24 * 3600
    hours = total_seconds // 3600
    total_seconds %= 3600
    minutes = total_seconds // 60
    total_seconds %= 60
    seconds = total_seconds

    instance = models.TimeRemain(
        hours=hours, minutes=minutes, seconds=seconds, total_seconds=seconds_remain
    )

    return instance


@app.get("/bids", response_model=list[models.UserBidPydantic])
async def list_bids() -> list[models.UserBidPydantic]:
    return await models.UserBidPydantic.from_queryset(models.UserBid.all())


@app.post("/bids", response_model=models.UserBidPydantic, responses={
    404: {"model": models.JsonMessage},
    403: {"model": models.JsonMessage}
})
async def create_bid(request: Request, bid: models.UserBidInPydantic, bg: BackgroundTasks):
    client = request.scope['client']

    if (await models.UserBid.get_or_none(ip_address=client[0])) is not None:
        return JSONResponse(
            models.JsonMessage(
                message="You've already sent a bid."
            ).dict(),
            403
        )

    # TODO! Add captcha validation

    payable = {}

    # Checks if a referral address exists and is correct
    # If everything is fine, we append a reward for ref wallets
    if bid.ref_address is not None:
        if bid.sbercoin_address == bid.ref_address:
            return JSONResponse(models.JsonMessage(
                message="You can't use yourself as a referral."
            ).dict(), 403)

        if not await sbercoin.address_exists(bid.ref_address):
            return JSONResponse(models.JsonMessage(
                message="Referral address doesn't exists."
            ).dict(), 404)

        payable = {
            bid.ref_address: PRIZE_REFERRAL,
            bid.sbercoin_address: PRIZE_REGISTER
        }

    if not await sbercoin.address_exists(bid.sbercoin_address):
        return JSONResponse(models.JsonMessage(
            message="Sbercoin address doesn't exists."
        ).dict(), 404)

    if bid.sbercoin_address in payable:
        payable[bid.sbercoin_address] += PRIZE_REFERRAL
    else:
        payable[bid.sbercoin_address] = PRIZE_REGISTER

    message = MessageSchema(
        subject="Sbercoin: Bid accepted.",
        subtype=MessageType.html,
        recipients=[bid.email],
        body=BID_ACCEPTED_TEMPLATE.format(
            coins_amount=payable[bid.sbercoin_address],
            address=bid.sbercoin_address
        ),
    )

    payable = list(map(lambda key: {key: payable[key]}, payable))

    bg.add_task(send, payable)

    user_object = await models.UserBid.create(
        **bid.dict(exclude_unset=True, exclude={'captcha'}), ip_address=client[0]
    )

    bg.add_task(mail.send_message, message)

    return await models.UserBidPydantic.from_tortoise_orm(user_object)


@app.get("/winners", response_model=list[models.UserBidHistoryPydantic])
async def winners() -> list[models.UserBidPydantic]:
    return await models.UserBidHistoryPydantic.from_queryset(
        models.UserBidHistory.filter(is_winner=True).order_by('-created_at')
    )


@app.on_event("startup")
async def init_orm() -> None:
    await Tortoise.init(
        db_url=settings.storages.postgres,
        modules={"models": ["api.models"]},
        timezone=settings.winpay.timezone
    )
    await Tortoise.generate_schemas()

    asyncio.create_task(start())


@app.on_event("shutdown")
async def close_orm() -> None:
    await connections.close_all()


@app.exception_handler(DoesNotExist)
async def does_not_exist_exception_handler(_: Request, exc: DoesNotExist):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
async def integrity_error_exception_handler(_: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": [], "msg": str(exc), "type": "IntegrityError"}]},
    )
