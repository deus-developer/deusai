import functools
import re
from typing import Match, List

from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
from core import EventManager, MessageManager, InnerHandler, CommandFilter, InnerUpdate
from decorators import command_handler, permissions
from decorators.permissions import is_admin, is_developer
from decorators.users import get_players
from models import TelegramUser, Player
from modules import BasicModule
from utils.functions import CustomInnerFilters, telegram_user_id_decode


class AdminModule(BasicModule):
    """
    Admin commands
    """
    module_name = 'admin'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='ban', description='Забанить игрока'),
                self._ban(True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='unban', description='Разбанить игрока'),
                self._ban(False),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='ban_ls', description='Список забанненых'),
                self._ban_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('admin_add'),
                self._admin(True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('admin_remove'),
                self._admin(False),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('admin_ls'),
                self._admin_list,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='crpt', description='Проверить сообщение на подпись'),
                self._crpt,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'[\s\S]*﻿(?P<secret_code>.+)﻿[\s\S]*'),
        argument_miss_msg='Пришли сообщение в формате "/crpt Текст"'
    )
    def _crpt(self, _: InnerUpdate, match: Match):
        """
        Анализирует текст на предмет двоичного обозначения TelegramUser.user_id в двоичном виде
        Вызывать с любым текстом, где может быть такой "шифр"
        """

        code = match.group('secret_code')
        telegram_user_id = telegram_user_id_decode(code)
        telegram_user = TelegramUser.get_by_user_id(telegram_user_id)
        if telegram_user is None:
            return self.message_manager.send_message(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                text='⚠Слушааай. Я не могу найти игрока с такой юзеркой.⚠'
            )

        return self.message_manager.send_message(
            chat_id=settings.GOAT_ADMIN_CHAT_ID,
            text=f'✅Это сообщение {telegram_user.mention_html()},\n если он его слил, то устраивай пенетрацию 🍆'
        )

    def _ban(self, is_banned: bool):
        """
        Банит/Разбанивает игрока по юзерке
        """

        @permissions(is_admin)
        @get_players(include_reply=True, break_if_no_players=True)
        def handler(self, update: InnerUpdate, players: List[Player]):
            chat_id = update.effective_chat_id
            state_text = f'{"за" if is_banned else "раз"}бан'
            for player in players:
                user = player.telegram_user
                if user == update.invoker:
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        text=f'⚠Ты не можешь {state_text}ить сам себя'
                    )
                    continue

                user.is_banned = is_banned
                user.save()

                if is_banned:
                    player.ban_player()
                else:
                    player.unban_player()

                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'*@{user.username}* {state_text}ен'
                )

        handler.__doc__ = f'{is_banned and "За" or "Раз"}банить игрока'
        return functools.partial(handler, self)

    def _admin(self, become_admin: bool):
        """
        Даёт/Забирает полномочия администратора по юзеркам
        """

        @permissions(is_developer)
        @get_players(include_reply=True, break_if_no_players=True)
        def handler(self, update: InnerUpdate, players: List[Player]):
            state_text = "" if become_admin else "не"
            for player in players:
                user = player.telegram_user
                user.is_admin = become_admin
                user.save()

                self.message_manager.send_message(
                    chat_id=update.effective_chat_id,
                    text=f'✅*@{user.username}* теперь {state_text} админ'
                )

        handler.__doc__ = f'{become_admin and "За" or "Раз"}админить игрока'
        return functools.partial(handler, self)

    @permissions(is_admin)
    def _admin_list(self, update: InnerUpdate):
        """
        Показывает список администраторов
        """
        result = [f'<b>Список админов</b>:']
        for user in TelegramUser.filter(TelegramUser.is_admin == True):
            if not user.player:
                continue

            if user.player.exists():
                player = user.player.get()
                name = player.nickname
            else:
                name = f'{user.first_name} {user.last_name}'

            result.append(mention_html(user.user_id, name))

        text = '\n'.join(result)
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @permissions(is_admin)
    def _ban_ls(self, update: InnerUpdate):
        """
        Показывает список банов
        """
        result = [f'<b>Список банов</b>:']
        for user in TelegramUser.filter(TelegramUser.is_banned == True):
            if not user.player:
                continue

            if user.player.exists():
                player = user.player.get()
                name = player.nickname
            else:
                name = f'{user.first_name} {user.last_name}'

            result.append(mention_html(user.user_id, name))

        text = '\n'.join(result)
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )
