import re

from telegram import ParseMode
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import (
    command_handler,
    permissions
)
from decorators.permissions import is_admin
from decorators.users import get_players
from models import (
    Group,
    TelegramChat
)
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
                CommandFilter(command='active_c', description='Активировать чат'), self._active_c,
                [CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='active_u', description='Активировать юзера'), self._active_u,
                [CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='active_g', description='Активировать группу'), self._active_g,
                [CustomInnerFilters.from_player]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<group_name>.*)'),
        argument_miss_msg='Пришли сообщение в формате "/active_g Имя группы"'
    )
    def _active_g(self, update: Update, match, *args, **kwargs):
        """
        Вызывается с аргументом Алиаса группы
        Меняет поле Group.is_active на противоположное значение
        """
        group_name = match.group('group_name')
        group = Group.get_by_name(group_name)
        if not group:
            return self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f'Группы "{group_name}" не существует!'
            )
        group.is_active = not group.is_active
        group.save()

        sex_state = 'а' if update.player.settings.sex == 1 else ''
        notify_state = f'активировал{sex_state}' if group.is_active else f'деактивировал{sex_state}'
        notify_text = (
            f'[{mention_html(update.player.telegram_user_id, update.player.nickname)}]'
            f'\t\t-> {notify_state} группу "{group.name}" ( <code>ID:{group.id}</code> )\n'
            f'<b>Причина:</b> {update.invoker.get_link()} напиши причину плез.'
        )
        self.message_manager.send_message(chat_id=settings.NOTIFY_CHAT_ID, text=notify_text, parse_mode='HTML')

        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'Группа "{group_name}" {"активирована" if group.is_active else "деактивированна"}'
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<alias>\w+)(\s+-\s+)?(?P<chat_id>.+)?'),
        argument_miss_msg='Пришли сообщение в формате "/active_c Алиас |- chat_id"'
    )
    def _active_c(self, update: Update, match, *args, **kwargs):
        """
        Вызывается с аргументом Алиаса группы и user_id чата для активации или просто в нужный чат
        Пример в лс боту: /active Test 10000
        Пример в нужный чат: /active Test
        Меняет поле TelegramChat.is_active на противоположное значение и присваивает TelegramChat.alias знаечение алиаса
        """
        alias = match.group('alias')
        chat_id = match.group('chat_id') or update.telegram_update.message.chat_id
        chat = TelegramChat.get_or_none(TelegramChat.chat_id == int(chat_id))
        if not chat or chat.chat_type == 'private':
            self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f'Чата с user_id:{chat_id} не найден'
            )
            return

        chat.is_active = not chat.is_active
        chat.shortname = alias
        chat.save()

        telegram_chat = self.message_manager.bot.get_chat(chat_id=chat_id)
        chat_name = f'<a href="{telegram_chat.invite_link}">{telegram_chat.title}</a>' if telegram_chat.invite_link else telegram_chat.title

        sex_state = 'а' if update.player.settings.sex == 1 else ''
        notify_state = f'активировал{sex_state}' if chat.is_active else f'деактивировал{sex_state}'
        notify_text = (
            f'[{mention_html(update.player.telegram_user_id, update.player.nickname)}]'
            f'\t\t-> {notify_state} чат {chat_name} ( {chat.shortname} )\n'
            f'<b>Причина:</b> {update.invoker.get_link()} напиши причину плез.'
        )
        self.message_manager.send_message(chat_id=settings.NOTIFY_CHAT_ID, text=notify_text, parse_mode='HTML')

        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f"Чат с user_id: {chat_id} {'активирован' if chat.is_active else 'деактивирован'}"
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/active_u @user1 @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def _active_u(self, update: Update, players, *args, **kwargs):  # TODO: Оптимизировать проставление статусов
        """
        Вызывается с аргументом @user1 @user2
        /active_u @user1
        Меняет значение Player.is_active на противоположное значение
        """
        actives = []
        deactives = []

        sex_state = 'а' if update.player.settings.sex == 1 else ''

        for player in players:
            player.is_active = not player.is_active

            if player.is_active:
                actives.append(mention_html(player.telegram_user_id, player.nickname))
            else:
                deactives.append(mention_html(player.telegram_user_id, player.nickname))
            
            player.save()

            notify_state = f'активировал{sex_state}' if player.is_active else f'деактивировал{sex_state}'
            notify_text = (
                f'[{mention_html(update.player.telegram_user_id, update.player.nickname)}]'
                f'\t\t-> {notify_state} игрока {mention_html(player.telegram_user_id, player.nickname)}\n'
                f'<b>Причина:</b> {update.invoker.get_link()} напиши причину плез.'
            )
            self.message_manager.send_message(chat_id=settings.NOTIFY_CHAT_ID, text=notify_text, parse_mode='HTML')

        if len(actives) != 0:
            self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f"Игроки: {'; '.join(actives)} - активированны",
                parse_mode=ParseMode.HTML
            )
        if len(deactives) != 0:
            return self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f"Игроки: {'; '.join(deactives)} - деактивированны",
                parse_mode=ParseMode.HTML
            )
