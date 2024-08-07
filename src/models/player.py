import datetime
from typing import List, cast, Optional, TYPE_CHECKING

import peewee
from playhouse.hybrid import hybrid_property
from playhouse.signals import post_save, Model, pre_save

from src.models import Settings
from src.utils.functions import get_next_raid_date
from .base import BaseModel
from .telegram_user import TelegramUser

if TYPE_CHECKING:
    from src.models import RaidAssign, Group

ThroughDeferredTransitionsRecived = peewee.DeferredThroughModel()
ThroughDeferredTransitionsSended = peewee.DeferredThroughModel()

KEY_SKILLS = ("hp", "power", "accuracy", "oratory", "agility")
PLAYER_STAT_DUPLICATING_PARAMS = (
    "hp",
    "attack",
    "defence",
    "power",
    "accuracy",
    "oratory",
    "agility",
    "stamina",
    "dzen",
)


class Player(BaseModel, Model):
    telegram_user = peewee.ForeignKeyField(TelegramUser, backref="player")

    nickname = peewee.CharField(max_length=255, null=False, default="", index=True, unique=True)

    fraction = peewee.CharField(max_length=255, null=False, default="")
    title = peewee.CharField(max_length=255, null=False, default="")

    attack = peewee.IntegerField(null=False, default=0)
    defence = peewee.IntegerField(null=False, default=0)

    hp = peewee.IntegerField(null=False, default=0)
    power = peewee.IntegerField(null=False, default=0)
    agility = peewee.IntegerField(null=False, default=0)
    oratory = peewee.IntegerField(null=False, default=0)
    accuracy = peewee.IntegerField(null=False, default=0)

    dzen = peewee.IntegerField(null=False, default=0)
    stamina = peewee.IntegerField(null=False, default=0)
    sum_stat = peewee.IntegerField(null=False, default=0)

    settings = peewee.ForeignKeyField(Settings, backref="player", on_delete="CASCADE", null=True)

    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    @hybrid_property
    def raid_reward(self) -> float:
        return (self.hp + self.attack + self.defence + self.agility) / 3

    def lider_access_query(self):
        from src.models import GroupPlayerThrough, Group

        return (
            self.select()
            .join(
                GroupPlayerThrough,
                on=(
                    (Player.id == GroupPlayerThrough.player_id)
                    & (GroupPlayerThrough.group_id << [x.id for x in self.liders])
                ),
            )
            .join(Group, on=(Group.id == GroupPlayerThrough.group_id))
            .distinct()
        )

    def add_stats(self, **kwargs):
        return PlayerStatHistory.create(player=self, **kwargs)

    def update_stats_from_history(self):
        if self.stats.time < self.last_update:
            return

        stats = self.stats
        for attr in PLAYER_STAT_DUPLICATING_PARAMS:
            setattr(self, attr, getattr(stats, attr))

        self.save()

    def set_sum_stat(self, sum_stat=0):
        self.sum_stat = sum_stat
        self.save()

    @property
    def stats(self) -> Optional["PlayerStatHistory"]:
        return self.history_stats.order_by(PlayerStatHistory.time.desc()).get() if self.history_stats else None

    @hybrid_property
    def actual_raid(self) -> Optional["RaidAssign"]:
        return self.raid_near_time()

    def raid_near_time(self, time: Optional[datetime.datetime] = None) -> Optional["RaidAssign"]:
        if not self.raids_assign:
            return

        from src.models import RaidAssign

        latest_raid = (
            self.raids_assign.filter(RaidAssign.time == get_next_raid_date(time))
            .order_by(RaidAssign.time.desc())
            .first()
        )
        return latest_raid

    @classmethod
    def get_by_nickname(cls, nickname) -> Optional["Player"]:
        return cls.get_or_none(peewee.fn.LOWER(cls.nickname).contains(nickname.lower()))

    @classmethod
    def get_iterator(cls):
        return (
            cls.select()
            .join(TelegramUser)
            .where((Player.telegram_user.is_banned == False) and (Player.is_active == True))
        )

    @classmethod
    def get_top(cls, field, group: Optional["Group"] = None) -> List["Player"]:
        model = group.members if group else Player

        query = (
            model.select(
                Player.nickname,
                Player.telegram_user,
                field.alias("value"),
                peewee.fn.dense_rank().over(order_by=[field.desc()]).alias("idx"),
            )
            .filter(Player.is_active == True)
            .order_by(field.desc())
        )

        for player in query:
            yield player

    def get_activity_flag(self) -> str:
        if not self.telegram_user.last_seen_date:
            return "?"
        weeks_not_seen = (datetime.datetime.now() - self.telegram_user.last_seen_date).days // 7
        if weeks_not_seen >= 4:
            return "---"
        return weeks_not_seen * "*"

    def add_to_group(self, group):
        from src.models import Group

        if group.type:
            for instance in self.members.filter(Group.type == group.type):
                self.members.remove(instance)

        if group not in self.members:
            self.members.add(group)

    def add_to_lider(self, group):
        if group not in self.liders:
            self.liders.add(group)

    @property
    def km(self) -> int:
        from src.models import Radar

        radar = self.radars.order_by(Radar.time.desc()).limit(1)
        if not radar:
            return 0
        return radar[0].km

    @property
    def goat(self) -> Optional["Group"]:
        from src.models import Group

        if self.members is not None:
            goat = self.members.filter(Group.type == "goat").limit(1)
            return goat.get() if goat else None
        return None

    @property
    def gang(self) -> Optional["Group"]:
        from src.models import Group

        if self.members is not None:
            gang = self.members.filter(Group.type == "gang").limit(1)
            return gang.get() if gang else None
        return None

    @goat.setter
    def goat(self, value: "Group"):
        from src.models import Group

        if value is not None:
            self.add_to_group(value)
        else:
            for group in self.members.filter(Group.type == "goat"):
                self.members.remove(group)

    @gang.setter
    def gang(self, value: "Group"):
        from src.models import Group

        if value is not None:
            self.add_to_group(value)
        else:
            for group in self.members.filter(Group.type == "gang"):
                self.members.remove(group)

    def ban_player(self):
        self.liders.clear()
        self.members.clear()
        self.is_active = False
        self.save()

    def unban_player(self):
        self.is_active = True
        self.save()

    def __str__(self) -> str:
        return cast(str, self.nickname)

    def mention_html(self, name: Optional[str] = None) -> str:
        if name is None:
            name = self.nickname

        return self.telegram_user.mention_html(name)

    class Meta:
        only_save_dirty = True


class PlayerStatHistory(BaseModel, Model):
    stat_id = peewee.BigAutoField(unique=True, primary_key=True, index=True, null=False)
    player = peewee.ForeignKeyField(Player, backref="history_stats")

    time = peewee.DateTimeField(default=datetime.datetime.now)

    attack = peewee.IntegerField(null=False, default=0)
    defence = peewee.IntegerField(null=False, default=0)

    hp = peewee.IntegerField(null=False, default=0)
    power = peewee.IntegerField(null=False, default=0)
    accuracy = peewee.IntegerField(null=False, default=0)
    oratory = peewee.IntegerField(null=False, default=0)
    agility = peewee.IntegerField(null=False, default=0)

    stamina = peewee.IntegerField(null=False, default=0)
    dzen = peewee.IntegerField(null=False, default=0)

    sum_stat = peewee.IntegerField(null=False, default=0)

    def set_sum_stat(self):
        self.sum_stat = sum(getattr(self, attr, 0) for attr in KEY_SKILLS)

    def __str__(self) -> str:
        return f"#{self.stat_id}"

    class Meta:
        only_save_dirty = True


@post_save(sender=PlayerStatHistory)
def post_save_handler(_, instance: PlayerStatHistory, created):
    instance.player.update_stats_from_history()
    instance.player.set_sum_stat(instance.sum_stat)


@pre_save(sender=PlayerStatHistory)
def pre_save_handler_stats(_, instance: PlayerStatHistory, created):
    return instance.set_sum_stat()
