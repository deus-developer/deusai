import peewee
from .base import BaseModel
from .telegram_user import TelegramUser


class LeadTime(BaseModel, peewee.Model):
    executor = peewee.ForeignKeyField(TelegramUser, backref='leadstime')
    start_time = peewee.BigIntegerField(null=False)
    end_time = peewee.BigIntegerField(null=False)

    name = peewee.CharField(max_length=255, null=True)
    description = peewee.CharField(max_length=255, null=True)
    update = peewee.TextField(null=False, default='{}')

    class Meta:
        only_save_dirty = True
