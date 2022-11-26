import datetime
import peewee

from .base import BaseModel


class RaidResult(BaseModel):

    km = peewee.IntegerField(null=False, default=0)
    name = peewee.CharField(max_length=255, null=False, default='')
    rating = peewee.IntegerField(null=False, default=0)
    league = peewee.CharField(max_length=255, null=False, default='-')
    wingoat = peewee.CharField(max_length=255, null=True, default='')
    wingoatpercent = peewee.FloatField(null=False, default=0.00)
    ourgoat = peewee.CharField(max_length=255, null=True, default='')
    ourgoatpercent = peewee.FloatField(null=False, default=0.00)
    goats = peewee.TextField(null=False, default='{}')
    raiders = peewee.TextField(null=False, default='{}')
    post_id = peewee.CharField(max_length=255, null=False, default='')
    date = peewee.DateTimeField(null=True)
    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    @classmethod
    def exist_rows(cls, date):
        rows_count = cls \
            .select() \
            .where(RaidResult.date == date) \
            .count()
        return rows_count > 0

    class Meta:
        only_save_dirty = True
