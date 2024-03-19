import html
import re
from typing import Match, List

from telegram.ext import Dispatcher

from core import EventManager, MessageManager, InnerHandler, CommandFilter, InnerUpdate
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_players
from models import TelegramChat, Group, Player
from modules import BasicModule
from utils.functions import CustomInnerFilters


class ActivatedModule(BasicModule):
    """
    message sending
    """
    module_name = 'activated'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='active_c', description='Активировать чат'),
                self._active_c, [CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='active_u', description='Активировать юзера'),
                self._active_u, [CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='active_g', description='Активировать группу'),
                self._active_g, [CustomInnerFilters.from_player]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<group_name>.*)'),
        argument_miss_msg='Пришли сообщение в формате "/active_g Имя группы"'
    )
    def _active_g(self, update: InnerUpdate, match: Match):
        """
        Вызывается с аргументом Алиаса группы
        Меняет поле Group.is_active на противоположное значение
        """

        group_name = match.group('group_name')
        group = Group.get_by_name(group_name)
        if group is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'Группы "{html.escape(group_name)}" не существует!'
            )

        new_group_status = not group.is_active
        group.is_active = new_group_status
        group.save()

        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Группа "{group_name}" {"активирована" if new_group_status else "деактивированна"}'
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<alias>\w+)(\s+-\s+)?(?P<chat_id>.+)?'),
        argument_miss_msg='Пришли сообщение в формате "/active_c Алиас |- chat_id"'
    )
    def _active_c(self, update: InnerUpdate, match: Match):
        """
        Вызывается с аргументом Алиаса группы и id чата для активации или просто в нужный чат
        Пример в лс боту: /active Test 10000
        Пример в нужный чат: /active Test
        Меняет поле TelegramChat.is_active на противоположное значение и присваивает TelegramChat.alias знаечение алиаса
        """

        alias = match.group('alias')
        chat_id = match.group('chat_id') or update.effective_chat_id
        chat = TelegramChat.get_or_none(TelegramChat.chat_id == int(chat_id))
        if chat is None or chat.chat_type == 'private':
            self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'Чата с id: {chat_id} не найден'
            )
            return

        new_chat_status = not chat.is_active
        chat.is_active = new_chat_status
        chat.shortname = alias
        chat.save()

        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f"Чат с id: {chat_id} {'активирован' if new_chat_status else 'деактивирован'}"
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/active_u @user1 @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def _active_u(self, update: InnerUpdate, players: List[Player]):
        """
        Вызывается с аргументом @user1 @user2
        /active_u @user1
        Меняет значение Player.is_active на противоположное значение
        """

        actives: List[str] = []
        deactives: List[str] = []

        for player in players:
            new_player_status = not player.is_active
            player.is_active = new_player_status
            player.save()

            if new_player_status:
                actives.append(player.mention_html())
            else:
                deactives.append(player.mention_html())

        if actives:
            self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f"Игроки: {'; '.join(actives)} - активированны"
            )

        if deactives:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f"Игроки: {'; '.join(deactives)} - деактивированны"
            )
