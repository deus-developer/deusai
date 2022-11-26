import datetime
import peewee

from .base import BaseModel


class TelegramChat(BaseModel):
    chat_id = peewee.BigIntegerField(
        null=False, index=True, unique=True, primary_key=True)
    chat_type = peewee.CharField(
        max_length=10,
        choices=(('CHANNEL', 'channel'), ('GROUP', 'group'), ('SUPERGROUP',
                                                              'supergroup')))
    title = peewee.CharField(max_length=255, null=True)
    shortname = peewee.CharField(max_length=32, null=True, index=True)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    is_active = peewee.BooleanField(default=False)

    @classmethod
    def get_by_name(cls, chat_name) -> 'TelegramChat':
        if chat_name:
            return cls.select().where((cls.title == chat_name) |
                                      (cls.shortname == chat_name)).first()

    def __str__(self):
        return self.title
        
    class Meta:
        only_save_dirty = True
