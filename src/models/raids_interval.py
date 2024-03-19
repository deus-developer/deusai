import datetime

import peewee

from .base import BaseModel


class RaidsInterval(BaseModel):
    start_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_date = peewee.DateTimeField(default=datetime.datetime.now)

    @classmethod
    def interval_by_date(cls, date: datetime.datetime, offset: int = 0):
        if x := cls.select().where((cls.start_date <= date) & (date <= cls.last_date)).order_by(cls.id.desc()).limit(1):
            interval = x.get() if x.exists() else None
        else:
            interval = None
        if offset > 0 and interval:
            interval = cls.get_or_none(id=interval.id - offset)
        return interval

    class Meta:
        only_save_dirty = True
