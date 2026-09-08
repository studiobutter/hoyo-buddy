# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from .base import BaseModel

if TYPE_CHECKING:
    from .user import User


class DMChannel(BaseModel):
    id = fields.BigIntField(pk=True, generated=False)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="dm_channels"
    )
