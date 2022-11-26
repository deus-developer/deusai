import datetime
import peewee
from peewee import Model
from models import BaseModel


class Feedback(BaseModel, Model):
    message_id = peewee.BigIntegerField(null=True)
    original_chat_id = peewee.BigIntegerField(null=False)
    status = peewee.IntegerField(default=0)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)