import datetime
import functools
import re
from collections import Counter, defaultdict
from typing import Optional, List, Set, Dict

import peewee
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
from core import EventManager, MessageManager, InnerUpdate, InnerHandler, UpdateFilter, CommandFilter
from decorators import command_handler, permissions, get_invoker_raid
from decorators.permissions import is_admin, is_developer
from decorators.users import get_players
from models import Group, RaidAssign, Player, TelegramUser, RaidsInterval, GroupPlayerThrough, Radar
from models.raid_assign import RaidStatus
from modules import BasicModule
from modules.statbot.parser import PlayerParseResult
from utils import get_next_raid_date, get_last_raid_date, get_when_raid_text, ExcelManager
from utils.functions import CustomInnerFilters
from wasteland_wars import constants


class RaidkmIcons:
    ON_PLACE = '🏕'
    CONFIRMED = '👊'
    MISSED = '💥'
    SLOW = '🐌'
    FAST = '🏃‍‍'
    UNKNOWN = '❓'
    ACCEPTED = '👍'
    IN_PROCESS = '👊'


RAIDKM_ICONS = {
    RaidStatus.ASSIGNED: '🌚',
    RaidStatus.CONFIRMED: "Ты точно подтвердил участие в рейде.",
    RaidStatus.REJECTED: '❌',
    RaidStatus.IN_PROCESS: 'Ты подтвердил участие в рейде. Никуда не уходи до его начала',
}
RAIDSTATUS_ICONS = {
    RaidStatus.ON_PLACE: '🏕',
    RaidStatus.CONFIRMED: '👊',
    RaidStatus.UNKNOWN: '❓',
    RaidStatus.ACCEPTED: '🏃‍‍',
    RaidStatus.IN_PROCESS: '👊',
}


class RaidModule(BasicModule):
    """ 
    Raids stuff
    """
    module_name = 'raid'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid'),
                self._assign_players,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('sendpin'),
                self._sendpin,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('when_raid'),
                self._when_raid,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidkm'),
                self._get_players_km,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidkm_n'),
                self._get_players_km_new,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_masterpin'),
                self._masterpin(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_masterpin_l'),
                self._masterpin(show_last_raid=True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_short'),
                self._raidshort(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_short_l'),
                self._raidshort(show_last_raid=True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('my_raidpin'),
                self._my_raidpin,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_accept'),
                self._raidpin_accept,
                [CustomInnerFilters.from_player, CustomInnerFilters.private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_reject'),
                self._raidpin_reject,
                [CustomInnerFilters.from_player, CustomInnerFilters.private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_help'),
                self._raidpin_help,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_su'),
                self._raid_status_update,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_statuses'),
                self._raid_status_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_excel'),
                self._raid_excel_report,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                UpdateFilter('profile'),
                self._update_from_profile
            )
        )
        self.add_inner_handler(
            InnerHandler(
                (UpdateFilter('profile') & UpdateFilter('raid')),
                self._confirm_raid_from_profile
            )
        )

        self._re_assign_group_menu = re.compile(r'raid_(?P<km>\d+)$')
        self._re_assign_player_menu = re.compile(r'raid_(?P<km>\d+)_(?P<group>\d+)$')

        self._re_assign_group = re.compile(r'(?P<unraid>un)?raid_group_(?P<km>\d+)_(?P<group>\d+)$')
        self._re_assign_player = re.compile(r'(?P<unraid>un)?raid_player_(?P<km>\d+)_(?P<player>\d+)_(?P<group>\d+)$')

        self._re_id = re.compile(r'#(?P<id>\d+)', re.MULTILINE)
        self._re_username = re.compile(r'@(?P<username>\w+)', re.MULTILINE)

        self._re_raidkm_type = re.compile(r'((?P<km>\d+)|(?P<group>\w+))')

        super().__init__(event_manager, message_manager, dispatcher)

        self.event_manager.scheduler.add_job(self._raids21_z, 'cron', day_of_week='mon-sun', hour=1, minute=1)

    def _raids21_z(self):
        last = get_last_raid_date()
        interval = RaidsInterval.interval_by_date(last, 0)
        if interval is not None:
            return

        last_id = RaidsInterval.select(RaidsInterval.id).order_by(RaidsInterval.id.desc()).limit(1).scalar()
        RaidsInterval.create(
            id=last_id + 1,
            start_date=last,
            last_date=last + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
        )

    def _raidpin_help(self, update: InnerUpdate):
        """Инструкция по пользованию пином"""
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text='''Попроси админов добавить этот триггер'''
        )

    @permissions(is_admin)
    def _raid_status_ls(self, update: InnerUpdate):
        text = (
            'Список рейд статусов\n'
            'Название -> Индекс\n\n'
        )
        for value, key in RaidStatus.dict().items():
            text += f'<b>{key}</b> -> <code>{value}</code>\n'

        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<date>\d{2}\.\d{2}\.\d{4}-\d{2})\s+(?P<status_id>([+-])?\d{1,3})'),
        argument_miss_msg='Пришли сообщение в формате "/raid_su дд.мм.гггг-чч Статус @User1 @User2"\nСписок статусов: '
                          '/raid_statuses'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _raid_status_update(self, update: InnerUpdate, match, players):
        message = update.telegram_update.message

        time = datetime.datetime.strptime(match.group('date'), '%d.%m.%Y-%H')
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), 0)
        if not (interval.start_date <= time <= interval.last_date):
            return message.reply_text('Этот рейд был вне текущего интервала рейдов!')

        status_id = int(match.group('status_id'))
        status_name = RaidStatus.dict().get(status_id)
        if status_name is None:
            return message.reply_text(f'Статуса с ID = {status_id} не существует\nСписок статусов: /raid_statuses')

        query = RaidAssign.update(
            {
                RaidAssign.status_id: status_id,
                RaidAssign.is_reported: False
            }
        ).where(
            (RaidAssign.player_id << [player.id for player in players]) &
            (RaidAssign.status_id != status_id) &
            (RaidAssign.time == time)
        )
        updated_rows = query.execute()

        def formatter(rows: int = 0):
            if rows == 0 or rows > 5:
                return 'ов'
            elif rows == 1:
                return ''
            elif 1 < rows < 5:
                return 'а'
            else:
                return ''

        return message.reply_text(
            f'Обновил <b>{updated_rows}</b> статус{formatter(updated_rows)} '
            f'рейда <b>{time}</b> на {status_name} ( ID{status_id} )'
        )

    @command_handler(
        regexp=re.compile(r'(?P<km>\d+)\s*(?P<groups>.+)?'),
        argument_miss_msg='Пришли сообщение в формате Км имя/алиас группы'
    )
    @get_players(include_reply=True, break_if_no_players=False)
    def _assign_players(self, update: InnerUpdate, match, players):
        """
        Назначение группы игроков на рейд.
        Возможно назначение только на следующий рейд.
        Принимаются сообщения в формате 'Км имя/алиас группы'
        """
        if len(update.player.liders) == 0:
            return self.message_manager.send_message(
                chat_id=update.invoker.chat_id,
                text='Нет доступа!'
            )

        message = update.telegram_update.message
        km = match.group('km')

        if message.chat_id == settings.GOAT_ADMIN_CHAT_ID:
            chat_id = settings.GOAT_ADMIN_CHAT_ID
        else:
            chat_id = update.invoker.chat_id

        if not km.isdigit():
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Пришли км, на который отправить группу, числом'
            )
        else:
            km = int(km)

        if km not in constants.raid_kms:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text='Такой рейдовой локации не существует'
            )

        next_raid_time = get_next_raid_date()
        pls = []
        nicknames = []
        if players:
            access = []
            for group in update.player.liders:
                for pl in group.members.filter((Player.is_active == True)):
                    access.append(pl.nickname)

            for player in players:
                if player.nickname not in access:
                    continue

                pls.append(player.mention_html())
                nicknames.append(f'@{player.telegram_user.username}')
                RaidAssign.assign(next_raid_time, player, km)

        groups = []
        error_groups = []
        for group_name in (match.group('groups') or '').split():
            group = Group.get_by_name(group_name)

            if not group:
                if group_name not in nicknames:
                    error_groups.append(group_name)
                continue

            if update.player not in group.liders:
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'Ты не являешься лидером группы "{group_name}"'
                )
                continue

            groups.append(group.name)
            for player in group.members.filter((Player.is_active == True)):
                RaidAssign.assign(next_raid_time, player, km)

        if error_groups:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Я не знаю групп: {"; ".join(error_groups)}'
            )

        if groups or pls:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'{", ".join(groups + pls)} в '
                     f'{next_raid_time.time()} рейдят {km}км'
            )
        else:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Кажется ты никого не послал на рейд.'
            )

    def _when_raid(self, update: InnerUpdate):
        """Выдает, через сколько времени будет следующий рейд"""
        text = get_when_raid_text()
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    def _sendpin(self, update: InnerUpdate):
        """
        Посылает сообщение в личку с указанием км, на который надо идти.
        Сообщение не будет отправлено тем, кто уже подтвердил участие в рейде и тем, кто уже получил его
        """
        message = update.telegram_update.message

        if len(update.player.liders) == 0:
            return self.message_manager.send_message(
                chat_id=update.invoker.chat_id,
                text='Нет доступа!'
            )

        access = []
        for group in update.player.liders:
            for member in group.members.filter((Player.is_active == True)):
                if member not in access:
                    access.append(member)

        players: List[Player] = []

        if update.command.argument == '':
            players = access
        else:
            parts = update.command.argument.split()
            users: List[Optional[TelegramUser]] = []
            kms: Set[int] = set()
            group_names: Set[str] = set()

            for part in parts:
                if part.isdigit():
                    kms.add(int(part))
                elif match := self._re_username.search(part):
                    telegram_user = TelegramUser.get_by_username(match.group('username'))
                    users.append(telegram_user)
                elif match := self._re_id.search(part):
                    telegram_user = TelegramUser.get_by_user_id(int(match.group('id')))
                    users.append(telegram_user)
                else:
                    group_names.add(part)

            for group_name in group_names:
                group = Group.get_by_name(group_name)
                if (
                    group is None or
                    group not in update.player.liders
                ):
                    continue

                for member in group.members:
                    if member in players:
                        continue
                    players.append(member)

            for telegram_user in users:
                if telegram_user is None:
                    continue

                if not telegram_user.player:
                    continue

                player = telegram_user.player.get()
                if player in players:
                    continue

                if player not in access:
                    continue

                players.append(player)

            for km in kms:
                for pin in RaidAssign.next_raid_players(status=RaidStatus.UNKNOWN, km=km):
                    player = pin.player
                    if (
                        player in players or
                        player not in access
                    ):
                        continue
                    players.append(player)

        mentions: List[str] = []
        for player in players:
            raid_assigned = player.actual_raid
            if not (raid_assigned and raid_assigned.status_id == RaidStatus.UNKNOWN):
                continue

            mentions.append(player.mention_html())
            raid_assigned.status = RaidStatus.HASNOTSEEN
            raid_assigned.last_update = update.date
            raid_assigned.save()

            chat_id = player.telegram_user.chat_id if not settings.DEBUG else update.effective_chat_id
            if not (player.settings.pings['sendpin'] if player.settings else True):
                continue

            self.message_manager.send_message(
                chat_id=chat_id,
                is_queued=True,
                text=self.get_assigned_message(raid_assigned)
            )

        if message.chat_id == settings.GOAT_ADMIN_CHAT_ID:
            chat_id = settings.GOAT_ADMIN_CHAT_ID
        else:
            chat_id = update.invoker.chat_id

        if not mentions:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text='Пины еще не назначены или уже все отправлены'
            )

        return self.message_manager.send_message(
            chat_id=chat_id,
            text=f'Пины отправлены игрокам ({len(mentions)}):\n\n' + ', '.join(mentions)
        )

    @get_invoker_raid
    def _my_raidpin(self, update: InnerUpdate, raid_assigned):
        """Посмотреть свой назначенный рейд"""
        invoker = update.invoker
        if raid_assigned.status == RaidStatus.HASNOTSEEN:
            raid_assigned.status = RaidStatus.ASSIGNED
            raid_assigned.last_update = update.date
            raid_assigned.save()

        self.message_manager.send_message(
            chat_id=invoker.chat_id,
            text=raid_assigned.get_msg()
        )
        if raid_assigned.km_assigned in constants.raid_kms_tz:
            self.message_manager.bot.send_photo(
                photo=open(f'static/timings/raid{raid_assigned.km_assigned}_timings.jpg', 'rb'),
                caption='Тайминги',
                chat_id=invoker.chat_id
            )

    @get_invoker_raid
    def _raidpin_accept(self, update: InnerUpdate, raid_assigned):
        """Принять назначенный рейд"""
        invoker = update.invoker
        if raid_assigned.status == RaidStatus.HASNOTSEEN:
            return self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text=self.get_assigned_message(raid_assigned)
            )
        elif raid_assigned.status >= RaidStatus.ACCEPTED:
            return self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text='Ты уже принял назначение на рейд'
            )

        raid_assigned.status = RaidStatus.ACCEPTED
        raid_assigned.last_update = update.date
        raid_assigned.save()

        self.message_manager.send_message(
            chat_id=invoker.chat_id,
            text=raid_assigned.get_msg()
        )

    @get_invoker_raid
    def _raidpin_reject(self, update: InnerUpdate, raid_assigned):
        """Отказаться от назначенного рейда"""
        invoker = update.invoker
        if raid_assigned.status == RaidStatus.HASNOTSEEN:
            return self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text=self.get_assigned_message(raid_assigned)
            )
        elif raid_assigned.status == RaidStatus.REJECTED:
            return self.message_manager.send_message(
                chat_id=invoker.chat_id,
                text='Ты уже отказался от рейда'
            )

        raid_assigned.status = RaidStatus.REJECTED
        raid_assigned.last_update = update.date
        raid_assigned.save()

        self.message_manager.send_message(
            chat_id=settings.GOAT_ADMIN_CHAT_ID,
            text=f'Игрок {update.player.mention_html()} отказался '
                 f'от пина [{raid_assigned.km_assigned}]'
        )

        self.message_manager.send_message(
            chat_id=invoker.chat_id,
            text=raid_assigned.get_msg()
        )

    @command_handler()
    def _get_players_km(self, update: InnerUpdate):
        """Возвращает положение игроков в пустоши для следующего рейда. Необходимо указать группу либо рейд-точку"""
        message = update.telegram_update.message
        next_raid_time = get_next_raid_date()
        speed_mapper = {
            RaidkmIcons.UNKNOWN: RaidkmIcons.FAST,
            RaidkmIcons.MISSED: RaidkmIcons.FAST
        }

        if message.chat_id == settings.GOAT_ADMIN_CHAT_ID:
            chat_id = settings.GOAT_ADMIN_CHAT_ID
        else:
            chat_id = update.invoker.chat_id

        access = []
        for group in update.player.liders:
            access.extend(group.members.filter((Player.is_active == True)))
        if not (access or update.invoker.is_admin):
            return self.message_manager.send_message(chat_id=chat_id, text='Нет доступа.')

        if not update.command.argument:
            raid_counter = defaultdict(Counter)
            for raid_assigned in RaidAssign.filter(RaidAssign.time == next_raid_time):
                if not ((raid_assigned.player in access) or update.invoker.is_admin):
                    continue
                if raid_assigned.status >= RaidStatus.ACCEPTED:
                    raid_counter[raid_assigned.km_assigned][RaidkmIcons.ACCEPTED] += 1
                raidpin_status = self.get_raidpin_status(raid_assigned)
                status = speed_mapper.get(raidpin_status, raidpin_status)
                raid_counter[raid_assigned.km_assigned][status] += 1

            def get_counter_formatted(status, km):
                return f'{status}{raid_counter[km][status]}'

            raid_km_str = "\n".join(f'{x}км ({get_counter_formatted(RaidkmIcons.ACCEPTED, x)}): '
                                    f'{get_counter_formatted(RaidkmIcons.ON_PLACE, x)} | '
                                    f'{get_counter_formatted(RaidkmIcons.IN_PROCESS, x)} | '
                                    f'{get_counter_formatted(RaidkmIcons.FAST, x)}'
                                    for x in sorted(raid_counter))

            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Рейд-точки на <b>{next_raid_time.time().hour}:00</b> мск:\n\n'
                     f'{raid_km_str}'
            )

        for arg in update.command.argument.split():
            res = []
            group = Group.get_by_name(arg)
            if group and group in update.player.liders:
                for player in group.members:
                    if player.actual_raid:
                        res.append(self.format_raid_km_line(player))
            elif arg.isdigit() and int(arg) in constants.raid_kms:
                for raid_assigned in RaidAssign.select().where(RaidAssign.km_assigned == int(arg),
                                                               RaidAssign.time == next_raid_time):
                    res.append(self.format_raid_km_line(raid_assigned.player))

            self.message_manager.send_message(
                chat_id=message.chat_id,
                text='\n'.join(sorted(res))
            )

    @permissions(is_admin)
    @get_players(include_reply=True, break_if_no_players=False, callback_message=False)
    @command_handler()
    def _get_players_km_new(self, update: InnerUpdate, players: List[Player]):
        message = update.telegram_update.message
        is_last = False
        raid_time = get_last_raid_date() if is_last else get_next_raid_date()
        argument_parts = update.command.argument.split()

        radar_query_dates = Radar.select(Radar.player_id, peewee.fn.MAX(Radar.time).alias('MAXDATE')).group_by(
            Radar.player_id).alias('radar_max')

        radar_query = Radar.select(Radar.km, Radar.player_id, Radar.time) \
            .join(radar_query_dates,
                  on=(Radar.player_id == radar_query_dates.c.player_id) & (Radar.time == radar_query_dates.c.MAXDATE))

        time_30 = datetime.datetime.now() - datetime.timedelta(minutes=30)
        time_5 = datetime.datetime.now() - datetime.timedelta(minutes=5)
        time_delta_case = peewee.Case(None, (
            (radar_query.c.time < time_30, '⏳'),
            (radar_query.c.time > time_5, '🆕'),
            (radar_query.c.time.between(time_30, time_5), '🆗')
        ))
        status_case = peewee.Case(None, (
            (RaidAssign.status_id << [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED], 0),
            (RaidAssign.km_assigned == radar_query.c.km, 1),
            (radar_query.c.km == 0, 4),
            (RaidAssign.km_assigned > radar_query.c.km, 2)
        ), 3)

        _players = Player.select(
            Player.nickname,
            Player.telegram_user_id,
            RaidAssign.km_assigned,
            radar_query.c.km,
            time_delta_case.alias('delta'),
            Player.sum_stat,
            Player.dzen,
            RaidAssign.status_id,
            status_case.alias('informer')
        ) \
            .join(GroupPlayerThrough, on=(GroupPlayerThrough.player_id == Player.id)) \
            .join(Group, on=(Group.id == GroupPlayerThrough.group_id)) \
            .join(RaidAssign, on=(RaidAssign.player_id == Player.id)) \
            .join(radar_query, on=(radar_query.c.player_id == Player.id)) \
            .where(
            (
                ((Group.name << argument_parts) | (Group.alias << argument_parts))
                | (RaidAssign.km_assigned << [int(x) for x in argument_parts if x.isdigit()])
                | (Player.id << [p.id for p in players])
            ) & (RaidAssign.time == raid_time)
        ) \
            .distinct() \
            .order_by(RaidAssign.km_assigned.desc(), status_case.asc(), radar_query.c.km.desc(), Player.sum_stat.desc(),
                      Player.dzen.desc())

        formatter_report = f'<b>Рейд {raid_time}</b>\n\n'

        statuses = ['👊', '🏕', '🏃‍‍', '❔', '😴']

        raid_counter = Counter()
        power_counter = Counter()
        last_km = None
        for _player in _players.dicts():
            km_assigned, km_radar, delta, chat_id, nickname, dzen, status_id, informer = _player['km_assigned'], \
                _player['km'], _player['delta'], _player['telegram_user'], _player['nickname'], _player['dzen'], \
            _player[
                'status_id'], _player['informer']
            if last_km is None:
                last_km = km_assigned
            if last_km != km_assigned:
                last_km = km_assigned
                formatter_report += f'🎓{power_counter["sum_stat"]}к на {power_counter["peoples"]} человек\n\n'
                power_counter = Counter()

            emojie = '🚷' if km_assigned in constants.raid_kms_tz else '🙀'
            sum_stat = round(_player['sum_stat'] / 1000, 1)
            emojie_speed = statuses[informer]
            raid_counter[emojie_speed] += 1
            power_counter['sum_stat'] += sum_stat
            power_counter['peoples'] += 1

            formatter_report += (f'{emojie}{km_assigned:02}|{emojie_speed}{km_radar:02}|{delta}|🎓{sum_stat:03.1f}|'
                                 f'🏵{dzen:02}|{mention_html(chat_id, nickname)}\n')
        formatter_report += f'🎓{power_counter["sum_stat"]:.1f}к на {power_counter["peoples"]} человек\n\n'

        formatter_report += (
            'Аналитика:\n'
            f'👊Прожаты: {raid_counter["👊"]}\n'
            f'🏕На точке: {raid_counter["🏕"]}\n'
            f'🏃‍‍В пути: {raid_counter["🏃‍‍"]}\n'
            f'❔Потерялись: {raid_counter["❔"]}\n'
            f'😴Спят: {raid_counter["😴"]}'
        )
        return message.reply_text(formatter_report, parse_mode='HTML')

    def _raidshort(self, show_last_raid: bool = False):
        @permissions(is_admin)
        @command_handler()
        def handler(self, update: InnerUpdate):
            message = update.telegram_update.message
            kms = update.command.argument.split()
            if not kms:
                return self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=f'Пришли команду в формате: /raidpin_short{"_l" if show_last_raid else ""} КМ'
                )

            def format_line(raid_status):
                if raid_power[raid_status] > 0:
                    return (f': <b>{raid_counts[raid_status]}</b> [{int(raid_counts[raid_status] / counts * 100)}%]'
                            f'({int(raid_power[raid_status] / 1000)}к💪)')
                return ''

            for arg in kms:
                raid_power = defaultdict(int)
                raid_counts = defaultdict(int)
                time = get_last_raid_date() if show_last_raid else get_next_raid_date()
                sum_stat = 0
                counts = 0
                for raid_assign in RaidAssign.next_raid_players(km=int(arg), time=time):
                    raid_power[raid_assign.status_id] += raid_assign.player.sum_stat
                    raid_counts[raid_assign.status_id] += 1
                    sum_stat += raid_assign.player.sum_stat
                    counts += 1
                lines = [
                    f'ПИН на <b>{arg}км</b>\n(<b>{time})</b>',
                    f'😑Игнорируют{format_line(RaidStatus.HASNOTSEEN)}',
                    f'🌚Посмотрели{format_line(RaidStatus.ASSIGNED)}',
                    f'🐌Уже вышли{format_line(RaidStatus.ACCEPTED)}',
                    f'🏕Пришли{format_line(RaidStatus.ON_PLACE)}',
                    f'👊Отметились{format_line(RaidStatus.IN_PROCESS)}'
                ]
                if time < get_next_raid_date():
                    lines.append(f'👊Подтвердили{format_line(RaidStatus.CONFIRMED)}')
                lines.append(f'❌Отказались{format_line(RaidStatus.REJECTED)}')
                if counts > 0:
                    efficiency_count = int(
                        (raid_counts[RaidStatus.IN_PROCESS] + raid_counts[RaidStatus.CONFIRMED]) * 100 / counts
                    )
                    lines.append(
                        f'Эффективность: <b>{efficiency_count}%</b>'
                        f'[{raid_counts[RaidStatus.IN_PROCESS] + raid_counts[RaidStatus.CONFIRMED]}/{counts}ч]')

                    efficiency_power = int(
                        (raid_power[RaidStatus.IN_PROCESS] + raid_power[RaidStatus.CONFIRMED]) / sum_stat * 100
                    )

                    lines.append(
                        f'Эффективность: <b>{efficiency_power}%</b>'
                        f'[{int((raid_power[RaidStatus.IN_PROCESS] + raid_power[RaidStatus.CONFIRMED]) / 1000)}к'
                        f'/{int(sum_stat / 1000)}к💪]'
                    )

                message_text = '\n'.join(lines)

                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=message_text
                )

        return functools.partial(handler, self)

    def _masterpin(self, show_last_raid: bool = False):
        @command_handler()
        def handler(self, update: InnerUpdate):
            """Счетчик по рейд статусам"""
            message = update.telegram_update.message

            if message.chat_id == settings.GOAT_ADMIN_CHAT_ID:
                chat_id = settings.GOAT_ADMIN_CHAT_ID
            else:
                chat_id = update.invoker.chat_id

            access = []
            for group in update.player.liders:
                access.extend(group.members)

            if not access:
                return self.message_manager.send_message(
                    chat_id=chat_id,
                    text='Нет доступа.'
                )

            def format_line(raid_status):
                return f'<b>{len(raid_users[raid_status])}</b>[{raid_power[raid_status]}]: ' \
                       f'{"; ".join(raid_users[raid_status])}' if raid_users[raid_status] else ''

            kms = update.command.argument.split()

            if not kms:
                return self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=f'Пришли команду в формате: /raidpin_masterpin{"_l" if show_last_raid else ""} КМ'
                )

            for arg in kms:
                raid_power = defaultdict(int)
                raid_users = defaultdict(list)

                time = get_last_raid_date() if show_last_raid else get_next_raid_date()

                for raid_assign in RaidAssign.next_raid_players(km=int(arg), time=time):
                    if not ((raid_assign.player in access) or update.invoker.is_admin):
                        continue

                    player = raid_assign.player
                    raid_power[raid_assign.status] += player.sum_stat
                    raid_users[raid_assign.status].append(f"{player.mention_html()}")

                lines = [
                    f'ПИН на <b>{arg}км</b>\n(<b>{time})</b>',
                    f'😑Еще не смотрели {format_line(RaidStatus.HASNOTSEEN)}',
                    f'🌚Посмотрели и все {format_line(RaidStatus.ASSIGNED)}',
                    f'🐌Уже вышли {format_line(RaidStatus.ACCEPTED)}',
                    f'🏕Пришли на точку {format_line(RaidStatus.ON_PLACE)}',
                    f'👊Отметились на точке {format_line(RaidStatus.IN_PROCESS)}'
                ]
                if time < get_next_raid_date():
                    lines.append(f'👊Подтвердили участие {format_line(RaidStatus.CONFIRMED)}')

                lines.append(f'❌Отказались от участия {format_line(RaidStatus.REJECTED)}')
                message_text = '\n'.join(lines)

                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=message_text
                )

        return functools.partial(handler, self)

    @staticmethod
    def get_raidpin_status(player_raid: RaidAssign) -> Optional[str]:
        if not player_raid:
            return

        if not player_raid.km_real:
            return RaidkmIcons.UNKNOWN

        if player_raid.km_real == player_raid.km_assigned:
            if player_raid.status == RaidStatus.IN_PROCESS:
                return RaidkmIcons.IN_PROCESS
            return RaidkmIcons.ON_PLACE

        return RaidkmIcons.FAST

    def format_raid_km_line(self, player: Player) -> str:
        line = []
        speed = self.get_raidpin_status(player.actual_raid)
        if player.actual_raid.km_real is not None:
            line.append(f'{str(player.actual_raid.km_real).zfill(2)}км')

        line.append(speed)
        line.append(player.nickname)
        return ' '.join(line)

    def _confirm_raid_from_profile(self, update: PlayerParseResult):
        message = update.telegram_update.message
        player = update.player
        if not player:
            return

        raid = update.raid
        if not raid:
            return

        if message.date - raid.time > datetime.timedelta(hours=8):
            return

        raid_assign = player.raid_near_time(raid.time - datetime.timedelta(seconds=5))
        if not (raid_assign and raid_assign.status == RaidStatus.IN_PROCESS):
            return

        raid_assign.status = RaidStatus.CONFIRMED
        raid_assign.last_update = update.date
        raid_assign.save()
        
        self.message_manager.send_message(
            chat_id=message.chat_id,
            text='✅Вопрос закрыт!✅\n'
                 'Ты окончательно подтвердил своё участие на предыдущем рейде.\n'
                 f'<b>{raid_assign.time}</b>'
        )

    def _update_from_profile(self, update: PlayerParseResult):
        message = update.telegram_update.message
        player = update.player
        if not player:
            return

        raid_assign = player.raid_near_time(update.date)
        if not (raid_assign and raid_assign.last_update < update.date):
            return

        if (
            raid_assign.status not in (RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED) and
            not raid_assign.is_reported and
            raid_assign.km_assigned == update.profile.distance
        ):
            if update.profile.stand_on_raid:
                raid_assign.status = RaidStatus.IN_PROCESS
                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text='✊Вижу твой кулак!✊\n'
                         'Ты подтвердил участие в рейде, дождись результатов.\n'
                         f'<b>{raid_assign.time}</b>'
                )

            else:
                raid_assign.status = RaidStatus.ON_PLACE
                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text='❗️Покажи кулачок, боец!❗️\n'
                         'Ты на точке, но не записался на рейд.\n'
                         f'<b>{raid_assign.time}</b>'
                )

        elif raid_assign.status == RaidStatus.IN_PROCESS and raid_assign.km_assigned != update.profile.distance:
            raid_assign.status = RaidStatus.LEFTED
            self.message_manager.send_message(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                text=f'Игрок {raid_assign.player.mention_html()} покинул '
                     f'свою рейд точку [{raid_assign.km_assigned}]\n'
                     f'<b>{raid_assign.time}</b>'
            )

            self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Эй, стой! Куда с рейда убежал?\n'
                     f'РЕЙД НА {raid_assign.km_assigned}км. !!!ОДУМАЙСЯ!!!\n'
                     f'<b>{raid_assign.time}</b>'
            )

        raid_assign.last_update = update.date
        raid_assign.save()

    @permissions(is_admin)
    @command_handler()
    def _raid_excel_report(self, update: InnerUpdate):
        players: List[Player] = []

        for group_name in update.command.argument.split():
            group = Group.get_by_name(group_name)
            if group is None:
                continue

            for member in group.members:
                if member in players:
                    continue
                players.append(member)

        player_ids: List[int] = [player.id for player in players]

        query = (
            RaidAssign.select()
            .where(
                RaidAssign.player_id << player_ids
            )
        )

        raid_assign_emoji_by_status: Dict[RaidStatus, int] = {
            RaidStatus.CONFIRMED: 2,
            RaidStatus.IN_PROCESS: 2,
            RaidStatus.LEFTED: -2,
            RaidStatus.ON_PLACE: 1,
            RaidStatus.ACCEPTED: 0,
            RaidStatus.HASNOTSEEN: -1,
            RaidStatus.REJECTED: -2
        }

        raid_statuses_by_time: Dict[datetime.datetime, Dict[int, int]] = defaultdict(dict)
        for raid_assign in query:
            status_emoji = raid_assign_emoji_by_status.get(raid_assign.status, 0)
            raid_statuses_by_time[raid_assign.time][raid_assign.player_id] = status_emoji

        if not raid_statuses_by_time:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text='Нет рейдов для построения статистики'
            )

        raid_times_sorted = sorted(raid_statuses_by_time.keys())

        records: Dict[int, List[Optional[int]]] = defaultdict(list)
        for raid_assign_time in raid_times_sorted:
            raid_statuses = raid_statuses_by_time[raid_assign_time]
            for player_id in player_ids:
                status_emoji = raid_statuses.get(player_id)
                records[player_id].append(status_emoji)

        manager = ExcelManager()
        manager.write_row(
            'Никнейм',
            'Telegram User ID',
            *raid_times_sorted
        )

        for player in players:
            player_raid_statuses = records.get(player.id)
            if player_raid_statuses is None:
                player_raid_statuses = []

            manager.write_row(
                player.nickname,
                player.telegram_user_id,
                *player_raid_statuses
            )

        with manager.save(resize=True) as fh:
            return update.telegram_update.effective_message.reply_document(
                document=open(fh.name, 'rb'),
                filename='статистика.xlsx'
            )

    @staticmethod
    def get_assigned_message(raid_assigned: RaidAssign) -> str:
        return 'Тебе выдан ПИН\n' \
               'Внимание на /my_raidpin\n' \
               f'{raid_assigned.time}'
