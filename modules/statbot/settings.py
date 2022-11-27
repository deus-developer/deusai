import re

from telegram.ext import Dispatcher

from core import (
    CommandFilter,
    CommandNameFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import (
    command_handler,
    permissions
)
from decorators.permissions import (
    and_,
    is_admin,
    is_rank,
    or_,
    self_
)
from decorators.users import get_players
from modules import BasicModule
from utils.functions import (
    CustomInnerFilters,
    _sex_image
)


def yes_no_emoji(value):
    return '✅' if bool(value) else '❌'


def editable_command(command: str, editable: bool):
    return f'\n\t\t\t-> /{command}' if editable else '🔒'


class SettingsModule(BasicModule):  # TODO: Доработать

    module_name = 'settings'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('set_sex'), self._set_sex,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('set_timezone'), self._set_timezone,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('set_sleeptime'), self._set_sleeptime,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('set_house'), self._set_house,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('settings'), self._settings,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('settings_pings'), self._settings_pings,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandNameFilter('sping'), self._sping_switch,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _settings(self, update: Update, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_settings(player, chat_id, update.player == player)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, and_(self_, is_rank(rank_name='Капрал'))))
    def _settings_pings(self, update: Update, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_ping_settings(player, chat_id, update.player == player)

    def _show_player_settings(self, player, chat_id, editable):
        formatted_settings = (
            f'\t\t\t\t<b>{player.nickname}</b>\n'
            f'\t\t\t\t\t<b>Настройки</b>\t\t\t\t\t\n'
        )
        settings = player.settings

        formatted_settings += (
            f'Пол: {_sex_image(settings.sex)} {editable_command("set_sex", editable)}\n'
            f'Временная зона: {settings.timedelta} {editable_command("set_timezone", editable)}\n'
            f'Время сна: {settings.sleeptime} {editable_command("set_sleeptime", editable)}\n'
            f'Дом в Ореоле: {"Есть" if settings.house == 1 else "Отсутствует"} {editable_command("set_house", editable)}\n'
        )

        if is_rank(rank_name='Капрал')(player=player):
            formatted_settings += (
                f'Пинги: <code>Меню</code> {"/settings_pings" if editable else "🔒"}\n'
            )

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_settings,
            parse_mode='HTML',
        )

    def _show_player_ping_settings(self, player, chat_id, editable):
        settings = player.settings
        pings = settings.pings

        formatted_settings = (
            f'\t\t\t\t<b>{player.nickname}</b>\n'
            f'\t\t\t\t\t<b>Настройки пингов</b>\t\t\t\t\t\n'
        )

        formatted_settings += (
            f'<code>Уведомление о ПИНе</code>: {yes_no_emoji(pings["sendpin"])} {editable_command("sping_sendpin", editable)}\n'
            f'<code>Рассылки</code>: {yes_no_emoji(pings["echo"])} {editable_command("sping_echo", editable)}\n'
            f'<code>Получении головы</code>: {yes_no_emoji(pings["drop_head"])} {editable_command("sping_drop_head", editable)}\n'
            f'<code>Призыв в чат</code>: {yes_no_emoji(pings["ping"])} {editable_command("sping_ping", editable)}\n'
            f'<code>Рейдовый отчёт</code>: {yes_no_emoji(pings["weekly_report"])} {editable_command("sping_weekly_report", editable)}\n'
            f'<code>За 3 часа до рейда</code>: {yes_no_emoji(pings["notify_raid_3"])} {editable_command("sping_notify_raid_3", editable)}\n'
            f'<code>За 10 минут до рейда🚷</code>: {yes_no_emoji(pings["notify_raid_tz_10"])} {editable_command("sping_notify_raid_tz_10", editable)}\n'
            f'<code>Выход на рейд🚷</code>: {yes_no_emoji(pings["notify_raid_tz"])} {editable_command("sping_notify_raid_tz", editable)}\n'
            f'<code>После итогов рейда🚷</code>: {yes_no_emoji(pings["notify_raid_tz_report"])} {editable_command("sping_notify_raid_tz_report", editable)}\n'
        )

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_settings,
            parse_mode='HTML',
        )

    @permissions(or_(is_admin, is_rank(rank_name='Сержант')))
    def _sping_switch(self, update: Update, *args, **kwargs):
        ping_name = update.command.subcommand
        settings = update.player.settings
        if ping_name not in settings.pings:
            return update.telegram_update.message.reply_text(f'Настройки "{ping_name}" не существует.')
        settings.pings[ping_name] = not settings.pings[ping_name]
        settings.pings = settings.pings
        settings.save()
        return update.telegram_update.message.reply_text(f'Изменил настройку пинга. Текущее значение: {yes_no_emoji(settings.pings[ping_name])}')

    @permissions(or_(is_admin, is_rank(rank_name='Рядовой')))
    @command_handler(
        regexp=re.compile(r'(?P<sex>[12])?'),
        argument_miss_msg='Пришли сообщение в формате "/set_sex [1-2]"\n\t1 - мужчина\n\t2 - женщина'
    )
    def _set_sex(self, update: Update, match, *args, **kwargs):
        """
        Команда вызывается с числовым параметром от 1 до 2. 
        1 - мужчина
        2 - женщина
        """
        pl = update.player
        chat_id = update.telegram_update.message.chat_id
        mr = match.group('sex') or (pl.settings.sex + 1) % 2 + 1
        new_sex = int(mr) - 1

        pl.settings.sex = new_sex
        pl.settings.save()

        self.message_manager.send_message(
            chat_id=chat_id,
            text=f'Твой пол обновлён ({_sex_image(new_sex)})'
        )

    @permissions(or_(is_admin, is_rank(rank_name='Рядовой')))
    @command_handler(
        regexp=re.compile(r'(?P<is_house>[12])?'),
        argument_miss_msg='Пришли сообщение в формате "/set_house [1-2]"\n\t1 - Нет дома в Ореоле\n\t2 - Есть дом в Ореоле'
    )
    def _set_house(self, update: Update, match, *args, **kwargs):
        """
        Команда вызывается с числовым параметром от 1 до 2. 
        1 - Нет дома в Ореоле
        2 - Есть дом в Ореоле
        """
        pl = update.player
        chat_id = update.telegram_update.message.chat_id
        mr = match.group('is_house') or (pl.settings.house + 1) % 2 + 1
        new_house = int(mr) - 1

        pl.settings.house = new_house
        pl.settings.save()

        self.message_manager.send_message(
            chat_id=chat_id,
            text=f'Наличие у тебя дома в Ореоле обновлено. ({"Есть" if new_house == 1 else "Отсутствует"})'
        )

    @permissions(or_(is_admin, is_rank(rank_name='Рядовой')))
    @command_handler(
        regexp=re.compile(r'(?P<sign>[+-])?(?P<timedelta>\d+)'),
        argument_miss_msg='Пришли сообщение в формате "/set_timezone [-24 - +24]"'
    )
    def _set_timezone(self, update: Update, match, *args, **kwargs):
        chat_id = update.telegram_update.message.chat_id
        sign, delta = match.group('sign', 'timedelta')
        delta = int(delta)
        if not (0 <= delta <= 23):
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Введи часы в диапазоне от -23 до 23'
            )
        sign = True if sign == '+' or sign == '' else False
        delta = int(delta) if sign else -int(delta)

        pl = update.player
        pl.settings.timedelta = delta
        pl.settings.save()

        self.message_manager.send_message(
            chat_id=chat_id,
            text=f'Твой часовой пояс обновлён ({delta})'
        )

    @permissions(or_(is_admin, is_rank(rank_name='Рядовой')))
    @command_handler(
        regexp=re.compile(r'(?P<time>(?P<hour1>\d{2}):(?P<minute1>\d{2})-(?P<hour2>\d{2}):(?P<minute2>\d{2}))'),
        argument_miss_msg='Пришли сообщение в формате "/set_sleeptime 00:00-00:00"\n\tПо МСК!!! Это диапазон времени твоего сна.'
    )
    def _set_sleeptime(self, update: Update, match, *args, **kwargs):
        chat_id = update.telegram_update.message.chat_id
        time = match.group('time')
        hour1, minute1, hour2, minute2 = [int(x) for x in match.group('hour1', 'minute1', 'hour2', 'minute2')]
        if not ((0 <= hour1 <= 23) and (0 <= hour2 <= 23)):
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Введи часы в диапазоне от 00 до 23'
            )
        if not ((0 <= minute1 <= 59) and (0 <= minute2 <= 59)):
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Введи минуты в диапазоне от 00 до 59'
            )

        pl = update.player
        pl.settings.sleeptime = time
        pl.settings.save()

        self.message_manager.send_message(
            chat_id=chat_id,
            text=f'Твоё время сна обновлёно ({time})'
        )
