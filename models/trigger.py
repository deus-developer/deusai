import peewee
import datetime
from peewee import Model

from models import (
    BaseModel,
    TelegramChat
)


class Trigger(BaseModel, Model):
    id = peewee.AutoField()
    chat = peewee.ForeignKeyField(TelegramChat, backref='triggers')
    request = peewee.TextField(default='!триггер')
    answer = peewee.TextField(default='Триггер!')
    type = peewee.CharField(
        max_length=9,
        choices=(('AUDIO', 'audio'), ('DOCUMENT', 'document'),
                 ('PHOTO', 'photo'), ('STICKER', 'sticker'),
                 ('VIDEO', 'video'), ('TEXT', 'text'))
    )
    file_path = peewee.CharField(max_length=255, default='')

    admin_only = peewee.BooleanField(default=False)
    ignore_case = peewee.BooleanField(default=True)
    pin_message = peewee.BooleanField(default=False)
    repling = peewee.BooleanField(default=True)
    in_message = peewee.BooleanField(default=False)
