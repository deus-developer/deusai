import datetime

from peewee import ForeignKeyField, IntegerField, CharField, DateTimeField
from playhouse.hybrid import hybrid_property

from .base import BaseModel
from .telegram_user import TelegramUser
from .telegram_chat import TelegramChat


class Pig(BaseModel):
    telegram_user = ForeignKeyField(TelegramUser, backref='pigs')
    telegram_chat = ForeignKeyField(TelegramChat, backref='pigs')

    name = CharField(max_length=32)
    weight = IntegerField()

    last_grow_at = DateTimeField()

    @hybrid_property
    def critical_chance(self) -> int:
        return 0

    @hybrid_property
    def feeded(self) -> bool:
        return datetime.datetime.now() - self.last_grow_at <= datetime.timedelta(days=1)

    class Meta:
        indexes = (
            (('telegram_user_id', 'telegram_chat_id'), True),
        )


class PigFight(BaseModel):
    telegram_chat = ForeignKeyField(TelegramChat, backref='fights')

    attacker = ForeignKeyField(Pig, backref='attacks')
    defender = ForeignKeyField(Pig, backref='defends', null=True)

    winner = ForeignKeyField(Pig, backref='wins', null=True)
    looser = ForeignKeyField(Pig, backref='looses', null=True)

    fighted_at = DateTimeField(null=True)
    created_at = DateTimeField()
