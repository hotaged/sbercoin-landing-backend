import fastapi
import rich

from api import models
from api.config import settings
from api.timing import seconds_remains
from api.transactions import TransactionManager

from fastapi import Request, Depends
from fastapi.responses import JSONResponse

from tortoise import Tortoise, connections
from tortoise.exceptions import DoesNotExist, IntegrityError
from fastapi.middleware.cors import CORSMiddleware


SBERCOIN_ADDRESS = settings.sbercoin.host
SBERCOIN_USER = settings.sbercoin.user
SBERCOIN_PASSWORD = settings.sbercoin.password
SBERCOIN_PORT = settings.sbercoin.port
SBERCOIN_WALLET = settings.sbercoin.wallet
SBERCOIN_PRIVATE_KEY = settings.sbercoin.wallet_pk

PRIZE_REGISTER = settings.prize.register
PRIZE_REFERRAL = settings.prize.referral
PRIZE_MASTER = settings.prize.master

app = fastapi.FastAPI()
sbercoin = TransactionManager(
    f"http://{SBERCOIN_ADDRESS}:{SBERCOIN_PORT}",
    (SBERCOIN_USER, SBERCOIN_PASSWORD),
    SBERCOIN_WALLET, SBERCOIN_PRIVATE_KEY
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def create_bid(request: Request, bid: models.UserBidInPydantic):
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

    payable = list(map(lambda key: {key: payable[key]}, payable))

    result = await sbercoin.send_coins(payable)

    rich.print(result)

    user_object = await models.UserBid.create(
        **bid.dict(exclude_unset=True, exclude={'captcha'}), ip_address=client[0]
    )
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
