import peewee
import datetime
from peewee import Model

from models import BaseModel


class Rank(BaseModel, Model):
    emoji = peewee.CharField(max_length=255, null=False)
    name = peewee.CharField(max_length=255, null=False)
    priority = peewee.IntegerField(default=0)
    description = peewee.TextField(default='')
    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    def remove_(self):
        nr = Rank.select().where(Rank.priority < self.priority).order_by(Rank.priority.desc()).limit(1).get()
        if not nr:
            nr = Rank.select().where(Rank.priority > self.priority).order_by(Rank.priority.ask()).limit(1).get()

        for pl in self.players:
            pl.rank = nr
            pl.save()
        self.delete_instance()

    class Meta:
        only_save_dirty = True
