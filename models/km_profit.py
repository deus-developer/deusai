import peewee
from .base import BaseModel


class KMProfit(BaseModel, peewee.Model):
    start_km = peewee.IntegerField(null=False, default=1)
    end_km = peewee.IntegerField(null=False, default=4)
    avg_profit = peewee.IntegerField(null=False, default=43)

    @classmethod
    def get_tier(cls, km: int = 1):
        km = cls.select().where((cls.start_km <= km) & (cls.end_km >= km)).limit(1)
        return km.get() if km.exists() else cls.get_or_none(id=1)

    class Meta:
        only_save_dirty = True
