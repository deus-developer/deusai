import peewee
import datetime
from peewee import Model
from models import BaseModel


class KarmaTransition(BaseModel, Model):
    module_name = peewee.CharField(max_length=255, null=False)
    amount = peewee.IntegerField(default=0)
    description = peewee.TextField(default='UNKOWN TRANSFER')
    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True
