import datetime
from typing import Optional

import peewee
from playhouse.signals import Model

from .base import BaseModel
from .player import Player

ThroughDeferredMembers = peewee.DeferredThroughModel()
ThroughDeferredLiders = peewee.DeferredThroughModel()


class Group(BaseModel, Model):
    name = peewee.CharField(max_length=255, null=False, index=True)
    alias = peewee.CharField(max_length=10, null=True, index=True, unique=True)
    members = peewee.ManyToManyField(Player, backref="members", through_model=ThroughDeferredMembers)
    liders = peewee.ManyToManyField(Player, backref="liders", through_model=ThroughDeferredLiders)

    type = peewee.CharField(max_length=20, null=True)
    league = peewee.CharField(max_length=20, null=True)

    parent = peewee.ForeignKeyField("self", backref="owners", null=True)
    is_active = peewee.BooleanField(null=False, default=False)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    @classmethod
    def get_by_name(cls, group_name: str, group_type: Optional[str] = None) -> Optional["Group"]:
        where_stmt = (cls.name == group_name) | (cls.alias == group_name)
        select_stmt = cls.select().where(where_stmt)

        if group_type:
            select_stmt = select_stmt.filter(cls.type == group_type)

        select_stmt = select_stmt.limit(1)
        groups = select_stmt
        if groups:
            return groups[0]

    class Meta(object):
        indexes = ((("name", "type"), True),)
        only_save_dirty = True


class GroupPlayerThrough(BaseModel, Model):
    player = peewee.ForeignKeyField(Player)
    group = peewee.ForeignKeyField(Group)

    class Meta:
        table_name = "group_player_through"


class GroupLiderThrough(BaseModel, Model):
    lider = peewee.ForeignKeyField(Player)
    group = peewee.ForeignKeyField(Group)

    class Meta:
        table_name = "group_lider_through"


ThroughDeferredMembers.set_model(GroupPlayerThrough)
ThroughDeferredLiders.set_model(GroupLiderThrough)
