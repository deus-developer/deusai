from collections import defaultdict
from typing import List, Dict

from telegram.ext import Dispatcher

from core import EventManager, MessageManager, InnerHandler, CommandFilter, CommandNameFilter, InnerUpdate
from decorators import permissions
from decorators.permissions import is_admin, or_, self_
from decorators.users import get_players
from models import Player
from modules import BasicModule
from utils.functions import CustomInnerFilters


def yes_no_emoji(value: bool) -> str:
    return '✅' if value else '❌'


def editable_command(command: str, editable: bool) -> str:
    return f'\n\t\t\t-> /{command}' if editable else '🔒'


class SettingsModule(BasicModule):
    module_name = 'settings'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('settings'),
                self._settings,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('settings_pings'),
                self._settings_pings,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandNameFilter('sping'),
                self._sping_switch,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _settings(self, update: InnerUpdate, players: List[Player]):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_settings(player, chat_id, update.player == player)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _settings_pings(self, update: InnerUpdate, players: List[Player]):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_ping_settings(player, chat_id, update.player == player)

    def _show_player_settings(self, player: Player, chat_id: int, editable: bool):
        formatted_settings = (
            f'\t\t\t\t<b>{player.nickname}</b>\n'
            f'\t\t\t\t\t<b>Настройки</b>\t\t\t\t\t\n'
        )
        formatted_settings += (
            f'Пинги: {editable_command("settings_pings", editable)}'
        )

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_settings
        )

    def _show_player_ping_settings(self, player: Player, chat_id: int, editable: bool):
        settings = player.settings

        pings: Dict[str, bool] = defaultdict(bool)
        pings.update(settings.pings)

        formatted_settings = (
            f'\t\t\t\t<b>{player.nickname}</b>\n'
            f'\t\t\t\t\t<b>Настройки пингов</b>\t\t\t\t\t\n'
        )

        formatted_settings += (
            f'<code>За 3 часа до рейда</code>: {yes_no_emoji(pings["notify_raid_3"])} '
            f'{editable_command("sping_notify_raid_3", editable)}\n'
            
            f'<code>За 10 минут до рейда🚷</code>: {yes_no_emoji(pings["notify_raid_tz_10"])} '
            f'{editable_command("sping_notify_raid_tz_10", editable)}\n'
            
            f'<code>Выход на рейд🚷</code>: {yes_no_emoji(pings["notify_raid_tz"])} '
            f'{editable_command("sping_notify_raid_tz", editable)}\n'
            
            f'<code>После итогов рейда🚷</code>: {yes_no_emoji(pings["notify_raid_tz_report"])} '
            f'{editable_command("sping_notify_raid_tz_report", editable)}\n'
        )

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_settings
        )

    def _sping_switch(self, update: InnerUpdate):
        ping_name = update.command.subcommand
        settings = update.player.settings
        if ping_name not in settings.pings:
            return update.telegram_update.message.reply_text(f'Настройки "{ping_name}" не существует.')

        settings.pings[ping_name] = not settings.pings[ping_name]
        settings.pings = settings.pings
        settings.save()

        return update.telegram_update.message.reply_text(
            f'Изменил настройку пинга. Текущее значение: {yes_no_emoji(settings.pings[ping_name])}'
        )
