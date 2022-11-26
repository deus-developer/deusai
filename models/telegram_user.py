import datetime
import peewee

from .base import BaseModel


class TelegramUser(BaseModel):
    # users.user_id
    user_id = peewee.IntegerField(
        null=False, index=True, unique=True, primary_key=True)
    # users.chatid
    chat_id = peewee.IntegerField(null=True, unique=True)
    # users.username
    username = peewee.CharField(max_length=32, null=True, index=True)
    first_name = peewee.CharField(max_length=255, null=True)
    last_name = peewee.CharField(max_length=255, null=True)

    # FROM admins
    is_admin = peewee.BooleanField(default=False)
    # FROM blacklist
    is_banned = peewee.BooleanField(default=False)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_seen_date = peewee.DateTimeField(null=True)

    @classmethod
    def get_by_user_id(cls, user_id):
        return cls.get_or_none(cls.user_id == user_id)

    @classmethod
    def get_by_username(cls, username):
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

    class Meta:
        only_save_dirty = True
