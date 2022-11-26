import peewee
import datetime
from typing import List
from .base import BaseModel

KEY_SKILLS = ('hp', 'power', 'accuracy', 'oratory', 'agility')
PLAYER_STAT_DUPLICATING_PARAMS = ('hp', 'attack', 'defence', 'power', 'accuracy',
                                  'oratory', 'agility', 'stamina', 'dzen')


class PVPEnemy(BaseModel, peewee.Model):
    nickname = peewee.CharField(max_length=255, null=False, default='', index=True)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)
    fraction = peewee.CharField(max_length=255, null=False, default='')
    gang = peewee.CharField(max_length=255, null=True)
    goat = peewee.CharField(max_length=255, null=True)

    hp = peewee.IntegerField(null=False, default=0)
    attack = peewee.IntegerField(null=False, default=0)
    defence = peewee.IntegerField(null=False, default=0)
    power = peewee.IntegerField(null=False, default=0)
    accuracy = peewee.IntegerField(null=False, default=0)
    oratory = peewee.IntegerField(null=False, default=0)
    agility = peewee.IntegerField(null=False, default=0)
    stamina = peewee.IntegerField(null=False, default=0)
    dzen = peewee.IntegerField(null=False, default=0)

    pvp_hp = peewee.IntegerField(null=False, default=0)
    pvp_attack = peewee.IntegerField(null=False, default=0)

    sum_stat = peewee.IntegerField(null=False, default=0)
    regeneration_l = peewee.IntegerField(default=0)

    @classmethod
    def get_by_nickname(cls, nickname):
        return cls.get_or_none(
            peewee.fn.LOWER(cls.nickname).contains(nickname.lower())
        )

    @classmethod
    def get_iterator(cls):
        return cls.select()

    def set_sum_stat(self):
        self.sum_stat = sum(getattr(self, attr) for attr in KEY_SKILLS)

    @classmethod
    def get_top(cls, field) -> List['PVPEnemy']:
        query = PVPEnemy.select(
            PVPEnemy.nickname,
            field.alias('value'),
            peewee.fn.rank().over(
                order_by=[field.desc()]
            ).alias('rank')
        )

        query = query.order_by(field.desc())

        for player in query:
            yield player

    def __str__(self):
        return self.nickname

    class Meta:
        only_save_dirty = True
