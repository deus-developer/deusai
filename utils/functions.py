import datetime
import functools
import hashlib
import math

import telegram
from telegram.ext import BaseFilter

from config import settings
from core import Update
from ww6StatBotWorld import Wasteland


def sha1(value):
    sha1 = hashlib.sha1()
    sha1.update(str(value).encode())
    return sha1.hexdigest()


def dict_serialize(obj=None):
    import models

    if not obj:
        return

    if isinstance(obj, datetime.datetime):
        return obj.timestamp()
    elif isinstance(obj, datetime.timedelta):
        return obj.total_seconds()
    elif isinstance(obj, telegram.Update):
        return obj.to_dict()
    elif isinstance(obj, models.TelegramUser):
        return obj.user_id
    elif isinstance(obj, models.Player):
        return obj.id
    elif isinstance(obj, models.TelegramChat):
        return obj.chat_id
    elif isinstance(obj, list):
        return [dict_serialize(x) for x in obj]
    elif isinstance(obj, dict):
        return {key: dict_serialize(value) for key, value in obj.items()}

    else:
        return None


def round_b(n):
    import math
    if n - math.floor(n) < 0.5:
        return math.floor(n)
    return math.ceil(n)


def clearEmoji(s):
    return s


@functools.lru_cache()
def price_upgrade(start: int = 1, end: int = 10, oratory: int = 0, is_oratory: bool = False):
    discount = 0 if is_oratory else 3 * oratory
    stat_price = 10 if is_oratory else 13

    return (end - start) * ((start + end - 1) * 0.5 * stat_price - discount)


@functools.lru_cache()
def walk_time(distance, stamina):
    walk_time = 120 + (25 if distance < 2 else 20)
    regen_time = 30 * 60
    rest = distance % stamina
    cycles = max(math.floor(distance / stamina) - (1 if rest == 0 else 0), 0)
    cycle_regen_time = max(regen_time - (stamina * walk_time), 0)
    total_regen_time = cycle_regen_time * cycles

    return math.ceil(math.ceil(distance * walk_time) + total_regen_time)


@functools.lru_cache()
def _loose_image(weeks: int, raids: int = 0):
    week = '✳'
    if weeks == 1:
        week = '✳'
    elif weeks == 2:
        week = '✡'
    elif weeks > 2:
        week = '✴'
    else:
        week = ''

    return f'{week} {{}} [{raids}p]'


def _sex_image(sex: int):
    if sex == 0:
        return '👱‍♂️'
    if sex == 1:
        return '👱🏻‍♀'
    else:
        return '👤'


def _ping_image(level: int):
    if level == 0:
        return '🔊'
    elif level == 1:
        return '🕪'
    elif level == 2:
        return '🕩'
    else:
        return '🕨'


def get_link(player, username=False):
    raise Exception(f'get_link usaged: Player={player}; Username={username}')
    if not player:
        return '[Неизвестный]'
    if not player.telegram_user:
        return player.nickname

    return f'<a href="tg://user?id={player.telegram_user.chat_id}">' \
           f'{player.telegram_user.full_name if username else player.nickname}' \
           f'</a>'


def get_ref(user: telegram.User):
    if user.username:
        return f'@{user.username}'
    else:
        return f'#{user.id}'


@functools.lru_cache()
def user_id_encode(user_id: int):
    s = ''
    while user_id > 0:
        s += '⁠' if user_id % 2 == 1 else '‍'
        user_id //= 2
    return f'﻿{s}﻿'


def user_id_decode(ss: str):
    user_id = 0
    arr = [True if s == '⁠' else False for s in ss]
    for i in range(len(arr)):
        user_id += (2 ** i) * arr[i]
    return user_id


def next_raid(date=None):
    date = date or datetime.datetime.now()
    now = date
    h = 8 - (now.hour - 1) % 8
    return now + datetime.timedelta(hours=h) - datetime.timedelta(
        minutes=now.minute, seconds=now.second,
        microseconds=now.microsecond
    )


def last_raid(date=None):
    date = date or datetime.datetime.now()
    now = date - datetime.timedelta(seconds=5)
    h = (now.hour - 1) % 8
    return now - datetime.timedelta(hours=h) - datetime.timedelta(
        minutes=now.minute, seconds=now.second,
        microseconds=now.microsecond
    )


class CustomFilters(object):
    class WWForwarded(BaseFilter):

        def filter(self, message):
            return message.forward_from and message.forward_from.id == Wasteland.chat_id

    class GreatWar(BaseFilter):

        def filter(self, message):
            return message.chat and message.chat.id == Wasteland.greatwar_chat_id

    class TolylyForwarded(BaseFilter):

        def filter(self, message):
            return message.forward_from_chat and message.forward_from_chat.id == Wasteland.tolyly_chat_id

    class Private(BaseFilter):

        def filter(self, message):
            return message.chat.type == 'private'

    ww_forwarded = WWForwarded()
    tolyly_forwarded = TolylyForwarded()
    greatwar = GreatWar()
    private = Private()


class CustomInnerFilters(object):

    @staticmethod
    def private(update: Update):
        """updates from private chats only"""
        return update.telegram_update and update.telegram_update.message and update.telegram_update.message.chat.type == 'private'

    @staticmethod
    def chat(update: Update):
        """updates from group chats only"""
        return update.telegram_update and update.telegram_update.message and 'group' in update.telegram_update.message.chat.type

    @staticmethod
    def from_player(update: Update):
        """ignores updates from banned or not existing players"""
        return update.player and not update.invoker.is_banned and update.player.is_active

    @staticmethod
    def from_active_chat(update: Update):
        """ ignores updates from not active chats """
        return not update.chat or update.chat.is_active

    @staticmethod
    def from_admin_goat_chat(update: Update):
        return update.telegram_update and update.telegram_update.message.chat_id == settings.GOAT_ADMIN_CHAT_ID

    @staticmethod
    def from_admin_chat_or_private(update: Update):
        return CustomInnerFilters.private(update) or CustomInnerFilters.from_admin_goat_chat(update)
