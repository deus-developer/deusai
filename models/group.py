import datetime
import peewee
from playhouse.signals import Model
from .base import BaseModel
from .player import Player

ThroughDeferredMembers = peewee.DeferredThroughModel()
ThroughDeferredLiders = peewee.DeferredThroughModel()


class Group(BaseModel, Model):
    name = peewee.CharField(max_length=255, null=False, index=True)
    alias = peewee.CharField(max_length=10, null=True, index=True, unique=True)
    members = peewee.ManyToManyField(Player, backref='members', through_model=ThroughDeferredMembers)
    liders = peewee.ManyToManyField(Player, backref='liders', through_model=ThroughDeferredLiders)

    type = peewee.CharField(max_length=20, null=True)
    league = peewee.CharField(max_length=20, null=True)

    parent = peewee.ForeignKeyField('self', backref='owners', null=True)
    is_active = peewee.BooleanField(null=False, default=False)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    @classmethod
    def get_by_name(cls, group_name='', group_type: str = None) -> 'Group':
        if group_name:
            gr = cls.select().where(
                (cls.name == group_name) |
                (cls.alias == group_name)
            )
            if group_type:
                gr = gr.filter(cls.type == group_type)
            gr = gr.limit(1)
            return gr[0] if gr else None

    class Meta(object):
        indexes = (
            (('name', 'group_type'), True),
        )
        only_save_dirty = True


class GroupPlayerThrough(BaseModel, Model):
    player = peewee.ForeignKeyField(Player)
    group = peewee.ForeignKeyField(Group)

    class Meta:
        table_name = 'group_player_through'


class GroupLiderThrough(BaseModel, Model):
    lider = peewee.ForeignKeyField(Player)
    group = peewee.ForeignKeyField(Group)

    class Meta:
        table_name = 'group_lider_through'


ThroughDeferredMembers.set_model(GroupPlayerThrough)
ThroughDeferredLiders.set_model(GroupLiderThrough)
