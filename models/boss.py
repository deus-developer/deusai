import peewee
import datetime
from .base import BaseModel
from models import Player

ThroughDeferred = peewee.DeferredThroughModel()


class Boss(BaseModel, peewee.Model):
    name = peewee.CharField(max_length=255, null=False, default='', index=True)
    hp = peewee.IntegerField(null=False, default=0)
    start_km = peewee.IntegerField(null=False, default=0)
    last_km = peewee.IntegerField(null=False, default=0)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    subscribers = peewee.ManyToManyField(Player, backref='boss_subscribes', through_model=ThroughDeferred)

    def __str__(self):
        return self.name

    class Meta:
        only_save_dirty = True


class BossPlayerThrough(BaseModel, peewee.Model):
    player = peewee.ForeignKeyField(Player)
    boss = peewee.ForeignKeyField(Boss)

    class Meta:
        table_name = 'boss_subscribe_through'


ThroughDeferred.set_model(BossPlayerThrough)
