import datetime
import enum

import peewee
from playhouse.signals import Model

from utils import next_raid
from utils.functions import user_id_encode
from ww6StatBotWorld import Wasteland
from .base import BaseModel
from .player import Player
from .radar import Radar


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
        RaidStatus.LEFTED: [RaidStatus.REJECTED]
    }
    buttons = but_set[status] or []
    return "\n\n".join([comm[b] for b in buttons]) + "\n\n❓ /raidpin_help справочная информация"


def get_status(status: RaidStatus):
    st = {
        RaidStatus.REJECTED: "Ты гордо отказался от ПИНа",
        RaidStatus.ASSIGNED: "Ты пока его не принял",
        RaidStatus.HASNOTSEEN: "Ты пока его не принял",
        RaidStatus.ACCEPTED: "Ты принял ПИН, но не подтвердил участие в рейде, "
                             "не забудь скинуть 📟Пип-бой с с нужного километра",
        RaidStatus.IN_PROCESS: "Ты подтвердил участие в рейде. Никуда не уходи до его начала",
        RaidStatus.CONFIRMED: "Ты точно подтвердил участие в рейде."
    }
    return st.get(status) or "Что-то пошло не так, я тебя потерял"


class RaidAssign(BaseModel, Model):
    time = peewee.DateTimeField()
    player = peewee.ForeignKeyField(Player, backref='raids_assign')
    km_assigned = peewee.IntegerField(null=True)
    status_id = peewee.IntegerField(null=True)
    is_reported = peewee.BooleanField(default=False)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        primary_key = peewee.CompositeKey('time', 'player')

    def get_msg(self, text=''):
        if self.km_assigned in Wasteland.raid_kms_tz:
            km_text = f'🚷{Wasteland.raid_locations_by_km[self.km_assigned][1]}<b>{self.km_assigned}км</b>'
        else:
            km_text = f'<b>{self.km_assigned}км</b>' if (self.km_assigned not in Wasteland.raid_kms) \
                else f'{Wasteland.raid_locations_by_km[self.km_assigned][1]}<b>{self.km_assigned}км</b>'
        secret_code = user_id_encode(self.player.telegram_user.user_id)
        text = f'Тебе выдан <b>ПИН</b>\n<b>{text}</b>\nВремя: <b>{self.time}</b>\nПросто {secret_code}иди на {km_text}\n\n' \
               f'<code>{get_status(self.status)}</code>\n\n{make_menu(self.status)}\n'
        return text

    @property
    def __radar_query(self) -> Radar:
        return self.player.radars.order_by(Radar.time.desc())

    @property
    def km_real(self):
        if self.__radar_query:
            return self.__radar_query.get().km

    @property
    def km_real_time(self):
        if self.__radar_query:
            return self.__radar_query.get().time

    @property
    def status(self):
        if self.status_id is not None:
            return RaidStatus(self.status_id)

    @status.setter
    def status(self, value):
        self.status_id = value.value

    @classmethod
    def next_raid_players(cls, status=None, km=None, time=None):
        if not time:
            time = next_raid()
        query = cls.filter(cls.time == time)
        if status is not None:
            query = query.filter(cls.status_id == status)
        if km is not None:
            query = query.filter(cls.km_assigned == km)
        return query

    @classmethod
    def assign(cls, time, player, km, status=RaidStatus.UNKNOWN):
        raid_assigned, created = cls.get_or_create(time=time, player=player)
        if km != raid_assigned.km_assigned:
            raid_assigned.status = status

            raid_assigned.km_assigned = km
            raid_assigned.save()
        return raid_assigned
