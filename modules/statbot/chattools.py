import datetime
import functools
import re

from telegram import ParseMode
from telegram.ext import Dispatcher

from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import permissions
from decorators.permissions import is_admin
from decorators.users import get_users
from modules import BasicModule
from utils.functions import CustomInnerFilters


class ChatToolsModule(BasicModule):
    """
    Admin commands
    """
    module_name = 'chat_tools'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('mute'), self._mute(True),
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('unmute'), self._mute(False),
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('kick'), self._kick,
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )
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
            except (Exception,):
                update.telegram_update.message.reply_text(f'???? ???????? ?????????????? {user.get_link()}')
            else:
                update.telegram_update.message.reply_text(f'?????? ?????????? {user.get_link()} ?? ?????????????? ???? ??????????.')

    def _mute(self, become_mute):
        """
        ????????/???????????????? ?????? ?? ???????? ???? ??????????????
        """

        @permissions(is_admin)
        @get_users(include_reply=True, break_if_no_users=True)
        def handler(self, update: Update, users, *args, **kwargs):
            chat_id = update.telegram_update.message.chat_id
            state_text = "??????????" if become_mute else "????????"

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
                    t = self.message_manager.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user.user_id,
                        until_date=time.timestamp(),
                        permissions=permissions
                    )
                except (Exception,):
                    update.telegram_update.message.reply_text(
                        text=f'???? ???????? ???????????????? ?????????? ?????? {user.get_link()}',
                        parse_mode=ParseMode.HTML
                    )
                    continue
                if become_mute:
                    update.telegram_update.message.reply_text(
                        text=f'{state_text} ?????? {user.get_link()} ???? <code>{time}</code>',
                        parse_mode=ParseMode.HTML
                    )
                else:
                    update.telegram_update.message.reply_text(
                        text=f'{state_text} ?????? {user.get_link()}',
                        parse_mode=ParseMode.HTML
                    )

        handler.__doc__ = f'{become_mute and "????????" or "????????"}???? ?????? ?? ????????????'
        return functools.partial(handler, self)
