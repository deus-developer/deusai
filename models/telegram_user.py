import datetime
import html
from typing import Optional, cast

import peewee

from .base import BaseModel


class TelegramUser(BaseModel):
    user_id = peewee.BigIntegerField(null=False, index=True, unique=True, primary_key=True)
    chat_id = peewee.BigIntegerField(null=True, unique=True)

    username = peewee.CharField(max_length=32, null=True, index=True)
    first_name = peewee.CharField(max_length=255, null=True)
    last_name = peewee.CharField(max_length=255, null=True)

    is_admin = peewee.BooleanField(default=False)
    is_banned = peewee.BooleanField(default=False)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_seen_date = peewee.DateTimeField(null=True)

    @classmethod
    def get_by_user_id(cls, user_id: int) -> Optional["TelegramUser"]:
        return cls.get_or_none(cls.user_id == user_id)

    @classmethod
    def get_by_username(cls, username: str) -> Optional["TelegramUser"]:
        return cls.get_or_none(peewee.fn.LOWER(cls.username) == username.lower())

    def __str__(self) -> str:
        if self.username:
            return f'@{self.username}'
        return f'#{self.user_id}'

    def get_link(self):
        if self.username:
            return f'@{self.username}'

        full_name = self.first_name
        if self.last_name:
            full_name += ' ' + self.last_name

        return f'<a href="tg://self?id={self.user_id}">{full_name}</a>'

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f'{self.first_name} {self.last_name}'
        return cast(str, self.first_name)

    def mention_html(self, name: Optional[str] = None) -> str:
        if name is None:
            name = self.full_name

        if self.username:
            return f'<a href="https://t.me/{self.username}">{html.escape(name)}</a>'
        return f'<a href="tg://user?id={self.user_id}">{html.escape(name)}</a>'

    class Meta:
        only_save_dirty = True
