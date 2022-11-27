import datetime
import math

from telegram import ParseMode
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
from core import CallbackResults
from core import (
    EventManager,
    MessageManager
)
from models import (
    Player,
    RaidAssign,
    Settings
)
from models.raid_assign import RaidStatus
from modules import BasicModule
from utils import (
    last_raid,
    next_raid
)
from ww6StatBotWorld import Wasteland


class NotificationsModule(BasicModule):  # TODO: Переработать, добавить "будильники"

    module_name = 'notifications'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        super().__init__(event_manager, message_manager)

        self.event_manager.scheduler.add_job(self._notification_confirmed, 'cron', day_of_week='mon-sun', hour='1,9,17')
        self.event_manager.scheduler.add_job(self._notification_when_raid_3, 'cron', day_of_week='mon-sun', hour='6,14,22')

        self.event_manager.scheduler.add_job(self._notification_when_raid_tz(kms=[24, 28, 53]), 'cron', day_of_week='mon-sun', hour='0,8,16', minute=57)
        self.event_manager.scheduler.add_job(self._notification_when_raid_tz(kms=[32]), 'cron', day_of_week='mon-sun', hour='0,8,16', minute=48)

    def _error_send(self, cr: CallbackResults):
        e = cr.error
        if not e:
            return
        block_list, obj = cr.args
        if "bot was blocked by the user" in e.message:
            block_list.append(mention_html(obj['chat_id'], obj['nickname']))

    def _blocked_message(self, block_list):
        if block_list:
            block_list = '\n'.join([f'{idx}. {link}' for idx, link in enumerate(block_list, 1)])
            self.message_manager.send_split(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                msg=f'Меня заблокировали эти игроки:\n{block_list}',
                n=30
            )

    def _notification_confirmed(self):
        block_list = []
        users = RaidAssign.select(Player.telegram_user_id.alias('chat_id'), Player.nickname, RaidAssign.time) \
            .join(Player, on=(Player.id == RaidAssign.player_id)) \
            .where((RaidAssign.status_id == RaidAssign.IN_PROCESS) & (RaidAssign.time >= datetime.datetime.now() - datetime.timedelta(hours=8)))

        for user in users:
            self.message_manager.send_message(
                chat_id=user['chat_id'],
                text=f'Отправь мне <b>ПОЛНЫЙ</b> 📟Пип-бой с рейда {user["time"]}',
                parse_mode='HTML',
                callback=self._error_send,
                callback_args=(block_list, user)
            )
        self._blocked_message(block_list)

    def _notification_when_raid_3(self):
        next_raid_time = next_raid()
        last_raid_time = last_raid()
        seconds = math.ceil((next_raid_time - datetime.datetime.now()).total_seconds())

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds %= 60
        text = f'Скоро рейд в *{next_raid_time.hour}:00* мск\n' \
               f'Т.е. через *{hours:.0f}* ч *{minutes:.0f}* мин *{seconds:.0f}* сек'

        users = RaidAssign.select(Player.telegram_user_id.alias('chat_id'), Player.nickname.alias('nickname')) \
            .join(Player, on=(RaidAssign.player_id == Player.id)) \
            .join(Settings, on=(Player.settings_id == Settings.id)) \
            .where(
            RaidAssign.status_id.not_in([RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED])
            & (RaidAssign.is_reported == False)
            & (RaidAssign.time > last_raid_time)
            & (Settings.pings['notify_raid_3'] == 'true')
            ).dicts()
        block_list = []
        for user in users:
            self.message_manager.send_message(
                chat_id=user['chat_id'],
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                callback=self._error_send,
                callback_args=(block_list, user)
            )
        self._blocked_message(block_list)

    def _notification_when_raid_tz_10(self):
        next_raid_time = next_raid()
        last_raid_time = last_raid()
        seconds = math.ceil((next_raid_time - datetime.datetime.now()).total_seconds())

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds %= 60
        text = f'Скоро рейд в *{next_raid_time.hour}:00* мск\n' \
               f'Т.е. через *{hours:.0f}* ч *{minutes:.0f}* мин *{seconds:.0f}* сек'

        users = RaidAssign.select(Player.telegram_user_id.alias('chat_id'), Player.nickname) \
            .join(Player, on=(RaidAssign.player_id == Player.id)) \
            .join(Settings, on=(Player.settings_id == Settings.id)) \
            .where(
            RaidAssign.status_id.not_in([RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED])
            & (RaidAssign.is_reported == False)
            & (RaidAssign.time > last_raid_time)
            & (Settings.pings['notify_raid_tz_10'] == 'true')
            & (RaidAssign.km_assigned << Wasteland.raid_kms_tz)
            ).dicts()
        block_list = []
        for user in users:
            self.message_manager.send_message(
                chat_id=user['chat_id'],
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                callback=self._error_send,
                callback_args=(block_list, user)
            )
        self._blocked_message(block_list)

    def _notification_when_raid_tz(self, kms: list):
        def wrapper():
            last_raid_time = last_raid()
            text = '<b>Время выхода на рейд в ТЗ!</b>'
            users = RaidAssign.select(Player.telegram_user_id.alias('chat_id'), Player.nickname) \
                .join(Player, on=(RaidAssign.player_id == Player.id)) \
                .join(Settings, on=(Player.settings_id == Settings.id)) \
                .where(
                RaidAssign.status_id.not_in([RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED])
                & (RaidAssign.is_reported == False)
                & (RaidAssign.time > last_raid_time)
                & (Settings.pings['notify_raid_tz'] == 'true')
                & (RaidAssign.km_assigned << kms)
                ).dicts()
            block_list = []
            for user in users:
                self.message_manager.send_message(
                    chat_id=user['chat_id'],
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    callback=self._error_send,
                    callback_args=(block_list, user)
                )
            self._blocked_message(block_list)

        return wrapper
