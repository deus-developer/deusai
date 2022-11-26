import peewee
from .base import BaseModel
from playhouse.postgres_ext import BinaryJSONField


def pings_default():
    return {
        'sendpin': True,
        'echo': True,
        'drop_head': True,
        'ping': True,
        'weekly_report': True,
        'notify_raid_3': True,
        'notify_raid_tz_10': True,
        'sping_notify_raid_tz': True,
        'notify_raid_tz_report': True,
    }


class Settings(BaseModel):
    sex = peewee.IntegerField(null=False, default=0)
    house = peewee.IntegerField(null=False, default=0)
    timedelta = peewee.IntegerField(null=False, default=0)
    sleeptime = peewee.CharField(max_length=13, null=False, default='00:00-00:00', index=True)

    pings = BinaryJSONField(default=pings_default)

    class Meta:
        only_save_dirty = True
