import datetime
from typing import List

from telegram.ext import Dispatcher

from src.core import EventManager, MessageManager
from src.models import RaidAssign, Player, Settings, TelegramUser
from src.models.raid_assign import RaidStatus
from src.modules import BasicModule
from src.utils import get_last_raid_date, get_when_raid_text
from src.wasteland_wars import constants


class NotificationsModule(BasicModule):
    module_name = "notifications"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        super().__init__(event_manager, message_manager, dispatcher)

        self.event_manager.scheduler.add_job(self._notification_when_raid_3, "cron", day_of_week="mon-sun", hour="6,22")

        self.event_manager.scheduler.add_job(
            self._notification_when_raid_tz(
                kms=[
                    24,
                ]
            ),
            "cron",
            day_of_week="mon-sun",
            hour="0,8",
            minute=57,
        )  # Выход с 23 км на 24 км

        self.event_manager.scheduler.add_job(
            self._notification_when_raid_tz(
                kms=[
                    32,
                ]
            ),
            "cron",
            day_of_week="mon-sun",
            hour="0,8",
            minute=47,
        )  # Выход с 27 км на 32 км

        self.event_manager.scheduler.add_job(
            self._notification_pipboy_update, "cron", day_of_week="mon-sun", hour="12"
        )  # Обновление пип-боев

    def _notification_pipboy_update(self):
        pipboy_expire_date = datetime.datetime.now() - datetime.timedelta(days=7)

        query = Player.select(Player.telegram_user_id).where(
            (Player.is_active == True) & (Player.last_update <= pipboy_expire_date)
        )

        text = (
            "Привет, пришло время обновить <b>полный</b> 📟Пип-бой.\n"
            "1. Зайди в @WastelandWarsBot, напиши /me\n"
            "2. Отправь результат мне (@deusai_bot)\n\n"
            "Хорошего тебе дня!"
        )

        for row in query:
            self.message_manager.send_message(chat_id=row["telegram_user_id"], text=text)

    def _notification_when_raid_3(self):
        last_raid_time = get_last_raid_date()

        users = (
            RaidAssign.select(
                Player.telegram_user_id.alias("chat_id"),
                Player.nickname.alias("nickname"),
            )
            .join(Player, on=(RaidAssign.player_id == Player.id))
            .join(Settings, on=(Player.settings_id == Settings.id))
            .where(
                RaidAssign.status_id.not_in([RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED])
                & (RaidAssign.is_reported == False)
                & (RaidAssign.time > last_raid_time)
                & (Settings.pings["notify_raid_3"] == "true")
            )
        ).dicts()

        text = get_when_raid_text()

        for user in users:
            self.message_manager.send_message(chat_id=user["chat_id"], text=text)

    def _notification_when_raid_tz_10(self):
        last_raid_time = get_last_raid_date()

        users = (
            RaidAssign.select(
                Player.telegram_user_id.alias("chat_id"),
                Player.nickname.alias("nickname"),
            )
            .join(Player, on=(RaidAssign.player_id == Player.id))
            .join(Settings, on=(Player.settings_id == Settings.id))
            .where(
                RaidAssign.status_id.not_in([RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED])
                & (RaidAssign.is_reported == False)
                & (RaidAssign.time > last_raid_time)
                & (Settings.pings["notify_raid_tz_10"] == "true")
                & (RaidAssign.km_assigned << constants.raid_kms_tz)
            )
        ).dicts()

        text = get_when_raid_text()

        for user in users:
            self.message_manager.send_message(chat_id=user["chat_id"], text=text)

    def _notification_when_raid_tz(self, kms: List[int]):
        def wrapper():
            last_raid_time = get_last_raid_date()
            text = "<b>Время выхода на рейд в ТЗ!</b>"

            users = (
                RaidAssign.select(
                    Player.telegram_user_id.alias("chat_id"),
                    Player.nickname.alias("nickname"),
                )
                .join(Player, on=(RaidAssign.player_id == Player.id))
                .join(Settings, on=(Player.settings_id == Settings.id))
                .where(
                    RaidAssign.status_id.not_in([RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED])
                    & (RaidAssign.is_reported == False)
                    & (RaidAssign.time > last_raid_time)
                    & (Settings.pings["notify_raid_tz"] == "true")
                    & (RaidAssign.km_assigned << kms)
                )
            ).dicts()

            for user in users:
                self.message_manager.send_message(chat_id=user["chat_id"], text=text, is_queued=False)

        return wrapper
