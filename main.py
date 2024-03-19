import logging
from types import FrameType
from typing import Type, List

from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import Updater

import modules.common as common_modules
import modules.statbot as statbot_modules
from config import settings
from core import EventManager, MessageManager
from modules import BasicModule

# logger = logging.getLogger('peewee')
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)


class StatBot:
    """StatBot runner"""

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

        modules: List[Type[BasicModule]] = [
            common_modules.ActivityModule,
            common_modules.CommandModule,  # Активити + Обработка команд

            statbot_modules.StatModule,
            statbot_modules.ParserModule,
            statbot_modules.TriggersModule,
            # Работа с текстовыми соо
            statbot_modules.ShopModule,

            # Частые хуки на парсинг
            statbot_modules.GroupModule,
            statbot_modules.KarmaModule,
            statbot_modules.RaidModule,
            statbot_modules.FractionModule,
            statbot_modules.PigsModule,

            # Остальные (Обработка команд)
            statbot_modules.StartModule,
            statbot_modules.RatingModule,
            statbot_modules.AdminRatingModule,
            statbot_modules.EchoModule,
            statbot_modules.AdminModule,
            statbot_modules.ActivatedModule,
            statbot_modules.NotificationsModule,
            statbot_modules.SettingsModule,
            statbot_modules.DeveloperToolsModule,
            statbot_modules.ChatToolsModule,
        ]

        self.modules: List[BasicModule] = []
        for Module in modules:
            instance = Module(self.event_manager, self.message_manager, self.updater.dispatcher)

            self.modules.append(instance)
            self.logger.info(f'Set up module "{str(instance)}"')

    def start(self):
        """Start Statbot"""
        for instance in self.modules:
            instance.startup()

        self.scheduler.start()

        self.logger.info('%s started', self.updater.bot.name)
        self.message_manager.send_message(chat_id=settings.ADMIN_CHAT_ID, text='Restarted')

        self.updater.start_polling(clean=True)
        self.updater.idle()

    def stop(self, _: int = None, __: FrameType = None):
        """Stop Statbot"""
        for instance in self.modules:
            instance.shutdown()

        self.updater.stop()
        self.scheduler.shutdown()

    def run(self):
        self.start()
        self.updater.idle()


def main():
    statbot = StatBot()
    statbot.start()


if __name__ == '__main__':
    main()
