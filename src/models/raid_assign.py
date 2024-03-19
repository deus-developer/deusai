import datetime
import enum
from typing import Optional

import peewee
from playhouse.signals import Model

from src.utils import get_next_raid_date
from src.utils.functions import telegram_user_id_encode
from src.wasteland_wars import constants
from .base import BaseModel
from .player import Player


class RaidStatus(enum.IntEnum):
    UNKNOWN = -100
    REJECTED = -10
    HASNOTSEEN = -5
    CHANGE = -3
    ASSIGNED = 0
    ACCEPTED = 10
    ON_PLACE = 20
    IN_PROCESS = 30
    CONFIRMED = 35
    LEFTED = -4

    @classmethod
    def dict(cls):
        return {x.value: x.name for x in cls}


def make_menu(status: RaidStatus):
    comm = {
        RaidStatus.REJECTED: "👎 /raidpin_reject я отказываюсь",
        RaidStatus.ACCEPTED: "👍 /raidpin_accept уже выхожу",
    }
    but_set = {
        RaidStatus.REJECTED: [RaidStatus.ACCEPTED],
        RaidStatus.ASSIGNED: [RaidStatus.ACCEPTED, RaidStatus.REJECTED],
        RaidStatus.ACCEPTED: [RaidStatus.REJECTED],
        RaidStatus.CONFIRMED: [RaidStatus.REJECTED],
        RaidStatus.IN_PROCESS: [RaidStatus.REJECTED],
        RaidStatus.ON_PLACE: [RaidStatus.REJECTED],
        RaidStatus.LEFTED: [RaidStatus.REJECTED],
    }
    buttons = but_set[status] or []
    return "\n\n".join([comm[b] for b in buttons]) + "\n\n❓ /raidpin_help справочная информация"


def get_raid_status_text(status: RaidStatus) -> str:
    st = {
        RaidStatus.REJECTED: "Ты гордо отказался от ПИНа",
        RaidStatus.ASSIGNED: "Ты пока его не принял",
        RaidStatus.HASNOTSEEN: "Ты пока его не принял",
        RaidStatus.ACCEPTED: "Ты принял ПИН, но не подтвердил участие в рейде, "
        "не забудь скинуть 📟Пип-бой с с нужного километра",
        RaidStatus.IN_PROCESS: "Ты подтвердил участие в рейде. Никуда не уходи до его начала",
        RaidStatus.CONFIRMED: "Ты точно подтвердил участие в рейде.",
    }
    return st.get(status) or "Что-то пошло не так, я тебя потерял"


class RaidAssign(BaseModel, Model):
    time = peewee.DateTimeField()
    player = peewee.ForeignKeyField(Player, backref="raids_assign")
    km_assigned = peewee.IntegerField(null=True)
    status_id = peewee.IntegerField(null=True)
    is_reported = peewee.BooleanField(default=False)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        primary_key = peewee.CompositeKey("time", "player")

    def get_msg(self, text: str = ""):
        is_dark_zone_emoji = "🚷" if self.km_assigned in constants.raid_kms_tz else ""

        # noinspection PyTypeChecker
        if raid_location := constants.raid_locations_by_km.get(self.km_assigned):
            _, raid_location_emoji = raid_location
        else:
            raid_location_emoji = ""

        km_text = f"{is_dark_zone_emoji}{raid_location_emoji}<b>{self.km_assigned}км</b>"

        status_text = get_raid_status_text(self.status)
        menu_text = make_menu(self.status)
        secret_code = telegram_user_id_encode(self.player.telegram_user.user_id)

        text = (
            f"Тебе выдан <b>ПИН</b>\n"
            f"<b>{text}</b>\n"
            f"Время: <b>{self.time}</b>\n"
            f"Просто иди на {secret_code}{km_text}{secret_code}\n\n"
            f"<code>{status_text}</code>\n\n"
            f"{menu_text}\n"
        )
        return text

    @property
    def status(self) -> Optional[RaidStatus]:
        if self.status_id is not None:
            return RaidStatus(self.status_id)

    @status.setter
    def status(self, value: RaidStatus):
        self.status_id = value.value

    @classmethod
    def next_raid_players(
        cls,
        status: Optional[RaidStatus] = None,
        km: Optional[int] = None,
        time: Optional[datetime.datetime] = None,
    ):
        if time is None:
            time = get_next_raid_date()

        query = cls.filter(cls.time == time)

        if status is not None:
            query = query.filter(cls.status_id == status)

        if km is not None:
            query = query.filter(cls.km_assigned == km)

        return query

    @classmethod
    def assign(
        cls,
        time: datetime.datetime,
        player: Player,
        km: int,
        status: RaidStatus = RaidStatus.UNKNOWN,
    ):
        raid_assigned, created = cls.get_or_create(time=time, player=player)
        if km != raid_assigned.km_assigned:
            raid_assigned.status = status

            raid_assigned.km_assigned = km
            raid_assigned.save()

        return raid_assigned
