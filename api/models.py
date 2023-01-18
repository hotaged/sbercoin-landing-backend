from tortoise import models, fields
from tortoise.contrib.pydantic import (
    pydantic_model_creator, pydantic_queryset_creator
)


class UserBid(models.Model):
    id = fields.IntField(pk=True)

    email = fields.CharField(
        null=False,
        max_length=255
    )
    sbercoin_address = fields.CharField(
        null=False,
        max_length=34
    )

    created_at = fields.DatetimeField(auto_now_add=True)

    victory = fields.BooleanField(
        null=False,
        default=False
    )

    modified_at = fields.DatetimeField(auto_now=True)

    is_valid = fields.BooleanField(null=False, default=True)

    async def win(self) -> None:
        self.victory = True
        await self.save()


UserBidPydantic = pydantic_model_creator(UserBid, name="UserBid")
UserBidInPydantic = pydantic_model_creator(UserBid, exclude_readonly=True, name="UserBidIn")
UserBidQueryset = pydantic_queryset_creator(UserBid, name="UserBidQueryset")
