import peewee
import datetime
from .base import BaseModel


class Notebook(BaseModel):
    passed = peewee.IntegerField(null=False, default=0)
    kills_pve = peewee.IntegerField(null=False, default=0)
    kills_pvp = peewee.IntegerField(null=False, default=0)
    hit_giant = peewee.IntegerField(null=False, default=0)
    win_boss = peewee.IntegerField(null=False, default=0)
    escaped = peewee.IntegerField(null=False, default=0)
    participated = peewee.IntegerField(null=False, default=0)
    used_stim = peewee.IntegerField(null=False, default=0)
    used_speeds = peewee.IntegerField(null=False, default=0)
    broken_things = peewee.IntegerField(null=False, default=0)
    completed_assignments = peewee.IntegerField(null=False, default=0)
    open_gifts = peewee.IntegerField(null=False, default=0)
    send_gifts = peewee.IntegerField(null=False, default=0)
    open_randbox = peewee.IntegerField(null=False, default=0)
    used_ster_meld = peewee.IntegerField(null=False, default=0)
    dange_completed = peewee.IntegerField(null=False, default=0)
    passed_cave = peewee.IntegerField(null=False, default=0)
    not_passed_cave = peewee.IntegerField(null=False, default=0)
    win_of_dome = peewee.IntegerField(null=False, default=0)
    invited = peewee.IntegerField(null=False, default=0)
    open_box = peewee.IntegerField(null=False, default=0)
    deads = peewee.IntegerField(null=False, default=0)

    buffer = peewee.IntegerField(null=False, default=0)

    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True
