import peewee
import datetime
from peewee import Model

from models import BaseModel
from models import (
    Player,
    Group
)


class Taking(BaseModel, Model):
    id = peewee.AutoField()

    group = peewee.ForeignKeyField(Group, backref='takings')
    invoker = peewee.ForeignKeyField(Player, backref='takings_invoke')
    km = peewee.IntegerField(null=False)

    reported = peewee.BooleanField(default=False)

    chat_id = peewee.BigIntegerField(null=False)
    message_id = peewee.BigIntegerField(null=True)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True


class TakingStatus(BaseModel, Model):
    taking = peewee.ForeignKeyField(Taking, backref='statuses')
    player = peewee.ForeignKeyField(Player, backref='takings_status')
    status_id = peewee.IntegerField(null=False)

    class Meta:
        only_save_dirty = True
