import peewee
from playhouse.db_url import connect

from config import settings

database = connect(settings.DATABASE_URL, autorollback=True)


class BaseModel(peewee.Model):
    class Meta:
        database = database
