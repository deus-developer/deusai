import peewee
import datetime
from peewee import Model
from models import (
    BaseModel,
    Player
)


class Radar(BaseModel, Model):
    player = peewee.ForeignKeyField(Player, backref='radars')
    time = peewee.DateTimeField(default=datetime.datetime.now)
    km = peewee.IntegerField(null=True)
    status = peewee.IntegerField(null=True)

    class Meta:
        only_save_dirty = True
