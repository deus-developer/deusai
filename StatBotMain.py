import logging
from types import FrameType

from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import Updater

import modules.common as common_modules
import modules.statbot as statbot_modules
from config import settings
from core import (
    EventManager,
    MessageManager
)
from models import TelegramUser


class StatBot:
    """StatBot runner"""

    def _promote_developer(self):
        """promotes main developer to admin status)))"""
        query = TelegramUser.update(
            {
                TelegramUser.is_admin: True
            }
        ).where(
            TelegramUser.user_id == settings.ADMIN_CHAT_ID
        )
        query.execute()

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # initializing Updater
        self.updater = Updater(
            token=settings.TG_TOKEN,
            user_sig_handler=self.stop
        )

        self.scheduler = BackgroundScheduler()
        self.event_manager = EventManager(self.scheduler)
        self.message_manager = MessageManager(self.updater.bot, self.scheduler)

        modules = [
            common_modules.ActivityModule,
            common_modules.CommandModule,  # Активити + Обработка команд

            statbot_modules.StatModule, statbot_modules.BossModule,
            statbot_modules.ParserModule, statbot_modules.RaidResultModule,

            statbot_modules.TriggersModule,  # Работа с текстовыми соо
            statbot_modules.TakingModule,

            statbot_modules.VoteModule,  # Inlines
            # Частые хуки на парсинг
            statbot_modules.GroupModule,
            statbot_modules.RadarModule,
            statbot_modules.KarmaModule,
            statbot_modules.RaidModule,
            statbot_modules.NotebookModule, statbot_modules.PVPModule,

            # Остальные (Обработка команд)
            statbot_modules.FeedbackModule,
            statbot_modules.StartModule, statbot_modules.RatingModule, statbot_modules.AdminRatingModule,
            statbot_modules.EchoModule, statbot_modules.AdminModule, statbot_modules.ActivatedModule,
            statbot_modules.StatisticsModule, statbot_modules.FreezeModule,
            statbot_modules.NotificationsModule, statbot_modules.RankModule, statbot_modules.SettingsModule,
            statbot_modules.DeveloperToolsModule, statbot_modules.ChatToolsModule, statbot_modules.InventoryModule,
        ]

        self.modules = []
        for Module in modules:
            self.modules.append(Module(self.event_manager, self.message_manager, self.updater.dispatcher))
            self.logger.info(f'set up module "{str(self.modules[-1])}"')

        self._promote_developer()

    def start(self):
        """Start Statbot"""
        self.scheduler.start()
        self.logger.debug(f'{self.updater.bot.name} started')
        self.message_manager.send_message(
            chat_id=settings.ADMIN_CHAT_ID,
            text='Restarted'
        )
        self.updater.start_polling(clean=True)
        self.updater.idle()

    def stop(self, signum: int = None, frame: FrameType = None):
        """Stop Statbot"""
        self.updater.stop()
        self.scheduler.shutdown()


if __name__ == '__main__':
    StatBot().start()
