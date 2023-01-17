from tortoise import models, fields


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

    def is_valid(self) -> bool:
        return True
