import fastapi

from api import models
from api.config import settings
from api.timing import next_winpay

from fastapi import Request
from fastapi.responses import JSONResponse

from tortoise import Tortoise, connections
from tortoise.exceptions import DoesNotExist, IntegrityError


app = fastapi.FastAPI()


@app.get('/bids', response_model=list[models.UserBidPydantic])
async def list_bids(valid: bool | None = None):
    if valid is None:
        return await models.UserBidPydantic.from_queryset(models.UserBid.all())

    if valid:
        return await models.UserBidPydantic.from_queryset(models.UserBid.filter(created_at__gte=next_winpay()))
    else:
        return await models.UserBidPydantic.from_queryset(models.UserBid.filter(created_at__le=next_winpay()))


@app.post("/bids", response_model=models.UserBidPydantic)
async def create_bid(bid: models.UserBidInPydantic):
    user_object = await models.UserBid.create(**bid.dict(exclude_unset=True))
    """
    @TODO:
        - add validation for email field.
        - add validation for sbercoin address.
        
        - add IP request limiter.
        - add Email request limiter.
        - add Address request limiter.
    """
    return await models.UserBidPydantic.from_tortoise_orm(user_object)


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
