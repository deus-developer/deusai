import peewee
import datetime
from peewee import Model

from models import (
    BaseModel,
    Player
)


class SPItem(BaseModel, Model):
    id = peewee.AutoField()
    name = peewee.CharField(max_length=255, null=False, index=True)
    description = peewee.TextField(default='')
    price = peewee.IntegerField(null=True)
    photo_fp = peewee.CharField(max_length=255, default='')

    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True


class SPProcess(BaseModel, Model):
    id = peewee.AutoField()
    status_id = peewee.IntegerField(default=0)
    player = peewee.ForeignKeyField(Player, backref='spitems')
    executor = peewee.ForeignKeyField(Player, backref='spprocess', null=True)
    item = peewee.ForeignKeyField(SPItem, backref='process')

    karma = peewee.IntegerField(default=0)
    raids21 = peewee.IntegerField(default=0)
    loose_raids_f = peewee.IntegerField(default=0)

    message_id = peewee.BigIntegerField(null=True)
    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True
