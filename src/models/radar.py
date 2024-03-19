import datetime

import peewee
from peewee import Model

from .base import BaseModel
from .player import Player


class Radar(BaseModel, Model):
    player = peewee.ForeignKeyField(Player, backref="radars")
    time = peewee.DateTimeField(default=datetime.datetime.now)
    km = peewee.IntegerField(null=True)
    status = peewee.IntegerField(null=True)

    class Meta:
        only_save_dirty = True
