from __future__ import annotations
import datetime
import logging
from typing import List

import peewee
from playhouse.hybrid import hybrid_property
from playhouse.signals import (
    Model,
    post_save,
    pre_save
)

from models import (
    KarmaTransition,
    Notebook,
    Rank,
    Settings
)
from utils.functions import next_raid
from .base import BaseModel
from .telegram_user import TelegramUser

ThroughDeferredTransitionsRecived = peewee.DeferredThroughModel()
ThroughDeferredTransitionsSended = peewee.DeferredThroughModel()

KEY_SKILLS = ('hp', 'power', 'accuracy', 'oratory', 'agility')
PLAYER_STAT_DUPLICATING_PARAMS = (
    'hp', 'attack', 'defence', 'power', 'accuracy',
    'oratory', 'agility', 'stamina', 'dzen', 'karma',
    'regeneration_l', 'raids21', 'raid_points',
    'loose_raids', 'loose_weeks'
)


class Player(BaseModel, Model):
    telegram_user = peewee.ForeignKeyField(TelegramUser, backref='player', on_delete='CASCADE', null=True)  # users.user_id

    mentor = peewee.ForeignKeyField('self', backref='referrals', null=True)

    nickname = peewee.CharField(max_length=255, null=False, default='', index=True, unique=True)

    fraction = peewee.CharField(max_length=255, null=False, default='')
    pu_code = peewee.CharField(max_length=12, null=False, default='')
    title = peewee.CharField(max_length=255, null=False, default='')

    is_active = peewee.BooleanField(default=False)
    frozen = peewee.BooleanField(default=False)
    frozendate = peewee.DateTimeField(null=True)

    hp = peewee.IntegerField(null=False, default=0)
    power = peewee.IntegerField(null=False, default=0)
    agility = peewee.IntegerField(null=False, default=0)
    oratory = peewee.IntegerField(null=False, default=0)
    accuracy = peewee.IntegerField(null=False, default=0)
    attack = peewee.IntegerField(null=False, default=0)
    defence = peewee.IntegerField(null=False, default=0)
    dzen = peewee.IntegerField(null=False, default=0)
    stamina = peewee.IntegerField(null=False, default=0)
    regeneration_l = peewee.IntegerField(null=False, default=0)
    batcoh_l = peewee.IntegerField(null=False, default=0)

    sum_stat = peewee.IntegerField(null=False, default=0)

    rank = peewee.ForeignKeyField(Rank, backref='players', null=True)
    settings = peewee.ForeignKeyField(Settings, backref='player', on_delete='CASCADE', null=True)
    notebook = peewee.ForeignKeyField(Notebook, backref='player', on_delete='CASCADE', null=True)

    karma = peewee.IntegerField(null=False, default=0)
    karma_recived = peewee.ManyToManyField(
        model=KarmaTransition,
        backref='recivier',
        through_model=ThroughDeferredTransitionsRecived
    )
    karma_sended = peewee.ManyToManyField(
        model=KarmaTransition,
        backref='sender',
        through_model=ThroughDeferredTransitionsSended
    )

    raids21 = peewee.IntegerField(null=False, default=0)
    raid_points = peewee.FloatField(null=False, default=0.000)
    loose_raids = peewee.IntegerField(null=False, default=0)
    loose_weeks = peewee.IntegerField(null=False, default=0)

    raid_reward = peewee.FloatField(null=False, default=0.000)

    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    __goat = None
    __gang = None

    def lider_access_query(self):
        from models import (
            GroupPlayerThrough,
            Group
        )
        return self.select()\
            .join(GroupPlayerThrough, on=(
                (Player.id == GroupPlayerThrough.player_id) &
                (GroupPlayerThrough.group_id << [x.id for x in self.liders])
            ))\
            .join(Group, on=(Group.id == GroupPlayerThrough.group_id)) \
            .distinct()

    def add_stats(self, **kwargs):
        return PlayerStatHistory.create(player=self, **kwargs)

    def update_stats_from_history(self):
        if self.stats.time < self.last_update:
            return False
        stats = self.stats
        for attr in PLAYER_STAT_DUPLICATING_PARAMS:
            setattr(self, attr, getattr(stats, attr))

        self.save()

    def set_raid_reward(self):
        self.raid_reward = (self.hp + self.attack + self.defence + self.agility) // 3
        self.save()

    def set_sum_stat(self, sum_stat=0):
        sum_stat_current = sum([getattr(self, attr, 0) for attr in KEY_SKILLS])
        if self.is_active:
            self.sum_stat = sum_stat_current
        elif self.sum_stat < sum_stat_current:
            self.sum_stat = sum_stat_current
        else:
            return

        self.save()

    @property
    def stats(self):
        if not self.history_stats:
            return None
        return self.history_stats.order_by(PlayerStatHistory.time.desc()).get()

    @hybrid_property
    def actual_raid(self):
        return self.raid_near_time()

    def raid_near_time(self, time=None):
        if not self.raids_assign:
            return
        from models import RaidAssign
        latest_raid = self.raids_assign \
            .filter(RaidAssign.time == next_raid(time)) \
            .order_by(RaidAssign.time.desc()) \
            .first()
        return latest_raid

    @classmethod
    def get_by_nickname(cls, nickname):
        return cls.get_or_none(peewee.fn.LOWER(cls.nickname).contains(nickname.lower()))

    @classmethod
    def get_iterator(cls):
        return cls.select() \
            .join(TelegramUser) \
            .where(
                (Player.frozen == False) and
                (Player.telegram_user.is_banned == False) and
                (Player.is_active == True)
            )

    @classmethod
    def get_top(cls, field, group=None) -> List[Player]:
        model = group.members if group else Player

        query = model.select(
            Player.nickname,
            Player.telegram_user,
            field.alias('value'),
            peewee.fn.dense_rank().over(
                order_by=[field.desc()]
            ).alias('idx')
        ).filter(Player.is_active == True) \
            .order_by(field.desc())

        for player in query:
            yield player

    def get_activity_flag(self):
        if not self.telegram_user.last_seen_date:
            return '?'

        weeks_not_seen = (datetime.datetime.now() - self.telegram_user.last_seen_date).days // 7
        if weeks_not_seen >= 4:
            return '---'
        return weeks_not_seen * '*'

    def add_to_group(self, group):
        from models import Group
        
        if group.type:
            for instance in self.members.filter(Group.type == group.type):
                self.members.remove(instance)
        if group not in self.members:
            self.members.add(group)

    def add_to_lider(self, group):
        if group not in self.liders:
            self.liders.add(group)

    @property
    def km(self):
        from models import Radar
        radar = self.radars.order_by(Radar.time.desc()).limit(1)
        if not radar:
            return 0
        return radar[0].km

    @property
    def goat(self):
        if self.__goat is not None:
            return self.__goat

        from models import Group
        if self.members is not None:
            goat = self.members.filter(Group.type == 'goat').limit(1)
            self.__goat = goat.get() if goat else None
            return self.__goat
        return None

    @property
    def gang(self):
        if self.__gang is not None:
            return self.__gang

        from models import Group
        if self.members is not None:
            gang = self.members.filter(Group.type == 'gang').limit(1)
            self.__gang = gang.get() if gang else None
            return self.__gang
        return None

    @goat.setter
    def goat(self, value):
        from models import Group
        if value is not None:
            self.add_to_group(value)
        else:
            for group in self.members.filter(Group.type == 'goat'):
                self.members.remove(group)

    @gang.setter
    def gang(self, value):
        from models import Group
        if value is not None:
            self.add_to_group(value)
        else:
            for group in self.members.filter(Group.type == 'gang'):
                self.members.remove(group)

    def delete_player(self):
        self.liders.clear()
        self.members.clear()
        self.is_active = False
        try:
            self.save()
        except (Exception,):
            return False
        return True

    def to_player(self):
        self.is_active = True
        try:
            self.save()
        except (Exception,):
            return False
        return True

    def __str__(self):
        return self.nickname

    class Meta:
        only_save_dirty = True


class PlayerRecivedThrough(BaseModel, Model):
    player = peewee.ForeignKeyField(Player)
    transition = peewee.ForeignKeyField(KarmaTransition)

    class Meta:
        table_name = 'player_recived_through'


class PlayerSendedThrough(BaseModel, Model):
    player = peewee.ForeignKeyField(Player)
    transition = peewee.ForeignKeyField(KarmaTransition)

    class Meta:
        table_name = 'player_sended_through'


ThroughDeferredTransitionsRecived.set_model(PlayerRecivedThrough)
ThroughDeferredTransitionsSended.set_model(PlayerSendedThrough)


class PlayerStatHistory(BaseModel, Model):
    stat_id = peewee.BigAutoField(unique=True, primary_key=True, index=True, null=False)
    player = peewee.ForeignKeyField(Player, backref='history_stats')

    time = peewee.DateTimeField(default=datetime.datetime.now)
    hp = peewee.IntegerField(null=False, default=0)
    attack = peewee.IntegerField(null=False, default=0)
    defence = peewee.IntegerField(null=False, default=0)
    power = peewee.IntegerField(null=False, default=0)
    accuracy = peewee.IntegerField(null=False, default=0)
    oratory = peewee.IntegerField(null=False, default=0)
    agility = peewee.IntegerField(null=False, default=0)
    stamina = peewee.IntegerField(null=False, default=0)
    dzen = peewee.IntegerField(null=False, default=0)
    regeneration_l = peewee.IntegerField(null=False, default=0)
    batcoh_l = peewee.IntegerField(null=False, default=0)
    sum_stat = peewee.IntegerField(null=False, default=0)
    karma = peewee.IntegerField(null=False, default=0)

    raids21 = peewee.IntegerField(null=False, default=0)
    raid_points = peewee.FloatField(null=False, default=0.000)
    loose_raids = peewee.IntegerField(null=False, default=0)
    loose_weeks = peewee.IntegerField(null=False, default=0)

    def set_sum_stat(self):
        sum_stat = sum(getattr(self, attr, 0) for attr in KEY_SKILLS)
        if self.sum_stat > sum_stat and not self.player.is_active:
            return
        self.sum_stat = sum_stat

    def __str__(self) -> str:
        return f'#{self.stat_id}'

    class Meta:
        only_save_dirty = True


@post_save(sender=PlayerStatHistory)
def post_save_handler(sender, instance: PlayerStatHistory, created):
    instance.player.update_stats_from_history()
    instance.player.set_raid_reward()
    instance.player.set_sum_stat(instance.sum_stat)


@pre_save(sender=PlayerStatHistory)
def pre_save_handler_stats(sender, instance: PlayerStatHistory, created):
    stats = instance.player
    is_active = stats.is_active
    if is_active:
        return instance.set_sum_stat()
    for attr in KEY_SKILLS:
        old_v = getattr(stats, attr, 0) if stats else 0
        v = getattr(instance, attr, 0)
        if v < old_v:
            setattr(instance, attr, old_v)
    instance.set_sum_stat()


@post_save(sender=Player)
def post_save_handler_player(sender, instance: Player, created):
    if not created:
        return
    logging.info(f'NEW PLAYER {sender} {instance}')


@pre_save(sender=Player)
def pre_save_handler_player(sender, instance: Player, created):
    if not instance.is_active:
        return
