import datetime
import math
import re
import time
from tempfile import NamedTemporaryFile
from typing import List, Match

import peewee
from jinja2 import Template
from pytils import dt
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, MessageHandler, CallbackQueryHandler
from telegram.ext.filters import Filters

from src.config import settings
from src.core import (
    EventManager,
    MessageManager,
    InnerUpdate,
    InnerHandler,
    UpdateFilter,
    CommandFilter,
    Command,
)
from src.decorators import permissions, command_handler
from src.decorators.chat import get_chat
from src.decorators.permissions import is_admin, or_, self_, is_lider
from src.decorators.update import inner_update
from src.decorators.users import get_player
from src.decorators.users import get_players, get_users
from src.models import (
    Group,
    Settings,
    Player,
    PlayerStatHistory,
    RaidAssign,
    RaidStatus,
    RaidsInterval,
    TelegramUser,
)
from src.modules import BasicModule
from src.utils import format_number
from src.utils.functions import CustomInnerFilters, get_sex_image, price_upgrade
from src.wasteland_wars import constants
from src.wasteland_wars.schemas import Profile
from .parser import PlayerParseResult

KEY_STATS = ("hp", "power", "accuracy", "oratory", "agility")
ICONS_STATS = ("❤️", "💪", "🎯", "🗣", "🤸🏽️")
REWARDS_STATS = {"hp": 2, "power": 2, "accuracy": 1, "oratory": 1, "agility": 1}
TRANSLATE_KEYS = {
    "hp": "Здоровье",
    "power": "Сила",
    "accuracy": "Меткость",
    "oratory": "Харизма",
    "agility": "Ловкость",
}


class StatModule(BasicModule):
    """
    responds to /stat, /info, /info, /progress commands,
    stores stats
    """

    module_name = "stat"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("info"),
                self._user_info,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter("stat"),
                self._stat,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("me"),
                self._stat,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter("rewards"),
                self._raid_reward,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("caps"),
                self._cap,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("raids"),
                self._raid_stat,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("raids_info"),
                self._raids_info,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter("title"),
                self._title,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                    CustomInnerFilters.from_player,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("progress"),
                self._progress,
                [
                    CustomInnerFilters.from_player,
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter("stamina_ls"),
                self._stamina_list,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                    CustomInnerFilters.from_player,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("timezones_ls"),
                self._timezone_list,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                    CustomInnerFilters.from_player,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("sleeptime_ls"),
                self._sleeptime_list,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                    CustomInnerFilters.from_player,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("houses_ls"),
                self._house_list,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                    CustomInnerFilters.from_player,
                ],
            )
        )

        self.add_inner_handler(InnerHandler(UpdateFilter("profile"), self._save_stats, [CustomInnerFilters.private]))

        self._re_raid_stat_inline = re.compile(r"^raids_(?P<player_id>\d+)_(?P<interval_id>\d+)$")
        self._re_raid_info_inline = re.compile(r"^raids_info_(?P<player_id>\d+)_(?P<interval_id>\d+)$")

        self.add_handler(CallbackQueryHandler(self._raid_stat_inline, pattern=self._re_raid_stat_inline))
        self.add_handler(CallbackQueryHandler(self._raid_info_inline, pattern=self._re_raid_info_inline))

        self._buttons = {
            "📊 Статы": {"handler": self._stat, "kwargs": {}},
            "📈 Прогресс": {"handler": self._progress, "kwargs": {}},
            "🗓 Рейды": {"handler": self._raid_stat, "kwargs": {}},
        }
        self.add_handler(MessageHandler(Filters.text(self._buttons.keys()), self._buttons_handler))

        self._progress_template = Template(open("static/templates/progress.html", "r", encoding="utf-8").read())

        super().__init__(event_manager, message_manager, dispatcher)

    @inner_update()
    @get_player
    @get_chat
    def _buttons_handler(self, update: InnerUpdate, *args, **kwargs):
        handler = self._buttons.get(update.telegram_update.message.text)
        if handler is None:
            return

        update.command = Command.from_message(update.telegram_update.message)
        update.command.argument = ""

        callback = handler["handler"]
        calback_kwargs = handler["kwargs"]
        return callback(update, *args, **kwargs, **calback_kwargs)

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/stamina_ls Группа"')
    def _stamina_list(self, update: InnerUpdate):
        group = Group.get_by_name(update.command.argument)
        if group is None:
            return

        output = [f"\t\t\t\tСписок игроков по стамине:\n"]
        members = group.members.where(Player.is_active == True).order_by(Player.stamina.desc())

        for idx, player in enumerate(members, 1):
            output.append(f"{idx}. {player.mention_html()}:\t\t{player.stamina}🔋")

        if len(output) == 1:
            output.append("Ой, а где они???")

        self.message_manager.send_message(chat_id=update.effective_chat_id, text="\n".join(output))

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/houses_ls Группа"')
    def _house_list(self, update: InnerUpdate):
        group = Group.get_by_name(update.command.argument)
        if group is None:
            return

        output = [f"\t\t\t\tСписок игроков по наличию дома в Ореоле:\n"]
        query = (
            group.members.where(Player.is_active == True)
            .join(Settings, on=(Settings.id == Player.settings_id))
            .order_by(Player.settings.house.desc(), Player.sum_stat.desc())
        )

        for idx, player in enumerate(query, 1):
            output.append(
                f'{idx}. {"✅" if player.settings.house == 1 else "❌"}'
                f'{player.mention_html()}[{player.sum_stat} 💪]'
            )

        if len(output) == 1:
            output.append("Ой, а где они???")

        self.message_manager.send_message(chat_id=update.effective_chat_id, text="\n".join(output))

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/timezones_ls Группа"')
    def _timezone_list(self, update: InnerUpdate):
        group = Group.get_by_name(update.command.argument)
        if group is None:
            return

        output = [f"\t\t\t\tСписок игроков по час. поясу:\n"]
        query = (
            group.members.where(Player.is_active == True)
            .join(Settings, on=(Settings.id == Player.settings_id))
            .order_by(Player.settings.timedelta.desc())
        )

        for idx, player in enumerate(query, 1):
            output.append(f"{idx}. {player.mention_html()}:" f"\t\t{player.settings.timedelta}⏳")

        if len(output) == 1:
            output.append("Ой, а где они???")

        self.message_manager.send_message(chat_id=update.effective_chat_id, text="\n".join(output))

    @permissions(is_lider)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/sleeptime_ls Группа"')
    def _sleeptime_list(self, update: InnerUpdate):
        group = Group.get_by_name(update.command.argument)
        if group is None:
            return

        output = [f"\t\t\t\tСписок игроков по сну:\n"]
        query = (
            group.members.where(Player.is_active == True)
            .join(Settings, on=(Settings.id == Player.settings_id))
            .order_by(Player.settings.sleeptime.desc())
        )

        for idx, player in enumerate(query, 1):
            output.append(f"{idx}. {player.mention_html()}:" f"\t\t{player.settings.sleeptime}⏳")

        if len(output) == 1:
            output.append("Ой, а где они???")

        self.message_manager.send_message(chat_id=update.effective_chat_id, text="\n".join(output))

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r"(?P<title>.*)\s+-.*"),
        argument_miss_msg='Пришли сообщение в формате "/title Звание - @User1 @User2 ..."',
    )
    @get_players(include_reply=True, break_if_no_players=True, callback_message=True)
    def _title(self, update: InnerUpdate, match: Match, players: List[Player]):
        title = match.group("title")
        for pl in players:
            pl.title = title
            pl.save()

        self.message_manager.send_message(chat_id=update.effective_chat_id, text="Раздал титул игрокам :)")

    def _show_user_info(self, user: TelegramUser, chat_id: int, is_admin: bool = False):
        player = user.player[0] if user.player else None
        if player:
            formatted_info = (
                f'Это 👤{player.mention_html()}'
                f'\n🤘{player.gang.name if player.gang else "(Без банды)"}'
                f'\n📯 {player.title if player.title else "Неизвестный"}'
            )
        else:
            formatted_info = f"Это 👤{user.get_link()}"

        formatted_info += (
            f'\n🆔:\t\t{user.user_id if is_admin else "<b>скрыто</b>"}'
            f'\n🗓Стаж:\t\t{(datetime.datetime.now() - user.created_date).days} дн.'
            f'\n⏱В последний раз замечен: \t{user.last_seen_date.strftime(settings.DATETIME_FORMAT)}'
        )

        self.message_manager.send_message(text=formatted_info, chat_id=chat_id)

    def _show_player_stats(self, player: Player, chat_id: int, editable: bool = False):
        formatted_stat = f"{get_sex_image(player.settings.sex if player.settings else 0)} <b>{player.nickname}</b>\n"

        def get_groups(group_type: str):
            return (group.name for group in player.members if group.type == group_type)

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
            formatted_stat += "\n" "👊️Рейды: /raids\n" "\n"

        stats = player.stats

        last_updated_at_text = dt.distance_of_time_in_words(
            stats.time if stats else player.last_update, to_time=time.time()
        )
        formatted_stat += f"📅Обновлён <b>{last_updated_at_text}</b>\n\n"

        if editable:
            formatted_stat += f"Настройки: /settings\n"

        self.message_manager.send_message(chat_id=chat_id, text=formatted_stat)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _stat(self, update: InnerUpdate, players: List[Player]):
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

        players_list = players or ([update.player] if update.command.argument == "" else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_stats(player, update.effective_chat_id, player == update.player)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _cap(self, update: InnerUpdate, players: List[Player]):
        players_list = players or ([update.player] if update.command.argument == "" else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_cap(player, update.effective_chat_id, player == update.player)

    def _show_player_cap(self, player: Player, chat_id: int, editable: bool = False):
        if editable:
            formatted_cap = f"Тебе осталось до капов 🏵{player.dzen}:"
        else:
            formatted_cap = f"{player.mention_html()} " f"осталось до капов 🏵{player.dzen}:"

        formatted_cap += "\n"

        total_discount = 0
        total_price = 0
        total_delta = 0

        def valueformatter(number: int, size: int = 0, symbol: str = " "):
            svalue = str(number)
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

        for KEY_STAT, base_cap in constants.KEY_STAT_BASE_CAP_BY_NAME.items():
            value = getattr(player, KEY_STAT, 0)

            end = base_cap + 50 * player.dzen
            delta = end - value
            if delta <= 0:
                continue

            price = int(
                price_upgrade(
                    start=value,
                    end=end,
                    oratory=player.oratory,
                    is_oratory=KEY_STAT == "oratory",
                )
            )
            price_with = int(
                price_upgrade(
                    start=value,
                    end=end,
                    oratory=1200 + 50 * player.dzen,
                    is_oratory=KEY_STAT == "oratory",
                )
            )

            total_discount += price - price_with
            total_price += price
            total_delta += delta

            max_start = max(max_start, value)
            max_end = max(max_end, end)
            max_delta = max(max_delta, delta)

            data[KEY_STAT] = {
                "start": value,
                "end": end,
                "delta": delta,
                "price": price,
            }

        startsize = len(str(max_start))
        endsize = len(str(max_end))
        deltasize = len(str(max_delta))

        for KEY_STAT, info in data.items():
            icon = constants.KEY_STAT_ICON_BY_NAME.get(KEY_STAT, "?")
            formatted_cap += (
                f'{icon}<code>{valueformatter(info["start"], startsize)}'
                f'</code>-><code>{valueformatter(info["end"], endsize)}</code>'
                f'(<code>{valueformatter(info["delta"], deltasize)}</code>) '
                f'<code>🕳{format_number(info["price"])}</code>\n'
            )

        formatted_cap += (
            f"\n🎓<code>{player.sum_stat}-></code>"
            f"<code>{player.sum_stat + total_delta}</code>"
            f"(<code>{total_delta}</code>)<code>🕳{format_number(total_price)}</code>\n"
        )

        formatted_cap += (
            f"<b>Если прокачать сначала харизму</b> до <code>{1200 + 50 * player.dzen}</code>\n"
            f"То на прокачке остальных стат можно будет сэкономить 🕳<code>{format_number(total_discount)}</code>"
        )
        self.message_manager.send_message(chat_id=chat_id, text=formatted_cap)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _raid_reward(self, update: InnerUpdate, players: List[Player]):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == "" else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_raid_reward(player, chat_id, player == update.player)

    def _show_player_raid_reward(self, player: Player, chat_id, editable=False):
        goat = player.goat
        if not goat:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=("Ты без козла => без рейдов" if editable else f"{player.mention_html()} без козла => без рейдов"),
            )

        league = goat.league
        if not league:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=(
                    "Ля, не знаю твою лигу. Кинь панель козла."
                    if editable
                    else f"Ля, не знаю лигу {player.mention_html()}. Кинь панель его козла."
                ),
            )

        formatted_reward = (
            f"<b>Расчет награды за рейд</b> для {player.mention_html()}\n" f"<b>Лига</b>: <code>{league}</code>\n\n"
        )

        for km in constants.raid_kms_by_league.get(league):
            name, icon = constants.raid_locations_by_km.get(km)
            price = constants.raid_kms_price.get(km, 0)
            formatted_reward += f"[{km:02}{icon}] — <code>🕳{math.floor(player.raid_reward * price)}</code>\n"

        self.message_manager.send_message(chat_id=chat_id, text=formatted_reward)

    def _calculate_raids_by_interval(
        self,
        start_date: datetime.datetime,
        last_date: datetime.datetime,
        player: Player,
    ):
        raids = (
            player.raids_assign.filter(RaidAssign.time.between(start_date, last_date))
            .filter(RaidAssign.status_id != RaidStatus.UNKNOWN)
            .order_by(RaidAssign.time)
        )

        return {
            "cz": raids.filter(RaidAssign.km_assigned.not_in(constants.raid_kms_tz)),
            "tz": raids.filter(RaidAssign.km_assigned << constants.raid_kms_tz),
            "all": raids,
        }

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _raid_stat(self, update: InnerUpdate, players: List[Player]):
        players_list = players or ([update.player] if update.command.argument == "" else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_raid_stat(
                player=player,
                invoker=update.invoker,
                update=update,
                editable=False,
                offset=0,
            )

    @inner_update()
    @get_player
    def _raid_stat_inline(self, update: InnerUpdate):
        player_id, interval_id = [
            int(x) for x in self._re_raid_stat_inline.search(update.telegram_update.callback_query.data).groups()
        ]

        player = Player.get_or_none(id=player_id)
        if not player:
            return update.telegram_update.callback_query.answer(f"Игрока с ID = {player_id} не существует!")

        now_interval_id = RaidsInterval.select(RaidsInterval.id).order_by(RaidsInterval.id.desc()).limit(1).scalar()
        if not now_interval_id:
            return update.telegram_update.callback_query.answer("В системе нет интервалов рейдов!")

        offset = now_interval_id - interval_id
        self._show_player_raid_stat(
            player=player,
            invoker=update.invoker,
            update=update,
            editable=True,
            offset=offset,
        )

    def _show_player_raid_stat(
        self,
        player: Player,
        invoker: TelegramUser,
        update: InnerUpdate,
        editable: bool = False,
        offset: int = 0,
    ):
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), offset=offset)
        if not interval:
            if editable:
                return update.telegram_update.callback_query.answer("Такого периода не существует!")
            return update.telegram_update.message.reply_text("Такого периода не существует")

        raids = self._calculate_raids_by_interval(
            start_date=interval.start_date, last_date=interval.last_date, player=player
        )

        def raidformatter(number: int):
            number %= 100
            if 11 <= number <= 19:
                return "ов"

            i = number % 10
            if i == 1:
                return ""
            elif 2 <= i <= 4:
                return "а"

            return "ов"

        if invoker.is_admin and update.player.telegram_user_id != invoker.user_id:
            name = player.mention_html()
            formatted_report = f"<b>Рейдовая статистика📊 " f"{player.mention_html()}</b>\n"
        else:
            name = "Ты"
            formatted_report = f"<b>Рейдовая статистика📊</b>\n"

        raids_all = raids["all"].count()

        raids_tz = raids["tz"].filter(RaidAssign.status_id << [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED]).count()
        raids_cz = raids["cz"].filter(RaidAssign.status_id << [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED]).count()

        raids_visited = raids_tz + raids_cz
        raids_passed = raids_all - raids_visited

        formatted_report += (
            f'<code>Период: с {interval.start_date.strftime("%d.%m %H-%M")} по '
            f'{interval.last_date.strftime("%d.%m %H-%M")}</code>\n'
            f'<b>{name} посетил {raids_visited} рейд{raidformatter(raids_visited)} 👊</b>\n'
            f'<b>{name} пропустил {raids_passed} рейд{raidformatter(raids_passed)} 👀</b>'
        )

        last_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id - 1)).scalar()
        next_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id + 1)).scalar()
        main_interval_id = interval.id + offset

        buttons = [[]]
        if last_interval_id:
            buttons[0].append(
                InlineKeyboardButton(
                    text="🔙Назад",
                    callback_data=f"raids_{player.id}_{last_interval_id}",
                )
            )
        buttons[0].append(
            InlineKeyboardButton(
                text="🧾Подробнее",
                callback_data=f"raids_info_{player.id}_{interval.id}",
            )
        )
        if next_interval_id:
            buttons[0].append(
                InlineKeyboardButton(
                    text="🔜Следующее",
                    callback_data=f"raids_{player.id}_{next_interval_id}",
                )
            )

        if offset != 0:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="🔝Текущее",
                        callback_data=f"raids_{player.id}_{main_interval_id}",
                    )
                ]
            )

        markup = InlineKeyboardMarkup(buttons)

        if not editable:
            self.message_manager.send_message(chat_id=invoker.chat_id, text=formatted_report, reply_markup=markup)
        else:
            message = update.telegram_update.callback_query.message
            if datetime.datetime.now() - message.date > datetime.timedelta(hours=12):
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id, text=formatted_report, reply_markup=markup
                )
            return update.telegram_update.callback_query.edit_message_text(
                text=formatted_report, reply_markup=markup, parse_mode="HTML"
            )

    @inner_update()
    @get_player
    def _raid_info_inline(self, update: InnerUpdate):
        player_id, interval_id = [
            int(x) for x in self._re_raid_info_inline.search(update.telegram_update.callback_query.data).groups()
        ]

        player = Player.get_or_none(id=player_id)
        if not player:
            return update.telegram_update.callback_query.answer(f"Игрока с ID = {player_id} не существует!")

        now_interval_id = RaidsInterval.select(RaidsInterval.id).order_by(RaidsInterval.id.desc()).limit(1).scalar()
        if not now_interval_id:
            return update.telegram_update.callback_query.answer("В системе нет интервалов рейдов!")

        offset = now_interval_id - interval_id
        self._show_player_raids_info(
            player=player,
            invoker=update.invoker,
            update=update,
            editable=True,
            offset=offset,
        )

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _raids_info(self, update: InnerUpdate, players: List[Player]):
        players_list = players or ([update.player] if update.command.argument == "" else [])
        if not players_list:
            return

        for player in players_list:
            self._show_player_raids_info(
                player=player,
                invoker=update.invoker,
                update=update,
                editable=False,
                offset=0,
            )

    def _show_player_raids_info(
        self,
        player: Player,
        invoker: TelegramUser,
        update: InnerUpdate,
        editable: bool = False,
        offset: int = 0,
    ):
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), offset=offset)
        if not interval:
            if editable:
                return update.telegram_update.callback_query.answer("Такого периода не существует!")
            return update.telegram_update.message.reply_text("Такого периода не существует")

        raids = self._calculate_raids_by_interval(
            start_date=interval.start_date, last_date=interval.last_date, player=player
        )

        if invoker.is_admin and invoker.user_id != player.telegram_user_id:
            formatted_report = f"<b>Детальная рейдовая статистика📊 " f"{player.mention_html()}</b>\n"
        else:
            formatted_report = f"<b>Детальная рейдовая статистика📊</b>\n"

        formatted_report += (
            f'<code>Период: с {interval.start_date.strftime("%d.%m %H-%M")} по '
            f'{interval.last_date.strftime("%d.%m %H-%M")}</code>\n\n'
        )

        for raid in raids["all"]:
            icon = "🚷" if raid.km_assigned in constants.raid_kms_tz else "🚶"
            knuckle = "✅" if raid.status_id in [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED] else "❌"

            formatted_report += (
                f'[{raid.time.strftime("%d.%m %H-%M")}]  {icon}' f'{raid.km_assigned:02}км  |{knuckle}\n'
            )

        last_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id - 1)).scalar()
        next_interval_id = RaidsInterval.select(RaidsInterval.id).filter(RaidsInterval.id == (interval.id + 1)).scalar()
        main_interval_id = interval.id + offset

        buttons = [[]]
        if last_interval_id:
            buttons[0].append(
                InlineKeyboardButton(
                    text="🔙Назад",
                    callback_data=f"raids_info_{player.id}_{last_interval_id}",
                )
            )
        buttons[0].append(InlineKeyboardButton(text="📄Кратко", callback_data=f"raids_{player.id}_{interval.id}"))
        if next_interval_id:
            buttons[0].append(
                InlineKeyboardButton(
                    text="🔜Следующее",
                    callback_data=f"raids_info_{player.id}_{next_interval_id}",
                )
            )

        if offset != 0:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="🔝Текущее",
                        callback_data=f"raids_info_{player.id}_{main_interval_id}",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(buttons)

        if not editable:
            self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text=formatted_report,
                reply_markup=reply_markup,
            )
        else:
            message = update.telegram_update.callback_query.message
            if datetime.datetime.now() - message.date > datetime.timedelta(hours=12):
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text=formatted_report,
                    reply_markup=reply_markup,
                )
            return update.telegram_update.callback_query.edit_message_text(
                text=formatted_report, reply_markup=reply_markup, parse_mode="HTML"
            )

    @get_users(include_reply=True, break_if_no_users=False)
    @permissions(or_(is_admin, self_))
    def _user_info(self, update: InnerUpdate, users: list):
        """
        Команду можно вызвать без параметров, вызвать в ответ на чье-либо сообщение либо
        передать конкретный список пользователей @user1 @user2 @user3.
        Возвращает информацию по указанным пользователям в виде::

            Это 👤Оценочка
            🤘Δeus Σx Tower
            🎗 Капрал [▒▒🔰▒▒]
            📯 Неизвестный
            🆔: 308522294
            🗓Стаж: 40 дн.
            ⏱В последний раз замечен: 2020-06-03 21:41:20

        """
        users = users or ([update.invoker] if not update.command.argument else [])
        if not users:
            return

        for user in users:
            self._show_user_info(user, update.effective_chat_id, update.invoker.is_admin)

    def _update_player(self, player: Player, profile: Profile, chat_id: int):
        stats = profile.stats
        rewards = 0
        total = 0

        output: List[str] = ["<b>Награда за прокачку</b>"]
        for idx, key in enumerate(KEY_STATS):
            prev_stat_value = getattr(player, key)
            stat_value = getattr(stats, key)
            delta = stat_value - prev_stat_value
            if delta <= 0:
                continue

            total += delta
            output.append(f"\t\t[{ICONS_STATS[idx]}]\t" f"{prev_stat_value}\t->\t{stat_value} " f"(+{delta})")

            rewards += delta * REWARDS_STATS[key]

        prev_combat_power = player.sum_stat
        player.add_stats(
            hp=stats.hp,
            attack=stats.attack,
            defence=stats.defence,
            power=stats.power,
            accuracy=stats.accuracy,
            oratory=stats.oratory,
            agility=stats.agility,
            stamina=stats.stamina,
            dzen=stats.dzen,
        )

        if profile.gang_name:
            if not (gang := Group.get_or_none(name=profile.gang_name, type="gang")):
                gang = Group.create(name=profile.gang_name, type="gang")

            is_active = gang.is_active
            if gang.parent and gang.parent.is_active:
                is_active = True

            player.gang = gang
            player.is_active = is_active

        player.nickname = profile.nickname
        player.fraction = profile.fraction
        player.save()

        self.message_manager.send_message(chat_id=chat_id, text="Статистика сохранена")

        if rewards <= 0:
            return

        if total > 0:
            output.append(f"\n\t\t[📯] {prev_combat_power}\t->\t{total + prev_combat_power} (+{total})")

        output.append(
            f"<code>Последние обновление "
            f"<b>{dt.distance_of_time_in_words(player.last_update, to_time=time.time())}</b></code>"
        )

        self.message_manager.send_message(chat_id=chat_id, text="\n".join(output))

    def _save_stats(self, update: PlayerParseResult):
        message = update.telegram_update.message
        profile = update.profile

        if update.invoker.username is None:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text="У тебя не указан юзернейм. Зайди в настройки своего телеграмм-аккаунта и укажи."
                "\nА то мы с тобой не сможем познакомиться)",
            )

        if update.player is None and profile.telegram_user_id is None:
            return self.message_manager.send_message(chat_id=message.chat_id, text="Пришли мне полный ПИП-БОЙ")

        if profile.telegram_user_id and profile.telegram_user_id != update.invoker.user_id:
            return self.message_manager.send_message(chat_id=message.chat_id, text="Это не твой ПИП-БОЙ")

        if update.player is None and update.timedelta > datetime.timedelta(minutes=5):
            return self.message_manager.send_message(chat_id=message.chat_id, text="А можно ПИП-БОЙ посвежее?")

        if (
            update.player
            and update.player.nickname != profile.nickname
            and update.invoker.user_id != profile.telegram_user_id
        ):
            return self.message_manager.send_message(chat_id=message.chat_id, text="Пришли мне полный ПИП-БОЙ")

        if update.player and update.player.last_update >= update.date:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text="ПИП-БОЙ слишком стар для обновления статистики",
            )

        if update.player is None:
            player = Player.get_or_none(nickname=profile.nickname)
            if player is None:
                player = Player.create(
                    telegram_user=update.invoker,
                    nickname=profile.nickname,
                    settings=Settings.create(),
                )
                created = True
            else:
                created = False
        else:
            created = False
            player = update.player

        if profile.telegram_user_id == update.invoker.user_id and profile.nickname != player.nickname:
            self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Раньше тебя звали {player.nickname}, теперь тебя зовут {profile.nickname}",
            )

        self._update_player(player, profile, message.chat_id)

        if not created:
            return

        self.message_manager.send_message(chat_id=message.chat_id, text="Я тебя запомнил")

        if not player.is_active:
            self.message_manager.send_message(
                chat_id=message.chat_id,
                text="Ты, кстати, не активирован, обратись к @DeusDeveloper",
            )

    @get_players(include_reply=True, break_if_no_players=False)
    @permissions(or_(is_admin, self_))
    def _progress(self, update: InnerUpdate, players: List[Player]):
        players = players or ([update.player] if update.command.argument == "" else [])
        if not players:
            return

        for player in players:
            self._show_player_progress(player, update.effective_chat_id)

    def _show_player_progress(self, player: Player, chat_id: int):
        dates_query = (
            PlayerStatHistory.select(peewee.fn.MAX(PlayerStatHistory.time).alias("maxtime"))
            .where(PlayerStatHistory.player == player)
            .group_by(peewee.fn.DATE(PlayerStatHistory.time))
            .order_by(peewee.fn.DATE(PlayerStatHistory.time).desc())
            .limit(10)
            .alias("dates_query")
        )

        stats_history = (
            PlayerStatHistory.select()
            .join(dates_query, on=(PlayerStatHistory.time == dates_query.c.maxtime))
            .where(PlayerStatHistory.player == player)
            .order_by(PlayerStatHistory.time)
        )

        if not stats_history:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f"Я поражён.... У игрока {player.mention_html()} " f"нет истории прокачки....",
            )

        times = []
        stats = {key: None for key in KEY_STATS}

        for history in stats_history:
            times.append(history.time.timestamp() * 1000)
            for key in constants.KEY_STATS.keys():
                stat = stats.get(key)
                if stat is None:
                    stat = []

                stat.append(getattr(history, key))
                stats[key] = stat

        dataset = []

        for KEY_STAT, label in constants.KEY_STATS.items():
            dataset.append(
                {
                    "label": label,
                    "color": constants.COLOR_BY_KEY_STAT.get(KEY_STAT, "rgb(255, 99, 132)"),
                    "dataset": [{"unix": times[idx], "y": value} for idx, value in enumerate(stats[KEY_STAT])],
                }
            )

        text = self._progress_template.render(dataset=dataset, nickname=player.nickname)

        with NamedTemporaryFile() as tmp:
            open(tmp.name, "w", encoding="utf-8").write(text)

            self.message_manager.bot.send_document(
                chat_id=chat_id, document=open(tmp.name, "rb"), filename="stats.html"
            )
