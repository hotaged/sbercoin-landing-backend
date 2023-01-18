from pydantic import (
    BaseModel, EmailStr, validator, constr
)
from tortoise import models, fields
from tortoise.contrib.pydantic import (
    pydantic_model_creator
)


class UserBid(models.Model):
    id = fields.IntField(pk=True)

    email = fields.CharField(
        null=False,
        unique=True,
        max_length=255
    )
    sbercoin_address = fields.CharField(
        null=False,
        unique=True,
        max_length=34
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    modified_at = fields.DatetimeField(auto_now=True)

    ip_address = fields.CharField(
        null=False,
        unique=True,
        max_length=16
    )


class UserBidHistory(models.Model):
    id = fields.IntField(pk=True)

    email = fields.CharField(
        null=False,
        max_length=255
    )
    sbercoin_address = fields.CharField(
        null=False,
        max_length=34
    )

    created_at = fields.DatetimeField()
    modified_at = fields.DatetimeField()

    victory = fields.BooleanField(default=False, null=False)


class UserBidInPydantic(BaseModel):
    email: EmailStr
    sbercoin_address: constr(max_length=34, min_length=34)

    @classmethod
    @validator('sbercoin_address')
    def sbercoin_address_validation(cls, v: str):
        if not v.startswith('S'):
            raise ValueError("Invalid sbercoin address")
        return v


UserBidPydantic = pydantic_model_creator(UserBid, name="UserBid")
UserBidHistoryPydantic = pydantic_model_creator(UserBidHistory, name="UserBidHistory")