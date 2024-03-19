import re
from functools import partial
from typing import Match, List

from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from src.config import settings
from src.core import (
    EventManager,
    MessageManager,
    InnerHandler,
    CommandFilter,
    InnerUpdate,
)
from src.decorators import command_handler, permissions
from src.decorators.permissions import is_admin, is_developer
from src.decorators.users import get_users
from src.models import TelegramUser
from src.modules import BasicModule
from src.utils.functions import CustomInnerFilters, telegram_user_id_decode


class AdminModule(BasicModule):
    """
    Admin commands
    """

    module_name = "admin"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="ban", description="Заблокировать пользователя"),
                partial(self._ban, is_banned=True),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="unban", description="Разблокировать пользователя"),
                partial(self._ban, is_banned=False),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="ban_ls", description="Список заблокированных"),
                self._ban_ls,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="admin_add", description="Добавить администратора"),
                partial(self._admin, become_admin=True),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="admin_remove", description="Удалить администратора"),
                partial(self._admin, become_admin=False),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="admin_ls", description="Список администраторов"),
                self._admin_list,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="crpt", description="Проверить сообщение на подпись"),
                self._crpt,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r"[\s\S]*﻿(?P<secret_code>.+)﻿[\s\S]*"),
        argument_miss_msg='Пришли сообщение в формате "/crpt Текст"',
    )
    def _crpt(self, _: InnerUpdate, match: Match):
        """
        Анализирует текст на предмет двоичного обозначения TelegramUser.user_id в двоичном виде
        Вызывать с любым текстом, где может быть такой "шифр"
        """

        code = match.group("secret_code")
        telegram_user_id = telegram_user_id_decode(code)
        telegram_user = TelegramUser.get_by_user_id(telegram_user_id)
        if telegram_user is None:
            return self.message_manager.send_message(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                text="⚠ Я не могу найти игрока с такой юзеркой. ⚠",
            )

        return self.message_manager.send_message(
            chat_id=settings.GOAT_ADMIN_CHAT_ID,
            text=f"✅ Это сообщение {telegram_user.mention_html()}",
        )

    @permissions(is_admin)
    @get_users(include_reply=True, break_if_no_users=True)
    def _ban(
        self,
        update: InnerUpdate, users: List[TelegramUser],
        is_banned: bool
    ):
        """
        Блокирует/Разблокирует пользователя
        """

        chat_id = update.effective_chat_id
        state_text = f'{"за" if is_banned else "раз"}бан'
        for user in users:
            if user == update.invoker:
                self.message_manager.send_message(chat_id=chat_id, text=f"⚠Ты не можешь {state_text}ить сам себя")
                continue

            user.is_banned = is_banned
            user.save()

            self.message_manager.send_message(chat_id=chat_id, text=f"*@{user.username}* {state_text}ен")

    @permissions(is_developer)
    @get_users(include_reply=True, break_if_no_users=True)
    def _admin(
        self,
        update: InnerUpdate,
        users: List[TelegramUser],
        become_admin: bool
    ):
        """
        Даёт/Забирает полномочия администратора
        """

        state_text = "" if become_admin else "не"
        for user in users:
            user.is_admin = become_admin
            user.save()

            self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f"✅*@{user.username}* теперь {state_text} администратор",
            )

    @permissions(is_admin)
    def _admin_list(self, update: InnerUpdate):
        """
        Показывает список администраторов
        """

        result = [f"<b>Список администраторов</b>:"]
        for user in TelegramUser.filter(TelegramUser.is_admin == True):
            player = user.player.get_or_none()
            if player is None:
                name = user.full_name
            else:
                name = player.nickname

            result.append(mention_html(user.user_id, name))

        text = "\n".join(result)
        self.message_manager.send_message(chat_id=update.effective_chat_id, text=text)

    @permissions(is_admin)
    def _ban_ls(self, update: InnerUpdate):
        """
        Показывает список заблокированных
        """

        result = [f"<b>Список заблокированных</b>:"]
        for user in TelegramUser.filter(TelegramUser.is_banned == True):
            player = user.player.get_or_none()
            if player is None:
                name = user.full_name
            else:
                name = player.nickname

            result.append(mention_html(user.user_id, name))

        text = "\n".join(result)
        self.message_manager.send_message(chat_id=update.effective_chat_id, text=text)
