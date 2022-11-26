import peewee
import datetime
from peewee import Model
from models import (
    BaseModel,
    Player
)


class PVP(BaseModel, Model):
    hash = peewee.CharField(max_length=255, null=False, unique=True, primary_key=True)
    winner = peewee.ForeignKeyField(Player, backref='pvp_win')
    looser = peewee.ForeignKeyField(Player, backref='pvp_loose')
    text = peewee.TextField(default='', null=False)
    time = peewee.DateTimeField(default=datetime.datetime.now, null=False)

    km = peewee.IntegerField(null=True)
    caps = peewee.IntegerField(null=True)
    mats = peewee.IntegerField(null=True)

    class Meta:
        only_save_dirty = True
