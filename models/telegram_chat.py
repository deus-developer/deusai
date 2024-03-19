import datetime
from typing import Optional, cast

import peewee

from .base import BaseModel


class TelegramChat(BaseModel):
    chat_id = peewee.BigIntegerField(
        null=False,
        index=True,
        unique=True,
        primary_key=True
    )
    chat_type = peewee.CharField(
        max_length=10,
        choices=(
            ('CHANNEL', 'channel'),
            ('GROUP', 'group'),
            ('SUPERGROUP', 'supergroup')
        )
    )

    title = peewee.CharField(max_length=255, null=True)
    shortname = peewee.CharField(max_length=32, null=True, index=True)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    is_active = peewee.BooleanField(default=False)

    @classmethod
    def get_by_name(cls, chat_name: str) -> Optional["TelegramChat"]:
        where_stmt = (cls.title == chat_name) | (cls.shortname == chat_name)
        select_stmt = cls.select().where(where_stmt)

        return select_stmt.first()

    def __str__(self) -> str:
        return cast(str, self.title)
        
    class Meta:
        only_save_dirty = True
