import html
import re
from typing import Match, List

from telegram.ext import Dispatcher

from src.core import (
    EventManager,
    MessageManager,
    InnerHandler,
    CommandFilter,
    InnerUpdate,
)
from src.decorators import command_handler, permissions
from src.decorators.permissions import is_admin
from src.decorators.users import get_users
from src.models import TelegramChat, Group, TelegramUser
from src.modules import BasicModule
from src.utils.functions import CustomInnerFilters


class ActivatedModule(BasicModule):
    """
    message sending
    """

    module_name = "activated"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="active_c", description="Активировать чат"),
                self._active_chat,
                [CustomInnerFilters.from_admin_chat_or_private],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="active_u", description="Активировать пользователя"),
                self._active_user,
                [CustomInnerFilters.from_admin_chat_or_private],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="active_g", description="Активировать группу"),
                self._active_group,
                [CustomInnerFilters.from_admin_chat_or_private],
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r"(?P<group_name>.*)"),
        argument_miss_msg='Пришли сообщение в формате "/active_g Имя группы"',
    )
    def _active_group(self, update: InnerUpdate, match: Match):
        """
        Вызывается с аргументом Алиаса группы
        Меняет поле Group.is_active на противоположное значение
        """

        group_name = match.group("group_name")
        group = Group.get_by_name(group_name)
        if group is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'Группы "{html.escape(group_name)}" не существует!',
            )

        new_group_status = not group.is_active
        group.is_active = new_group_status
        group.save()

        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Группа "{group_name}" {"активирована" if new_group_status else "деактивированна"}',
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r"(?P<alias>\w+)(\s+-\s+)?(?P<chat_id>.+)?"),
        argument_miss_msg='Пришли сообщение в формате "/active_c Алиас |- chat_id"',
    )
    def _active_chat(self, update: InnerUpdate, match: Match):
        """
        Вызывается с аргументом Алиаса группы и id чата для активации или просто в нужный чат
        Пример в лс боту: /active Test 10000
        Пример в нужный чат: /active Test
        Меняет поле TelegramChat.is_active на противоположное значение и присваивает TelegramChat.alias знаечение алиаса
        """

        alias = match.group("alias")
        chat_id = match.group("chat_id") or update.effective_chat_id
        chat = TelegramChat.get_or_none(TelegramChat.chat_id == int(chat_id))
        if chat is None or chat.chat_type == "private":
            self.message_manager.send_message(chat_id=update.effective_chat_id, text=f"Чата с id: {chat_id} не найден")
            return

        new_chat_status = not chat.is_active
        chat.is_active = new_chat_status
        chat.shortname = alias
        chat.save()

        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f"Чат с id: {chat_id} {'активирован' if new_chat_status else 'деактивирован'}",
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/active_u @user1 @user2"')
    @get_users(include_reply=True, break_if_no_users=True)
    def _active_user(self, update: InnerUpdate, users: List[TelegramUser]):
        """
        Вызывается с аргументом @user1 @user2
        /active_u @user1
        Меняет значение Player.is_active на противоположное значение
        """

        actives: List[str] = []
        deactives: List[str] = []

        for user in users:
            new_player_status = not user.is_active
            user.is_active = new_player_status
            user.save()

            if new_player_status:
                actives.append(user.mention_html())
            else:
                deactives.append(user.mention_html())

        if actives:
            self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f"Пользователи: {'; '.join(actives)} - активированны",
            )

        if deactives:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f"Пользователи: {'; '.join(deactives)} - деактивированны",
            )
