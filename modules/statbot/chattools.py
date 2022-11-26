import functools
import re
import datetime
import time
from telegram import ParseMode
from telegram.ext import Dispatcher
from core import EventManager, MessageManager, Handler as InnerHandler, CommandFilter, Update
from decorators import command_handler, permissions
from decorators.permissions import is_admin, is_developer
from decorators.users import get_players, get_users
from models import TelegramUser, Player, KarmaTransition
from modules import BasicModule
from utils import get_link
from utils.functions import CustomInnerFilters, user_id_encode, user_id_decode
from config import settings
from modules.statbot.karma import Karma
from sentry_sdk import capture_message

class ChatToolsModule(BasicModule):
    """
    Admin commands
    """
    module_name = 'chat_tools'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('mute'), self._mute(True),
                                            [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('unmute'), self._mute(False),
                                            [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))

        self.add_inner_handler(InnerHandler(CommandFilter('kick'), self._kick,
                                            [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))
        # self.add_inner_handler(InnerHandler(CommandFilter('mute_ls'), self._mute_ls,
        #                                     [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))
        # self.add_inner_handler(InnerHandler(CommandFilter('warn'), self._warn(True),
        #                                     [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))
        # self.add_inner_handler(InnerHandler(CommandFilter('unwarn'), self._unwarn(False),
        #                                     [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))
        # self.add_inner_handler(InnerHandler(CommandFilter('banhammer'), self._banhammer,
        #                                     [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]))
        self._re_time = re.compile(r'((?P<days>\d+)d)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?((?P<hours>\d+)h)?')
        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @get_users(include_reply=True, break_if_no_users=True)
    def _kick(self, update: Update, users, *args, **kwargs):
        chat_id = update.telegram_update.message.chat_id
        time = datetime.datetime.now()
        for item in self._re_time.finditer(update.command.argument):
            days, hours, minutes, seconds = [int(x) if x else 0 for x in item.group('days', 'hours', 'minutes', 'seconds')]
            time += datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
            
        for user in users:
            try:
                self.message_manager.bot.kick_chat_member(chat_id=chat_id, user_id=user.user_id, until_date=time.timestamp())
            except Exception as e:
                update.telegram_update.message.reply_text(f'Не могу выгнать {user.get_link()}')
            else:
                update.telegram_update.message.reply_text(f'Дал пинка {user.get_link()} и выкинул на мороз.')

    def _mute(self, become_mute):
        """
        Даёт/Забирает мут в чате по юзеркам
        """
        @permissions(is_admin)
        @get_users(include_reply=True, break_if_no_users=True)
        def handler(self, update: Update, users, *args, **kwargs):
            chat_id = update.telegram_update.message.chat_id
            state_text = "Выдал" if become_mute else "Снял"

            chat = self.message_manager.bot.get_chat(chat_id=chat_id)

            permissions = chat.permissions
            time = datetime.datetime.now()
            if become_mute:
                for item in self._re_time.finditer(update.command.argument):
                    days, hours, minutes, seconds = [int(x) if x else 0 for x in item.group('days', 'hours', 'minutes', 'seconds')]
                    time += datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

            for key, value in permissions.to_dict().items():
                setattr(permissions, key, False if become_mute else value)


            for user in users:
                try:
                    t = self.message_manager.bot.restrict_chat_member(  chat_id = chat_id,
                                                                        user_id = user.user_id,
                                                                        until_date = time.timestamp(),
                                                                        permissions = permissions)
                except Exception as e:
                    update.telegram_update.message.reply_text(  text=f'Не смог изменить права для {user.get_link()}',
                                                                parse_mode=ParseMode.HTML)
                    continue
                if become_mute:
                    update.telegram_update.message.reply_text(  text=f'{state_text} мут {user.get_link()} до <code>{time}</code>',
                                                                parse_mode=ParseMode.HTML)
                else:
                    update.telegram_update.message.reply_text(  text=f'{state_text} мут {user.get_link()}',
                                                                parse_mode=ParseMode.HTML)

        handler.__doc__ = f'{become_mute and "выда" or "снят"}ть мут с игрока'
        return functools.partial(handler, self)