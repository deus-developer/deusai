import datetime
import math
from typing import Optional

from telegram.ext import BaseFilter

from src.config import settings
from src.core import InnerUpdate
from src.wasteland_wars import constants


def banking_round(value: float) -> int:
    if value - math.floor(value) < 0.5:
        return math.floor(value)
    return math.ceil(value)


def price_upgrade(start: int = 1, end: int = 10, oratory: int = 0, is_oratory: bool = False) -> int:
    discount = 0 if is_oratory else 3 * oratory
    stat_price = 10 if is_oratory else 13

    return (end - start) * ((start + end - 1) // 2 * stat_price - discount)


def get_loose_image(weeks: int, raids: int = 0) -> str:
    if weeks == 1:
        week = "✳"
    elif weeks == 2:
        week = "✡"
    elif weeks > 2:
        week = "✴"
    else:
        week = ""
    return week + "{}" + f"[{raids}р]"


def get_sex_image(sex: int) -> str:
    if sex == 0:
        return "👱‍♂️"
    if sex == 1:
        return "👱🏻‍♀"
    else:
        return "👤"


def telegram_user_id_encode(user_id: int) -> str:
    s = ""
    while user_id > 0:
        s += "⁠" if user_id % 2 else "‍"
        user_id //= 2
    return f"﻿{s}﻿"


def telegram_user_id_decode(string: str) -> int:
    user_id = 0

    for index, char in enumerate(string):
        if char == "⁠":
            user_id += 2**index

    return user_id


def _get_next_raid_date(date: datetime.datetime) -> datetime.datetime:
    h = 8 - (date.hour - 1) % 8

    return (
        date
        + datetime.timedelta(hours=h)
        - datetime.timedelta(minutes=date.minute, seconds=date.second, microseconds=date.microsecond)
    )


def get_next_raid_date(date: Optional[datetime.datetime] = None) -> datetime.datetime:
    date = _get_next_raid_date(date or datetime.datetime.now())
    if date.hour == 17:
        return date + datetime.timedelta(hours=8)
    return date


def _get_last_raid_date(date: datetime.datetime) -> datetime.datetime:
    next_raid_date = _get_next_raid_date(date)
    last_raid_date = next_raid_date - datetime.timedelta(hours=8)

    return last_raid_date


def get_last_raid_date(date: Optional[datetime.datetime] = None) -> datetime.datetime:
    date = _get_last_raid_date(date or datetime.datetime.now())
    if date.hour == 17:
        return date - datetime.timedelta(hours=8)
    return date


class CustomFilters:
    class WWForwarded(BaseFilter):
        def filter(self, message):
            return message.forward_from and message.forward_from.id == constants.chat_id

    class Private(BaseFilter):
        def filter(self, message):
            return message.chat and message.chat.type == "private"

    ww_forwarded = WWForwarded()
    private = Private()


class CustomInnerFilters:
    @staticmethod
    def private(update: InnerUpdate) -> bool:
        """updates from private chats only"""
        return (
            update.telegram_update
            and update.telegram_update.message
            and update.telegram_update.message.chat.type == "private"
        )

    @staticmethod
    def chat(update: InnerUpdate) -> bool:
        """updates from group chats only"""
        return (
            update.telegram_update
            and update.telegram_update.message
            and update.telegram_update.message.chat.type in ("group", "supergroup")
        )

    @staticmethod
    def from_player(update: InnerUpdate) -> bool:
        """ignores updates from banned or not existing players"""
        return update.invoker and not update.invoker.is_banned and update.player and update.player.is_active

    @staticmethod
    def from_active_chat(update: InnerUpdate) -> bool:
        """ignores updates from not active chats"""
        return not update.chat or update.chat.is_active

    @staticmethod
    def from_admin_goat_chat(update: InnerUpdate) -> bool:
        return (
            update.telegram_update
            and update.telegram_update.message
            and update.effective_chat_id == settings.GOAT_ADMIN_CHAT_ID
        )

    @classmethod
    def from_admin_chat_or_private(cls, update: InnerUpdate) -> bool:
        return cls.private(update) or cls.from_admin_goat_chat(update)
