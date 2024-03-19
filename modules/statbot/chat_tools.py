import datetime
import functools
import re
from typing import List

from telegram import Message, Poll, PollOption
from telegram.ext import Dispatcher

from core import EventManager, MessageManager, InnerHandler as InnerHandler, CommandFilter, InnerUpdate
from decorators import permissions
from decorators.permissions import is_admin
from decorators.users import get_users
from models import TelegramUser
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
                CommandFilter('mute'),
                self._mute(True),
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('unmute'),
                self._mute(False),
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('kick'),
                self._kick,
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('id'),
                self._chat_id,
                [CustomInnerFilters.chat, CustomInnerFilters.from_active_chat]
            )
        )

        self._re_time = re.compile(r'((?P<days>\d+)d)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?((?P<hours>\d+)h)?')
        super().__init__(event_manager, message_manager, dispatcher)

    def _chat_id(self, update: InnerUpdate):
        if update.effective_chat_id is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text='🆔 not found'
            )

        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'🆔 {update.effective_chat_id}'
        )

    def get_timedelta_from_command_argument(self, argument: str) -> datetime.timedelta:
        result = datetime.timedelta(0)

        for item in self._re_time.finditer(argument):
            days, hours, minutes, seconds = (
                0 if value is None else int(value)
                for value in item.group('days', 'hours', 'minutes', 'seconds')
            )
            result += datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

        return result

    @permissions(is_admin)
    @get_users(include_reply=True, break_if_no_users=True)
    def _kick(self, update: InnerUpdate, users: List[TelegramUser]):
        until_date = datetime.datetime.now() + self.get_timedelta_from_command_argument(update.command.argument)

        for user in users:
            try:
                self.message_manager.bot.kick_chat_member(
                    chat_id=update.effective_chat_id,
                    user_id=user.user_id,
                    until_date=until_date.timestamp()
                )
            except (Exception,):
                self.message_manager.send_message(
                    chat_id=update.effective_chat_id,
                    text=f'Не могу выгнать {user.get_link()}'
                )
            else:
                self.message_manager.send_message(
                    chat_id=update.effective_chat_id,
                    text=f'Дал пинка {user.get_link()} и выкинул на мороз.'
                )

    def _mute(self, become_mute: bool):
        """
        Даёт/Забирает мут в чате по юзеркам
        """

        @permissions(is_admin)
        @get_users(include_reply=True, break_if_no_users=True)
        def handler(self, update: InnerUpdate, users: List[TelegramUser]):
            chat_id = update.effective_chat_id
            state_text = "Выдал" if become_mute else "Снял"

            chat = self.message_manager.bot.get_chat(chat_id=chat_id)
            chat_permissions = chat.permissions
            for key, value in chat_permissions.to_dict().items():
                setattr(chat_permissions, key, False if become_mute else value)

            until_date = datetime.datetime.now()
            if become_mute:
                until_date += self.get_timedelta_from_command_argument(update.command.argument)

            for user in users:
                try:
                    self.message_manager.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user.user_id,
                        until_date=until_date.timestamp(),
                        permissions=chat_permissions
                    )
                except (Exception,):
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        text=f'Не смог изменить права для {user.get_link()}'
                    )
                    continue

                if become_mute:
                    text = f'{state_text} мут {user.get_link()} до <code>{until_date}</code>'
                else:
                    text = f'{state_text} мут {user.get_link()}'

                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=text
                )

        handler.__doc__ = f'{become_mute and "выда" or "снят"}ть мут с игрока'
        return functools.partial(handler, self)
