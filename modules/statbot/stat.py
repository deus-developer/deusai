import datetime
import math
import re
import time
from tempfile import NamedTemporaryFile

import peewee
import telegram
from jinja2 import Template
from pytils import dt
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    CallbackQueryHandler,
    Dispatcher,
    MessageHandler
)
from telegram.ext.filters import Filters
from telegram.utils.helpers import mention_html

import core
import models
from config import settings
from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update as InnerUpdate,
    UpdateFilter
)
from decorators import (
    command_handler,
    permissions
)
from decorators.chat import get_chat
from decorators.log import lead_time
from decorators.permissions import (
    is_admin,
    is_lider,
    or_,
    self_
)
from decorators.update import inner_update
from decorators.users import get_player
from decorators.users import (
    get_players,
    get_users
)
from models import (
    Group,
    Notebook,
    Player,
    PlayerStatHistory,
    RaidAssign,
    RaidStatus,
    RaidsInterval,
    Rank,
    Settings,
    TelegramUser
)
from modules import BasicModule
from modules.statbot.karma import Karma
from utils.functions import (
    CustomInnerFilters,
    _sex_image,
    price_upgrade
)
from ww6StatBotWorld import Wasteland
from .parser import (
    PlayerParseResult,
    Profile
)

KEY_STATS = ('hp', 'power', 'accuracy', 'oratory', 'agility')
ICONS_STATS = ('❤️', '💪', '🎯', '🗣', '🤸🏽️')
REWARDS_STATS = {
    'hp': 2,
    'power': 2,
    'accuracy': 1,
    'oratory': 1,
    'agility': 1
}
TRANSLATE_KEYS = {
    'hp': 'Здоровье',
    'power': 'Сила',
    'accuracy': 'Меткость',
    'oratory': 'Харизма',
    'agility': 'Ловкость'
}


class StatModule(BasicModule):  # TODO: Провести оптимизацию
    """
    responds to /stat, /info, /info, /progress commands,
    stores stats
    """

    module_name = 'stat'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('info'), self._user_info,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('stat'), self._stat,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('me'), self._stat,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('rewards'), self._raid_reward,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('caps'), self._cap,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raids'), self._raid_stat,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raids_info'), self._raids_info,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('title'), self._title,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('progress'), self._progress,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('karmachart'), self._karma_chart,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('stamina_ls'), self._stamina_list,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('timezones_ls'), self._timezone_list,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('sleeptime_ls'), self._sleeptime_list,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('houses_ls'), self._house_list,
                [CustomInnerFilters.from_admin_chat_or_private, CustomInnerFilters.from_player]
            )
        )

        self._re_raid_stat_inline = re.compile(r'^raids_(?P<player_id>\d+)_(?P<interval_id>\d+)$')
        self._re_raid_info_inline = re.compile(r'^raids_info_(?P<player_id>\d+)_(?P<interval_id>\d+)$')

        self.add_handler(CallbackQueryHandler(self._raid_stat_inline, pattern=self._re_raid_stat_inline))
        self.add_handler(CallbackQueryHandler(self._raid_info_inline, pattern=self._re_raid_info_inline))

        self._buttons = {
            '📊 Статы': {
                'handler': self._stat,
                'kwargs': {}
            },
            '📈 Прогресс': {
                'handler': self._progress,
                'kwargs': {}
            },
            '🗓 Рейды': {
                'handler': self._raid_stat,
                'kwargs': {}
            },
        }
        self.add_handler(MessageHandler(Filters.text(self._buttons.keys()), self._buttons_handler))

        self.add_inner_handler(InnerHandler(UpdateFilter('profile'), self._save_stats, [CustomInnerFilters.private]))
        super().__init__(event_manager, message_manager, dispatcher)

    @inner_update()
    @get_player
    @get_chat
    def _buttons_handler(self, update: InnerUpdate, *args, **kwargs):
        handler = self._buttons.get(update.telegram_update.message.text, None)
        if None:
            return update.message.reply_text(f'Пока что кнопка [{update.telegram_update.message.text}] не работает')
        update.command = core.Command(update.telegram_update.message)
        update.command.argument = ''
        # noinspection PyTypeChecker
        return handler['handler'](update, *args, **kwargs, **handler['kwargs'])

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/stamina_ls Группа"')
    @lead_time(name='/stamina_ls command', description='Вызов данных по стамине')
    def _stamina_list(self, update: InnerUpdate, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        group = Group.get_by_name(update.command.argument)
        if not group:
            return

        output = [f'\t\t\t\tСписок игроков по стамине:\n']
        members = group.members \
            .where(Player.is_active == True) \
            .filter(Player.frozen == False) \
            .order_by(models.Player.stamina.desc())

        for idx, player in enumerate(members, 1):
            output.append(f'{idx}. {mention_html(player.telegram_user_id, player.nickname)}:\t\t{player.stamina}🔋')
        if len(output) == 1:
            output.append('Ой, а где они???')

        self.message_manager.send_message(
            chat_id=chat_id,
            text='\n'.join(output),
            parse_mode=telegram.ParseMode.HTML
        )

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/houses_ls Группа"')
    @lead_time(name='/houses_ls command', description='Вызов данных по дому в Ореоле')
    def _house_list(self, update: InnerUpdate, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        group = Group.get_by_name(update.command.argument)
        if not group:
            return

        output = [f'\t\t\t\tСписок игроков по наличию дома в Ореоле:\n']
        query = group.members \
            .where(Player.is_active == True) \
            .filter(Player.frozen == False) \
            .join(Settings, on=(Settings.id == models.Player.settings_id)) \
            .order_by(models.Player.settings.house.desc(), models.Player.sum_stat.desc())

        for idx, player in enumerate(query, 1):
            output.append(f'{idx}. {"✅" if player.settings.house == 1 else "❌"}{mention_html(player.telegram_user_id, player.nickname)}[{player.sum_stat} 💪]')
        if len(output) == 1:
            output.append('Ой, а где они???')

        self.message_manager.send_message(
            chat_id=chat_id,
            text='\n'.join(output),
            parse_mode=telegram.ParseMode.HTML
        )

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/timezones_ls Группа"')
    @lead_time(name='/timezones_ls command', description='Вызов данных по таймзонам')
    def _timezone_list(self, update: InnerUpdate, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        group = Group.get_by_name(update.command.argument)
        if not group:
            return

        output = [f'\t\t\t\tСписок игроков по час. поясу:\n']
        query = group.members \
            .where(Player.is_active == True) \
            .filter(Player.frozen == False) \
            .join(Settings, on=(Settings.id == models.Player.settings_id)) \
            .order_by(models.Player.settings.timedelta.desc())

        for idx, player in enumerate(query, 1):
            output.append(f'{idx}. {mention_html(player.telegram_user_id, player.nickname)}:\t\t{player.settings.timedelta}⏳')
        if len(output) == 1:
            output.append('Ой, а где они???')

        self.message_manager.send_message(
            chat_id=chat_id,
            text='\n'.join(output),
            parse_mode=telegram.ParseMode.HTML
        )

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/sleeptime_ls Группа"')
    @lead_time(name='/sleeptime_ls command', description='Вызов данных по времени сна')
    def _sleeptime_list(self, update: InnerUpdate, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        group = Group.get_by_name(update.command.argument)
        if not group:
            return

        output = [f'\t\t\t\tСписок игроков по сну:\n']
        query = group.members \
            .where(Player.is_active == True) \
            .filter(Player.frozen == False) \
            .join(Settings, on=(Settings.id == models.Player.settings_id)) \
            .order_by(models.Player.settings.sleeptime.desc())
        for idx, player in enumerate(query, 1):
            output.append(f'{idx}. {mention_html(player.telegram_user_id, player.nickname)}:\t\t{player.settings.sleeptime}⏳')
        if len(output) == 1:
            output.append('Ой, а где они???')

        self.message_manager.send_message(
            chat_id=chat_id,
            text='\n'.join(output),
            parse_mode=telegram.ParseMode.HTML
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<title>.*)\s+-.*'),
        argument_miss_msg='Пришли сообщение в формате "/title Звание - @User1 @User2 ..."'
    )
    @get_players(include_reply=True, break_if_no_players=True, callback_message=True)
    def _title(self, update: InnerUpdate, match, players, *args, **kwargs):
        title = match.group('title')
        for pl in players:
            pl.title = title
            pl.save()
        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text='Раздал титул игрокам :)'
        )

    def _show_user_info(self, user: models.TelegramUser, chat_id, is_admin=False):
        player = user.player[0] if user.player else None
        if player:
            formatted_info = f'Это 👤{mention_html(player.telegram_user_id, player.nickname)}' \
                             f'\n🤘{player.gang.name if player.gang else "(Без банды)"}' \
                             f'\n🎗 {player.rank.name if player.rank else "Без звания"}  [{player.rank.emoji if player else "Без погонов"}]' \
                             f'\n📯 {player.title if player.title else "Неизвестный"}'

        else:
            formatted_info = f'Это 👤{user.get_link()}'

        formatted_info += f'\n🆔:\t\t{user.user_id if is_admin else "<b>скрыто</b>"}' \
                          f'\n🗓Стаж:\t\t{(datetime.datetime.now() - user.created_date).days} дн.' \
                          f'\n⏱В последний раз замечен: \t{user.last_seen_date.strftime(settings.DATETIME_FORMAT)}'

        self.message_manager.send_message(
            text=formatted_info,
            chat_id=chat_id,
            parse_mode='HTML'
        )

    def _show_player_stats(self, player: models.Player, chat_id, editable=False):
        formatted_stat = (
            f'{_sex_image(player.settings.sex if player.settings else 0)} <b>{player.nickname}</b>\n'
        )

        def get_groups(type_):
            return (group.name for group in player.members.where(Group.type == type_).order_by(models.Group.name))

        formatted_stat += (
            f'🐐Козел: <b>{", ".join(get_groups("goat")) or "-"}</b>\n'
            f'🤘Банда: <b>{", ".join(get_groups("gang")) or "-"}</b>\n'
            f'🔰Отряд: <b>{", ".join(get_groups("squad")) or "-"}</b>\n'
            '\n'
            f'🛡Броня: <b>{player.defence}</b>\n'
            f'⚔️Урон: <b>{player.attack}</b>\n'
            '\n'
            f'❤️Здоровье: <b>{player.hp}</b>\n'
            f'💪Сила: <b>{player.power}</b>\n'
            f'🎯Меткость: <b>{player.accuracy}</b>\n'
            f'🗣Харизма: <b>{player.oratory}</b>\n'
            f'🤸🏽️Ловкость: <b>{player.agility}</b>\n'
            '\n'
            f'🔋Выносливость: <b>{player.stamina}</b> 🏵Дзен: <b>{player.dzen}</b>\n '
        )

        if player.is_active:
            formatted_stat += (
                '\n'
                f'☯️Карма: <b>{player.karma}</b>\n'
                '👊️Рейды: /raids\n'
                '🎒Инвентарь: /inventory\n'
                '\n'
            )
        stats = player.stats
        formatted_stat += (
            f'📅Обновлён <b>{dt.distance_of_time_in_words(stats.time if stats else player.last_update, to_time=time.time())}</b>\n\n'
        )
        if editable:
            formatted_stat += (
                f'Настройки: /settings\n'
                f'Квесты: /quests' if player.id == 178 else ''
            )

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_stat,
            parse_mode='HTML',
        )

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _stat(self, update: InnerUpdate, players: list, *args, **kwargs):
        """
        Команду можно вызвать без параметров, вызвать в ответ на чье-либо сообщение либо
        передать конкретный список пользователей @user1 @user2 @user3.
        Возвращает информацию по указанным пользователям в виде ::

            👱🏻‍♀ Оценочка
            🐐Козел: Δeus Σx Machina
            🤘Банда: Δeus Σx Tower
            🔰Отряд: -

            🛡Броня: 197
            ⚔️Урон: 480

            ❤️Здоровье: 584
            💪Сила: 439
            🎯Меткость: 70
            🗣Харизма: 66
            🤸🏽️Ловкость: 152

            🔋Выносливость: 15 🏵Дзен: 0
             
            ☯️Карма: 22
            👊️Рейдов из 21: 2
            😑Рейдов пропущенно: 12

            📅Обновлён 2 часа назад
            Настройки: /settings
        """
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_stats(player, chat_id, player == update.player)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _cap(self, update: InnerUpdate, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_cap(player, chat_id, player == update.player)

    def _show_player_cap(self, player: models.Player, chat_id, editable=False):
        formatted_cap = f'Тебе осталось до капов 🏵{player.dzen}:' if editable else f'{mention_html(player.telegram_user_id, player.nickname)} осталось до капов 🏵{player.dzen}:'
        formatted_cap += '\n'

        total_discount = 0
        total_price = 0
        total_delta = 0

        def valueformatter(value: int, size: int = 0, symbol: str = ' '):
            svalue = str(value)
            vsize = len(svalue)
            if size == 0:
                size = vsize

            if size < vsize:
                size = vsize

            return symbol * (size - vsize) + svalue

        data = {}
        max_start = 0
        max_end = 0
        max_delta = 0

        for KEY_STAT, base_cap in Wasteland.KEY_STAT_BASE_CAP_BY_NAME.items():
            value = getattr(player, KEY_STAT, 0)

            end = base_cap + 50 * player.dzen
            delta = end - value
            if delta <= 0:
                continue

            price = int(price_upgrade(start=value, end=end, oratory=player.oratory, is_oratory=KEY_STAT == 'oratory'))
            price_with = int(price_upgrade(start=value, end=end, oratory=1200 + 50 * player.dzen, is_oratory=KEY_STAT == 'oratory'))

            total_discount += price - price_with
            total_price += price
            total_delta += delta

            max_start = max([max_start, value])
            max_end = max([max_end, end])
            max_delta = max([max_delta, delta])

            data.update(
                {
                    KEY_STAT:
                        {
                            'start': value,
                            'end': end,
                            'delta': delta,
                            'price': price
                        }
                }
            )
        startsize = len(str(max_start))
        endsize = len(str(max_end))
        deltasize = len(str(max_delta))

        def priceformatter(price: int, size: int = 3):
            sprice = str(price)
            nums = [str(x) for x in sprice][::-1]
            a = []
            for x in range(0, len(sprice), size):
                a.append(nums[x:x + size])
            return ' '.join([''.join(x[::-1]) for x in a][::-1])

        for KEY_STAT, info in data.items():
            icon = Wasteland.KEY_STAT_ICON_BY_NAME.get(KEY_STAT, '?')
            formatted_cap += f'{icon}<code>{valueformatter(info["start"], startsize)}</code>-><code>{valueformatter(info["end"], endsize)}</code>(<code>' \
                             f'{valueformatter(info["delta"], deltasize)}</code>) <code>🕳{priceformatter(info["price"])}</code>\n'
        formatted_cap += f'\n🎓<code>{player.sum_stat}-></code><code>{player.sum_stat + total_delta}</code>(<code>{total_delta}</code>)<code>🕳{priceformatter(total_price)}</code>\n'

        formatted_cap += (
            f'<b>Если прокачать сначала харизму</b> до <code>{1200 + 50 * player.dzen}</code>\n'
            f'То на прокачке остальных стат можно будет сэкономить 🕳<code>{priceformatter(total_discount)}</code>'
        )
        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_cap,
            parse_mode='HTML',
        )

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _raid_reward(self, update: InnerUpdate, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_raid_reward(player, chat_id, player == update.player)

    def _show_player_raid_reward(self, player: models.Player, chat_id, editable=False):
        goat = player.goat
        if not goat:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text='Ты без козла => без рейдов' if editable else f'{mention_html(player.telegram_user_id, player.nickname)} без козла => без рейдов',
                parse_mode='HTML',
            )
        league = goat.league
        if not league:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text='Ля, не знаю твою лигу. Кинь панель козла.' if editable else f'Ля, не знаю лигу {mention_html(player.telegram_user_id, player.nickname)}. Кинь панель его '
                                                                                  f'козла.',
                parse_mode='HTML',
            )
        formatted_reward = (
            f'<b>Расчет награды за рейд</b> для {mention_html(player.telegram_user_id, player.nickname)}\n'
            f'<b>Лига</b>: <code>{league}</code>\n\n'
        )

        for km in Wasteland.raid_kms_by_league.get(league):
            name, icon = Wasteland.raid_locations_by_km.get(km)
            price = Wasteland.raid_kms_price.get(km, 0)
            formatted_reward += f'[{km:02}{icon}] — <code>🕳{math.floor(player.raid_reward * price)}</code>\n'

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_reward,
            parse_mode='HTML',
        )

    def _calculate_raids_by_interval(self, start_date: datetime.datetime, last_date: datetime.datetime, player: models.Player):
        raids = player.raids_assign.filter(RaidAssign.time.between(start_date, last_date)) \
            .filter(RaidAssign.status_id != RaidStatus.UNKNOWN).order_by(RaidAssign.time)
        return {
            'cz': raids.filter(RaidAssign.km_assigned.not_in(Wasteland.raid_kms_tz)),
            'tz': raids.filter(RaidAssign.km_assigned << Wasteland.raid_kms_tz),
            'all': raids
        }

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _raid_stat(self, update: InnerUpdate, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_raid_stat(
                player=player,
                invoker=update.invoker,
                update=update,
                editable=False,
                offset=0
            )

    @inner_update()
    @get_player
    def _raid_stat_inline(self, update: InnerUpdate):
        player_id, interval_id = [int(x) for x in self._re_raid_stat_inline.search(update.telegram_update.callback_query.data).groups()]

        player = Player.get_or_none(id=player_id)
        if not player:
            return update.telegram_update.callback_query.answer(f'Игрока с ID = {player_id} не существует!')

        now_interval_id = RaidsInterval.select(RaidsInterval.id).order_by(RaidsInterval.id.desc()).limit(1).scalar()
        if not now_interval_id:
            return update.telegram_update.callback_query.answer('В системе нет интервалов рейдов!')

        offset = now_interval_id - interval_id
        self._show_player_raid_stat(
            player=player,
            invoker=update.invoker,
            update=update,
            editable=True,
            offset=offset
        )

    def _show_player_raid_stat(
        self, player: models.Player,
        invoker: models.TelegramUser, update: InnerUpdate,
        editable: bool = False, offset: int = 0
    ):
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), offset=offset)
        if not interval:
            if editable:
                return update.telegram_update.callback_query.answer('Такого периода не существует!')
            return update.telegram_update.message.reply_text('Такого периода не существует')

        raids = self._calculate_raids_by_interval(start_date=interval.start_date, last_date=interval.last_date, player=player)

        sex_suffix = 'а' if player.settings.sex == 1 else ''

        def raidformatter(number: int):
            mod = number % 10
            if mod == 1:
                return ''
            elif 2 <= mod <= 4:
                return 'а'
            elif 0 <= mod <= 5:
                return 'ов'
            else:
                return ''

        name = mention_html(player.telegram_user_id, player.nickname.capitalize()) if invoker.is_admin else 'Ты'
        if invoker.is_admin:
            formatted_report = f'<b>Рейдовая статистика📊 {mention_html(player.telegram_user_id, player.nickname.capitalize())}</b>\n'
        else:
            formatted_report = f'<b>Рейдовая статистика📊</b>\n'

        raids_all = raids['all'].count()

        raids_tz = raids['tz'].filter(RaidAssign.status_id == RaidStatus.CONFIRMED).count()
        raids_cz = raids['cz'].filter(RaidAssign.status_id == RaidStatus.CONFIRMED).count()

        raids_visited = raids_tz + raids_cz
        raids_passed = raids_all - raids_visited

        raids_points = raids_tz * 1 + raids_cz * 0.75

        formatted_report += (
            f'<code>Период: с {interval.start_date.strftime("%d.%m %H-%M")} по {interval.last_date.strftime("%d.%m %H-%M")}</code>\n'
            f'<b>{name} посетил{sex_suffix} {raids_visited} рейд{raidformatter(raids_visited)}👊</b>\n'
            f'<b>{name} пропустил{sex_suffix} {raids_passed} рейд{raidformatter(raids_passed)}👀</b>\n'
            f'<b>{name} получил{sex_suffix} {raids_points} балл{raidformatter(raids_points)}</b>'
        )

        last_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id - 1)).scalar()
        next_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id + 1)).scalar()
        main_interval_id = interval.id + offset

        buttons = [
            []
        ]
        if last_interval_id:
            buttons[0].append(InlineKeyboardButton(text='🔙Назад', callback_data=f'raids_{player.id}_{last_interval_id}'))
        buttons[0].append(InlineKeyboardButton(text='🧾Подробнее', callback_data=f'raids_info_{player.id}_{interval.id}'))
        if next_interval_id:
            buttons[0].append(InlineKeyboardButton(text='🔜Следующее', callback_data=f'raids_{player.id}_{next_interval_id}'))

        if offset != 0:
            buttons.append([InlineKeyboardButton(text='🔝Текущее', callback_data=f'raids_{player.id}_{main_interval_id}')])

        markup = InlineKeyboardMarkup(buttons)

        if not editable:
            self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text=formatted_report,
                reply_markup=markup,
                parse_mode='HTML',
            )
        else:
            message = update.telegram_update.callback_query.message
            if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text=formatted_report,
                    reply_markup=markup,
                    parse_mode='HTML',
                )
            return update.telegram_update.callback_query.edit_message_text(text=formatted_report, reply_markup=markup, parse_mode='HTML')

    @inner_update()
    @get_player
    def _raid_info_inline(self, update: InnerUpdate):
        player_id, interval_id = [int(x) for x in self._re_raid_info_inline.search(update.telegram_update.callback_query.data).groups()]

        player = Player.get_or_none(id=player_id)
        if not player:
            return update.telegram_update.callback_query.answer(f'Игрока с ID = {player_id} не существует!')

        now_interval_id = RaidsInterval.select(RaidsInterval.id).order_by(RaidsInterval.id.desc()).limit(1).scalar()
        if not now_interval_id:
            return update.telegram_update.callback_query.answer('В системе нет интервалов рейдов!')

        offset = now_interval_id - interval_id
        self._show_player_raids_info(
            player=player,
            invoker=update.invoker,
            update=update,
            editable=True,
            offset=offset
        )

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _raids_info(self, update: InnerUpdate, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_raids_info(
                player=player,
                invoker=update.invoker,
                update=update,
                editable=False,
                offset=0
            )

    def _show_player_raids_info(
        self, player: models.Player,
        invoker: models.TelegramUser, update: InnerUpdate,
        editable: bool = False, offset: int = 0
    ):
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), offset=offset)
        if not interval:
            if editable:
                return update.telegram_update.callback_query.answer('Такого периода не существует!')
            return update.telegram_update.message.reply_text('Такого периода не существует')

        raids = self._calculate_raids_by_interval(start_date=interval.start_date, last_date=interval.last_date, player=player)

        if invoker.is_admin:
            formatted_report = f'<b>Детальная рейдовая статистика📊 {mention_html(player.telegram_user_id, player.nickname.capitalize())}</b>\n'
        else:
            formatted_report = f'<b>Детальная рейдовая статистика📊</b>\n'
        formatted_report += (
            f'<code>Период: с {interval.start_date.strftime("%d.%m %H-%M")} по {interval.last_date.strftime("%d.%m %H-%M")}</code>\n'
            '[дд.мм чч-мм]🚶00км Кулачок|Награда ( баллы ):\n'
        )

        total = 0
        for raid in raids['all']:
            icon = '🚷' if raid.km_assigned in Wasteland.raid_kms_tz else '🚶'
            points = 1 if raid.km_assigned in Wasteland.raid_kms_tz else 0.75
            knuckle = '✅' if raid.status_id in [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED] else '❌'
            final = '✅' if raid.status_id == RaidStatus.CONFIRMED else '❌'

            if raid.status_id != RaidStatus.CONFIRMED:
                total += points
            formatted_report += f'[{raid.time.strftime("%d.%m %H-%M")}]{icon}{raid.km_assigned:02}км {knuckle}|{final} ({points:.02f} б.)\n'

        formatted_report += (
            f'\n<code>Можно аппелировать {total} баллов</code>\n'
            '<b>Писать в лс: @DeusDeveloper</b>'
        )

        last_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id - 1)).scalar()
        next_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id + 1)).scalar()
        main_interval_id = interval.id + offset

        buttons = [
            []
        ]
        if last_interval_id:
            buttons[0].append(InlineKeyboardButton(text='🔙Назад', callback_data=f'raids_info_{player.id}_{last_interval_id}'))
        buttons[0].append(InlineKeyboardButton(text='📄Кратко', callback_data=f'raids_{player.id}_{interval.id}'))
        if next_interval_id:
            buttons[0].append(InlineKeyboardButton(text='🔜Следующее', callback_data=f'raids_info_{player.id}_{next_interval_id}'))

        if offset != 0:
            buttons.append([InlineKeyboardButton(text='🔝Текущее', callback_data=f'raids_info_{player.id}_{main_interval_id}')])

        markup = InlineKeyboardMarkup(buttons)

        if not editable:
            self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text=formatted_report,
                reply_markup=markup,
                parse_mode='HTML',
            )
        else:
            message = update.telegram_update.callback_query.message
            if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text=formatted_report,
                    reply_markup=markup,
                    parse_mode='HTML',
                )
            return update.telegram_update.callback_query.edit_message_text(text=formatted_report, reply_markup=markup, parse_mode='HTML')

    @get_users(include_reply=True, break_if_no_users=False)
    @permissions(or_(is_admin, self_))
    def _user_info(self, update: InnerUpdate, users: list, *args, **kwargs):
        """
        Команду можно вызвать без параметров, вызвать в ответ на чье-либо сообщение либо
        передать конкретный список пользователей @user1 @user2 @user3.
        Возвращает информацию по указанным пользователям в виде ::

            Это 👤Оценочка
            🤘Δeus Σx Tower
            🎗 Капрал  [▒▒🔰▒▒ ]
            📯 Неизвестный
            🆔:  308522294
            🗓Стаж:  40 дн.
            ⏱В последний раз замечен:  2020-06-03 21:41:20
            
        """
        users = users or ([update.invoker] if not update.command.argument else [])
        if not users:
            return
        for user in users:
            self._show_user_info(user, update.telegram_update.message.chat_id, update.invoker.is_admin)

    def _update_player(self, player: models.Player, profile: Profile, chat_id, created=False):
        st = profile.stats
        rewards = 0
        total = 0
        output = ['<b>Награда за прокачку</b>']
        for idx, key in enumerate(KEY_STATS):
            old = getattr(player, key, 0)
            new = getattr(st, key, 0)
            delta = new - old
            if delta <= 0:
                continue
            total += delta
            output.append(f'\t\t[{ICONS_STATS[idx]}]\t{old}\t->\t{new} (+{delta})')
            rewards += delta * REWARDS_STATS.get(key, 1)
        sum_stat_old = player.sum_stat
        player.add_stats(
            hp=st.hp, attack=st.attack, defence=st.defence,
            power=st.power, accuracy=st.accuracy, oratory=st.oratory,
            agility=st.agility, stamina=st.stamina, dzen=st.dzen,
            raids21=player.raids21, raid_points=player.raid_points, loose_raids=player.loose_raids, loose_weeks=player.loose_weeks,
            karma=player.karma, regeneration_l=player.regeneration_l, batcoh_l=player.batcoh_l
        )
        if profile.crew:
            gang = Group.get_by_name(profile.crew, group_type='gang') or Group.create(name=profile.crew, type='gang')
            player.gang = gang
            player.is_active = player.is_active or gang.is_active
        player.fraction = profile.fraction
        player.save()

        self.message_manager.send_message(
            chat_id=chat_id,
            text='Статистика сохранена'
        )

        if rewards <= 0:
            return

        if total > 0:
            output.append(f'\n\t\t[📯] {sum_stat_old}\t->\t{total + sum_stat_old} (+{total})')
        rewards *= 0.1 if created else 1
        output.append(f'\t\t[☯️]\t\t+{rewards}\n')
        output.append(f'<code>Последние обновление <b>{dt.distance_of_time_in_words(player.last_update, to_time=time.time())}</b></code>')

        u = InnerUpdate()
        u.karma_ = Karma(module_name='stat', recivier=player, sender=player, amount=rewards, description=f'Начисление кармы за прокачку.')
        self.event_manager.invoke_handler_update(u)

        self.message_manager.send_message(chat_id=chat_id, text='\n'.join(output), parse_mode='HTML')

        max_damage = (player.power / 0.57144)

    def _save_stats(self, update: PlayerParseResult):
        message = update.telegram_update.message
        profile = update.profile

        if update.invoker.username is None:
            return self.message_manager.send_message(
                chat_id=message.chat_id, text='У тебя не указан юзернейм. Зайди в настройки своего телеграмм-аккаунта и укажи.'
                                              '\nА то мы с тобой не сможем познакомиться)'
            )

        created = False
        player = update.player
        if not player:
            created = True
            player = Player.get_or_none(nickname=profile.nickname)
            if not player:
                player = Player.create(telegram_user=update.invoker)
        elif not player.is_active:
            created = True

        if created:
            if update.timedelta > datetime.timedelta(minutes=5):
                return self.message_manager.send_message(chat_id=message.chat_id, text='А можно ПИП-БОЙ посвежее?')

            if update.invoker.user_id != profile.uid:
                return self.message_manager.send_message(chat_id=message.chat_id, text='Это не твой ПИП-БОЙ')

            player.nickname = profile.nickname
            player.rank = Rank.select().order_by(Rank.priority).get()
            player.settings = Settings.create()
            player.notebook = Notebook.create()
            player.telegram_user = update.invoker
        elif update.date < player.last_update:
            return self.message_manager.send_message(chat_id=message.chat_id, text='ПИП-БОЙ слишком стар для обновления статистики')

        if profile.nickname != player.nickname and profile.uid == update.invoker.user_id:
            self.message_manager.send_message(chat_id=message.chat_id, text=f'Раньше тебя звали {player.nickname}, теперь тебя зовут {profile.nickname}')
            player.nickname = profile.nickname
        elif profile.nickname == player.nickname:
            self._update_player(player, profile, message.chat_id, created)
        player.last_update = update.date
        player.save()

        if created:
            self.message_manager.send_message(chat_id=message.chat_id, text='Я тебя запомнил')
            if not player.is_active:
                self.message_manager.send_message(chat_id=message.chat_id, text='Ты, кстати, не активирован, обратись к @DeusDeveloper')
            self.logger.info(f'#{update.invoker.user_id}')

    @get_players(include_reply=True, break_if_no_players=False)
    @permissions(or_(is_admin, self_))
    @lead_time(name='/progress command', description='Вызов данных по прокачке ( график )')
    def _progress(self, update: InnerUpdate, players: list, *args, **kwargs):
        players = players or ([update.player] if update.command.argument == '' else [])
        if not players:
            return
        for player in players:
            self._show_player_progress(player, update.telegram_update.message.chat_id)

    @get_players(include_reply=True, break_if_no_players=True)
    @permissions(or_(is_admin, self_))
    def _karma_chart(self, update: InnerUpdate, players: list, *args, **kwargs):
        players = players or ([update.player] if update.command.argument == '' else [])
        if not players:
            return
        for player in players:
            self._show_player_karma(player, update.telegram_update.message.chat_id)

    def _show_player_karma(self, player: models.Player, chat_id):
        dates_query = PlayerStatHistory.select(peewee.fn.MAX(PlayerStatHistory.time).alias('maxtime')) \
            .where(PlayerStatHistory.player == player) \
            .group_by(peewee.fn.DATE(PlayerStatHistory.time)) \
            .order_by(peewee.fn.DATE(PlayerStatHistory.time).desc()) \
            .limit(15) \
            .alias('dates_query')
        stats_history = PlayerStatHistory.select() \
            .join(dates_query, on=(PlayerStatHistory.time == dates_query.c.maxtime)) \
            .where(PlayerStatHistory.player == player) \
            .order_by(PlayerStatHistory.time)
        if not stats_history:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Я поражён.... У игрока {mention_html(player.telegram_user_id, player.nickname)} нет истории кармы....',
                parse_mode=telegram.ParseMode.HTML
            )
        times = []
        karma = []
        for history in stats_history:
            times.append(history.time.timestamp() * 1000)
            karma.append(history.karma)

        template = Template(open('files/templates/progress.template.html', 'r', encoding='utf-8').read())

        dataset = [{
            'label': '☯️Карма',
            'color': 'rgb(255, 99, 132)',
            'dataset': [{
                'unix': times[idx],
                'y': value
            } for idx, value in enumerate(karma)]
        }]

        t = template.render(dataset=dataset, nickname=player.nickname)

        with NamedTemporaryFile() as tmp:
            open(tmp.name, 'w', encoding='utf-8').write(t)
            self.message_manager.bot.send_chat_action(
                chat_id=chat_id,
                action=telegram.ChatAction.UPLOAD_DOCUMENT
            )

            self.message_manager.bot.send_document(chat_id=chat_id, document=open(tmp.name, 'rb'), filename='karmachart.html')

    def _show_player_progress(self, player: models.Player, chat_id):
        dates_query = PlayerStatHistory.select(peewee.fn.MAX(PlayerStatHistory.time).alias('maxtime')) \
            .where(PlayerStatHistory.player == player) \
            .group_by(peewee.fn.DATE(PlayerStatHistory.time)) \
            .order_by(peewee.fn.DATE(PlayerStatHistory.time).desc()) \
            .limit(10).alias('dates_query')

        stats_history = PlayerStatHistory.select() \
            .join(dates_query, on=(PlayerStatHistory.time == dates_query.c.maxtime)) \
            .where(PlayerStatHistory.player == player) \
            .order_by(PlayerStatHistory.time)

        if not stats_history:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Я поражён.... У игрока {mention_html(player.telegram_user_id, player.nickname)} нет истории прокачки....',
                parse_mode=telegram.ParseMode.HTML
            )
        times = []
        stats = {key: None for key in KEY_STATS}

        for history in stats_history:
            times.append(history.time.timestamp() * 1000)
            for key in Wasteland.KEY_STATS.keys():
                stat = stats.get(key, None)
                if not stat:
                    stat = []
                stat.append(getattr(history, key))
                stats.update(
                    {
                        key: stat
                    }
                )

        template = Template(open('files/templates/progress.template.html', 'r', encoding='utf-8').read())

        dataset = []

        for KEY_STAT, label in Wasteland.KEY_STATS.items():
            dataset.append(
                {
                    'label': label,
                    'color': Wasteland.COLOR_BY_KEY_STAT.get(KEY_STAT, 'rgb(255, 99, 132)'),
                    'dataset': [{
                        'unix': times[idx],
                        'y': value
                    } for idx, value in enumerate(stats.get(KEY_STAT))]
                }
            )
        t = template.render(dataset=dataset, nickname=player.nickname)

        with NamedTemporaryFile() as tmp:
            open(tmp.name, 'w', encoding='utf-8').write(t)
            self.message_manager.bot.send_chat_action(
                chat_id=chat_id,
                action=telegram.ChatAction.UPLOAD_DOCUMENT
            )

            self.message_manager.bot.send_document(
                chat_id=chat_id, document=open(tmp.name, 'rb'), filename='stats.html'
            )
