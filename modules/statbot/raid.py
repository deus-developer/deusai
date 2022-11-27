import datetime
import functools
import re
from collections import (
    Counter,
    defaultdict
)

import peewee
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode
)
from telegram.ext import (
    CallbackQueryHandler,
    Dispatcher
)
from telegram.utils.helpers import mention_html

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
    get_invoker_raid,
    permissions
)
from decorators.log import lead_time
from decorators.log import log
from decorators.permissions import (
    is_admin,
    is_developer
)
from decorators.update import inner_update
from decorators.users import (
    get_player,
    get_players
)
from models import (
    Feedback,
    Group,
    GroupPlayerThrough,
    Player,
    Radar,
    RaidAssign,
    RaidsInterval,
    TelegramUser,
    Vote,
    VoteAnswer
)
from models.raid_assign import RaidStatus
from modules import BasicModule
from modules.statbot.parser import PlayerParseResult
from utils import (
    last_raid,
    next_raid
)
from utils.functions import CustomInnerFilters
from ww6StatBotWorld import Wasteland


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


class RaidModule(BasicModule):  # TODO: Провести оптимизацию
    """ 
    Raids stuff
    """
    module_name = 'raid'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid'), self._assign_players,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_n'), self._assign_km_menu,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raids21_z'), self._raids21_z_com,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('sendpin'), self._sendpin,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('when_raid'), self._when_raid,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidkm'), self._get_players_km,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidkm_n'), self._get_players_km_new,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_masterpin'), self._masterpin(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_masterpin_l'), self._masterpin(is_last=True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_short'), self._raidshort(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_short_l'), self._raidshort(is_last=True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('my_raidpin'), self._my_raidpin,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_accept'), self._raidpin_accept,
                [CustomInnerFilters.from_player, CustomInnerFilters.private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_reject'), self._raidpin_reject,
                [CustomInnerFilters.from_player, CustomInnerFilters.private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raidpin_help'), self._raidpin_help,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_su'), self._raid_status_update,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_statuses'), self._raid_status_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('test_raid_votes'), self._test_votes,
                [CustomInnerFilters.from_player, CustomInnerFilters.private]
            )
        )

        self.add_inner_handler(InnerHandler(UpdateFilter('profile'), self._update_from_profile))
        self.add_inner_handler(InnerHandler((UpdateFilter('profile') & UpdateFilter('raid')), self._confirm_raid_from_profile))

        self._re_assign_group_menu = re.compile(r'raid_(?P<km>\d+)$')
        self._re_assign_player_menu = re.compile(r'raid_(?P<km>\d+)_(?P<group>\d+)$')

        self._re_assign_group = re.compile(r'(?P<unraid>un)?raid_group_(?P<km>\d+)_(?P<group>\d+)$')
        self._re_assign_player = re.compile(r'(?P<unraid>un)?raid_player_(?P<km>\d+)_(?P<player>\d+)_(?P<group>\d+)$')

        self._re_id = re.compile(r'#(?P<user_id>\d+)', re.MULTILINE)
        self._re_username = re.compile(r'@(?P<username>\w+)', re.MULTILINE)

        self._re_raidkm_type = re.compile(r'((?P<km>\d+)|(?P<group>\w+))')

        self.add_handler(CallbackQueryHandler(self._assign_group_menu, pattern=self._re_assign_group_menu))
        self.add_handler(CallbackQueryHandler(self._assign_player_menu, pattern=self._re_assign_player_menu))
        self.add_handler(CallbackQueryHandler(self._assign_km_menu_callback, pattern=re.compile(r'raid_menu$')))

        self.add_handler(CallbackQueryHandler(self._assign_group_callback, pattern=self._re_assign_group))
        self.add_handler(CallbackQueryHandler(self._assign_player_callback, pattern=self._re_assign_player))

        super().__init__(event_manager, message_manager, dispatcher)
        self.event_manager.scheduler.add_job(self._raids21_z, 'cron', day_of_week='mon-sun', hour=1, minute=1)

        self.event_manager.scheduler.add_job(self._create_votes, 'cron', day_of_week='mon-sun', hour='9,17', minute=30)
        self.event_manager.scheduler.add_job(self._create_votes, 'cron', day_of_week='mon-sun', hour=1)

    @permissions(is_developer)
    def _raids21_z_com(self, update: InnerUpdate):
        self._raids21_z()

    @permissions(is_developer)
    def _test_votes(self, update: InnerUpdate):
        self._create_votes()

    def _create_votes(self):
        goats = Group.select().where((Group.type == 'goat') & (Group.is_active == True))
        raid_time = next_raid()
        end = raid_time - (datetime.timedelta(hours=1, minutes=30) if raid_time.hour == 17 else datetime.timedelta(hours=1))
        for goat in goats:
            lider = goat.liders.order_by(Player.nickname)[0] if goat.liders else None
            if not lider:
                continue
            vote = Vote.create(subject=f'Куда хочешь пойти на рейде {raid_time}?', invoker=lider, enddate=end, type=1)
            vote_group = Group.create(name=f'Vote_{vote.id}', type='vote', is_active=True)
            vote_group.liders = goat.liders
            vote_group.save()

            answers = []
            for title in ['🕳Крышки [ 32км ]', '⛑ Эфедрин [ 24км ]', '🏖Отдых [ 12км ]']:
                ans = VoteAnswer.create(vote=vote, title=title)
                answers.append(ans)
                group = Group.create(
                    name=f'Vote_{vote.id}_{ans.id}', parent=vote_group,
                    type='vote', is_active=True
                )
                group.liders = goat.liders
                group.save()

            results = []
            for idx, answer in enumerate(answers, 1):
                results.append(f'\t\t{idx}. <code>{answer.title}</code>\n\t\t\t- Vote_{vote.id}_{answer.id}')
            results = '\n'.join(results)
            text = (
                f'<b>Опрос #{vote.id}</b> начался.\n'
                f'Его тема: <b>{vote.subject}</b>\n'
                f'\nРезультаты в группах:\n{results}\n'
            )
            for lider in goat.liders:
                self.message_manager.send_message(chat_id=lider.telegram_user.chat_id, text=text, parse_mode='HTML')
            pls = []
            for player in goat.members.filter((Player.is_active == True) & (Player.frozen == False)):
                raid_assigned = player.actual_raid
                if raid_assigned:
                    continue
                raid_assigned = RaidAssign.assign(raid_time, player, 12)
                pls.append(f'{mention_html(player.telegram_user_id, player.nickname)}')
                raid_assigned.status = RaidStatus.HASNOTSEEN
                raid_assigned.last_update = datetime.datetime.now()
                raid_assigned.save()
                if not (player.settings.pings['sendpin'] if player.settings else True):
                    continue

                chat_id = player.telegram_user_id
                try:
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        is_queued=True,
                        text=self.get_assigned_message(raid_assigned)
                    )
                except (Exception, ):
                    pass

    @log
    @inner_update()
    @get_player
    def _assign_km_menu_callback(self, update: InnerUpdate, *args, **kwargs):
        update.telegram_update.message = update.telegram_update.callback_query.message
        self._assign_km_menu(update=update)

    def _assign_km_menu(self, update: InnerUpdate, *args, **kwargs):
        message = update.telegram_update.message
        gangs = update.player.liders
        if gangs.count() == 0:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа.')
        raid_time = next_raid()
        pins_count_ = RaidAssign.select(RaidAssign.km_assigned, peewee.fn.COUNT(RaidAssign.km_assigned)) \
            .where(RaidAssign.time == raid_time) \
            .group_by(RaidAssign.km_assigned)
        pins_count = {}
        for km in pins_count_.dicts():
            pins_count.update(
                {
                    km.get('km_assigned', 0): km.get('count', 0)
                }
            )

        reply_markup = []
        for name, info in Wasteland.raid_locations.items():
            pins_c = pins_count.get(info[1], 0)
            pins = f' ( {pins_c} ч. )' if pins_c > 0 else ''
            reply_markup.append([InlineKeyboardButton(text=f'[{info[1]}км] {name}{pins}', callback_data=f'raid_{info[1]}')])

        reply_markup = InlineKeyboardMarkup([*reply_markup])

        text = f'<i>🍀Мастер установки ПИНа🍀</i>\n\t\t\tна <b>{raid_time}</b>\n\t\t\t<code>Выбирайте рейдовый КМ:</code>'
        if update.telegram_update.callback_query:
            if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
                self.message_manager.send_message(
                    chat_id=message.chat_id, reply_markup=reply_markup,
                    text=text, parse_mode='HTML', is_queued=False
                )
            else:
                self.message_manager.update_msg(
                    chat_id=message.chat_id, message_id=message.message_id, reply_markup=reply_markup,
                    text=text, parse_mode='HTML', is_queued=False
                )
        else:
            self.message_manager.send_message(
                chat_id=message.chat_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )

    @log
    @inner_update()
    @get_player
    def _assign_group_menu(self, update: InnerUpdate, *args, **kwargs):
        callback_query = update.telegram_update.callback_query
        message = callback_query.message
        gangs = update.player.liders
        if gangs.count() == 0:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text="У тебя нет доступа."
            )

        m = self._re_assign_group_menu.search(callback_query.data)
        km = int(m.group('km'))
        reply_markup = []
        for gang in gangs:
            reply_markup.append(
                [InlineKeyboardButton(
                    text=f'{gang.name} ({Wasteland.group_type_translate.get(gang.type, "Неопределенно")}) [ {gang.members.filter(Player.is_active & (Player.frozen == False)).count()} ч. ]',
                    callback_data=f'raid_{km}_{gang.id}'
                )]
            )

        reply_markup = InlineKeyboardMarkup([*reply_markup, [InlineKeyboardButton(text='Назад ◀️', callback_data='raid_menu')]])

        text = f'<i>🍀Мастер установки ПИНа🍀</i>\n\t\t\tна <b>{next_raid()}</b> в {km}км\n\t\t\t<code>Выбирайте рейдовую группу:</code>'
        if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
            self.message_manager.send_message(
                chat_id=message.chat_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )
        else:
            self.message_manager.update_msg(
                chat_id=message.chat_id, message_id=message.message_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )

    @log
    @inner_update()
    @get_player
    def _assign_player_menu(self, update: InnerUpdate, *args, **kwargs):
        callback_query = update.telegram_update.callback_query
        message = callback_query.message

        m = self._re_assign_player_menu.search(callback_query.data)
        km = int(m.group('km'))
        group_id = int(m.group('group'))

        group = Group.get_or_none(Group.id == group_id)
        if not group:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Группы с ID = {group_id} не существует.'
            )
        if update.player not in group.liders:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Ты не являешься лидером этой группы.'
            )
        reply_markup, text = self._generate_group_menu(group, km)

        text = f'<i>🍀Мастер установки ПИНа🍀</i>\n\t\t\tна <b>{next_raid()}</b> в {km}км\n\t\t\t<code>Установите рейдеров <b>{group.name}</b> на точку:</code>'
        if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
            self.message_manager.send_message(
                chat_id=message.chat_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )
        else:
            self.message_manager.update_msg(
                chat_id=message.chat_id, message_id=message.message_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )

    @log
    @inner_update()
    @get_player
    def _assign_group_callback(self, update: InnerUpdate, *args, **kwargs):
        callback_query = update.telegram_update.callback_query
        message = callback_query.message
        m = self._re_assign_group.search(callback_query.data)

        unraid = m.group('unraid') is not None
        km, group_id = [int(x) for x in m.group('km', 'group')]

        group = Group.get_or_none(Group.id == group_id)
        if not group:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Группы с ID = {group_id} не существует.'
            )
        if group not in update.player.liders:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Ты не являешься лидером этой группы.'
            )
        next_raid_time = next_raid()
        members = group.members.where(Player.is_active == True) \
            .filter(Player.frozen == False)

        for member in members:
            if unraid:
                raidpin = member.actual_raid
                if raidpin and raidpin.km_assigned == km:
                    raidpin.delete_instance()
            else:
                RaidAssign.assign(next_raid_time, member, km)

        self.message_manager.bot.answer_callback_query(
            callback_query_id=callback_query.id,
            show_alert=False, text=f'{"Отменил" if unraid else "Выдал"} группе ПИН на {km}км'
        )

        reply_markup, text = self._generate_group_menu(group, km)

        text = f'<i>🍀Мастер установки ПИНа🍀</i>\n\t\t\tна <b>{next_raid()}</b> в {km}км\n\t\t\t<code>Установите рейдеров <b>{group.name}</b> на точку:</code>'
        if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
            self.message_manager.send_message(
                chat_id=message.chat_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )
        else:
            self.message_manager.update_msg(
                chat_id=message.chat_id, message_id=message.message_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )

    @log
    @inner_update()
    @get_player
    def _assign_player_callback(self, update: InnerUpdate, *args, **kwargs):
        callback_query = update.telegram_update.callback_query
        message = callback_query.message
        m = self._re_assign_player.search(callback_query.data)

        unraid = m.group('unraid') is not None
        km, player_id, group_id = [int(x) for x in m.group('km', 'player', 'group')]

        player = Player.get_or_none(Player.id == player_id)
        if not player:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Игрока с ID = {player_id} не существует.'
            )

        if not player.is_active:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Этот игрок неактивен.'
            )
        groups = update.player.liders
        is_lider = False
        for group in groups:
            if player in group.members:
                is_lider = True
                break
        if not is_lider:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False, text=f'Ты не лидер этого игрока.'
            )
        next_raid_time = next_raid()
        if unraid:
            raidpin = player.actual_raid
            if raidpin and raidpin.km_assigned == km:
                raidpin.delete_instance()
        else:
            RaidAssign.assign(next_raid_time, player, km)

        self.message_manager.bot.answer_callback_query(
            callback_query_id=callback_query.id,
            show_alert=False, text=f'{"Отменил" if unraid else "Выдал"} рейд игроку {player.nickname}'
        )
        reply_markup = []
        is_all_not = True
        group = Group.get_or_none(Group.id == group_id)
        if not group:
            return

        reply_markup, text = self._generate_group_menu(group, km)

        if datetime.datetime.utcnow() - message.date > datetime.timedelta(hours=12):
            self.message_manager.send_message(
                chat_id=message.chat_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )
        else:
            self.message_manager.update_msg(
                chat_id=message.chat_id, message_id=message.message_id, reply_markup=reply_markup,
                text=text, parse_mode='HTML', is_queued=False
            )

    def _generate_group_menu(self, group, km):
        reply_markup = []
        is_all_not = True
        members = group.members.where(Player.is_active == True) \
            .filter(Player.frozen == False).order_by(Player.sum_stat.desc())
        for member in members:
            raidpin = member.actual_raid
            raidpin_status = raidpin and raidpin.km_assigned == km
            if raidpin_status:
                is_all_not = False
            reply_markup.append(
                [InlineKeyboardButton(
                    text=f'{"✅" if raidpin_status else "❌"} {member.nickname} [{member.sum_stat} 💪]',
                    callback_data=f'{"un" if raidpin_status else ""}raid_player_{km}_{member.id}_{group.id}'
                )]
            )

        reply_markup = InlineKeyboardMarkup(
            [*reply_markup,
             [InlineKeyboardButton(
                 text='Отправить всех' if is_all_not else 'Отменить всем',
                 callback_data=f'{"" if is_all_not else "un"}raid_group_{km}_{group.id}'
             )],
             [InlineKeyboardButton(text='Назад ◀️', callback_data=f'raid_{km}')]
             ]
        )

        text = f'<i>🍀Мастер установки ПИНа🍀</i>\n\t\t\tна <b>{next_raid()}</b> в {km}км\n\t\t\t<code>Установите рейдеров <b>{group.name}</b> на точку:</code>'

        return reply_markup, text

    def _raids21_z(self):
        last = last_raid()
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
        self.message_manager.send_message(  # todo: переделать на триггер?
            chat_id=update.telegram_update.message.chat_id,
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
        update.telegram_update.message.reply_text(text=text, parse_mode='HTML')

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<date>\d{2}\.\d{2}\.\d{4}-\d{2})\s+(?P<status_id>([+-])?\d{1,3})'),
        argument_miss_msg='Пришли сообщение в формате "/raid_su дд.мм.гггг-чч Статус @User1 @User2"\nСписок статусов: /raid_statuses'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _raid_status_update(self, update: InnerUpdate, match, players, *args, **kwargs):
        message = update.telegram_update.message

        time = datetime.datetime.strptime(match.group('date'), '%d.%m.%Y-%H')
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), 0)
        if not (interval.start_date <= time <= interval.last_date):
            return message.reply_text('Этот рейд был вне текущего интервала рейдов!')
        status_id = int(match.group('status_id'))
        status_name = RaidStatus.dict().get(status_id, None)
        if not status_name:
            return message.reply_text(f'Статуса с ID = {status_id} не существует\nСписок статусов: /raid_statuses')

        query = RaidAssign.update(
            {
                RaidAssign.status_id: status_id,
                RaidAssign.is_reported: False
            }
        ).where((RaidAssign.player_id << [x.id for x in players]) & (RaidAssign.status_id != status_id) & (RaidAssign.time == time))
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

        message.reply_text(
            f'Обновил <b>{updated_rows}</b> статус{formatter(updated_rows)} рейда <b>{time}</b> на {status_name} ( ID{status_id} )',
            parse_mode='HTML'
        )

    @command_handler(
        regexp=re.compile(r'(?P<km>\d+)\s*(?P<groups>.+)?'),
        argument_miss_msg='Пришли сообщение в формате Км имя/алиас группы'
    )
    @get_players(include_reply=True, break_if_no_players=False)
    def _assign_players(self, update: InnerUpdate, match, players, *args, **kwargs):
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
        chat_id = settings.GOAT_ADMIN_CHAT_ID if settings.GOAT_ADMIN_CHAT_ID == message.chat_id else update.invoker.chat_id

        if not km.isdigit():
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Пришли км, на который отправить группу, числом'
            )
            return
        else:
            km = int(km)

        if km not in Wasteland.raid_kms:
            self.message_manager.send_message(
                chat_id=chat_id,
                text='Такой рейдовой локации не существует'
            )
            return
        next_raid_time = next_raid()
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
                pls.append(mention_html(player.telegram_user_id, player.nickname))
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
            for player in group.members.filter((Player.frozen == False) & (Player.is_active == True)):
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
                     f'{next_raid_time.time()} рейдят {km}км',
                parse_mode=ParseMode.HTML
            )
        else:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Кажется ты никого не послал на рейд.'
            )

    def _when_raid(self, update: InnerUpdate):
        """Выдает, через сколько времени будет следующий рейд"""
        next_raid_time = next_raid()
        seconds = (next_raid_time - datetime.datetime.now()).total_seconds()
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds %= 60
        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'Ближайший рейд в *{next_raid_time.hour}:00* мск\n'
                 f'Т.е. через *{hours:.0f}* ч *{minutes:.0f}* мин *{seconds:.0f}* сек',
            parse_mode=ParseMode.MARKDOWN
        )

    def _sendpin(self, update: InnerUpdate, *args, **kwargs):
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
            for member in group.members.filter(Player.is_active & (Player.frozen == False)):
                if member not in access:
                    access.append(member)
        players = []
        if update.command.argument == '':
            players = access
        else:
            parts = update.command.argument.split()
            kms = []
            users = []
            group_names = []
            for part in parts:
                if part.isdigit():
                    kms.append(int(part))
                else:
                    username = self._re_username.search(part)
                    user_id = self._re_id.search(part)
                    if username:
                        tg_user = TelegramUser.get_by_username(username.group('username'))
                        users.append(tg_user)
                    elif user_id:
                        tg_user = TelegramUser.get_by_user_id(int(user_id.group('user_id')))
                        users.append(tg_user)
                    elif part not in group_names:
                        group_names.append(part)
                    else:
                        continue

            groups = []
            for x in group_names:
                group = Group.get_by_name(x.group('group'))
                if not (group and group in update.player.liders and group not in groups):
                    continue

                for member in group.members:
                    if member in players:
                        continue
                    players.append(member)

            for user in users:
                pl = user.player.get() if user.player else None
                if not (pl and pl in access and pl not in access):
                    continue
                players.append(pl)
            for km in kms:
                for pin in RaidAssign.next_raid_players(status=RaidStatus.UNKNOWN, km=km):
                    pl = pin.player
                    if not (pl in access and pl not in players):
                        continue
                    players.append(pl)
        pls = []
        for player in players:
            raid_assigned = player.actual_raid
            if not (raid_assigned and raid_assigned.status_id == RaidStatus.UNKNOWN):
                continue
            pls.append(f'{mention_html(player.telegram_user_id, player.nickname)}')
            raid_assigned.status = RaidStatus.HASNOTSEEN
            raid_assigned.last_update = update.date
            raid_assigned.save()

            chat_id = player.telegram_user.chat_id if not settings.DEBUG else update.telegram_update.message.chat_id
            if not (player.settings.pings['sendpin'] if player.settings else True):
                continue
            self.message_manager.send_message(
                chat_id=chat_id,
                is_queued=True,
                text=self.get_assigned_message(raid_assigned)
            )

        chat_id = settings.GOAT_ADMIN_CHAT_ID if settings.GOAT_ADMIN_CHAT_ID == message.chat_id else update.invoker.chat_id
        if not pls:
            self.message_manager.send_message(
                chat_id=chat_id,
                text='Пины еще не назначены или уже все отправлены'
            )
        else:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Пины отправлены игрокам ({len(pls)}):\n\n' +
                     ', '.join(pls),
                parse_mode=ParseMode.HTML
            )

    @get_invoker_raid
    def _my_raidpin(self, update: InnerUpdate, raid_assigned, *args, **kwargs):
        """Посмотреть свой назначенный рейд"""
        invoker = update.invoker
        if raid_assigned.status == RaidStatus.HASNOTSEEN:
            raid_assigned.status = RaidStatus.ASSIGNED
            raid_assigned.last_update = update.date
            raid_assigned.save()
        goat = update.player.goat
        lider = goat.liders.order_by(Player.nickname)[0] if goat and goat.liders else None

        if lider:
            vote = lider.votes_invoked.filter(Vote.type == 1).order_by(Vote.enddate.desc()).limit(1)
            if vote:
                vote = vote[0]
                vote = None if vote.complete else vote
        else:
            vote = None

        if vote and raid_assigned.km_assigned not in Wasteland.raid_kms_tz:
            buttons = []
            for answer in vote.answers.order_by(VoteAnswer.id):
                if update.player in answer.voted:
                    continue
                buttons.append([InlineKeyboardButton(text=answer.title, callback_data=f'vote_answer_{vote.id}_{answer.id}')])
            markup = InlineKeyboardMarkup(buttons) if buttons else None

        else:
            markup = None
        self.message_manager.send_message(
            chat_id=invoker.chat_id,
            text=raid_assigned.get_msg(),
            parse_mode=ParseMode.HTML,
            reply_markup=markup
        )
        if raid_assigned.km_assigned in Wasteland.raid_kms_tz:
            self.message_manager.bot.send_photo(
                photo=open(f'files/timings/raid{raid_assigned.km_assigned}_timings.jpg', 'rb'),
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
            text=raid_assigned.get_msg(),
            parse_mode=ParseMode.HTML
        )

    @get_invoker_raid
    def _raidpin_reject(self, update: InnerUpdate, raid_assigned, *args, **kwargs):
        """Отказаться от  назначенного рейда"""
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
        feedback = Feedback(original_chat_id=invoker.chat_id)
        m = self.message_manager.send_message(
            chat_id=settings.GOAT_ADMIN_CHAT_ID,
            text=f'Игрок {mention_html(update.invoker.user_id, update.player.nickname)} отказался от пина [{raid_assigned.km_assigned}]',
            parse_mode=ParseMode.HTML,
            is_queued=False
        )
        if not m:
            return
        feedback.message_id = m.message_id
        feedback.save()
        self.message_manager.send_message(
            chat_id=invoker.chat_id,
            text=raid_assigned.get_msg(),
            parse_mode=ParseMode.HTML
        )

    @command_handler()
    @lead_time(name='/raidkm command', description='Вызов отображения позиций на рейде')
    def _get_players_km(self, update: InnerUpdate, *args, **kwargs):
        """Возвращает положение игроков в пустоши для следующего рейда. Необходимо указать группу либо рейд-точку"""
        message = update.telegram_update.message
        next_raid_time = next_raid()
        speed_mapper = {
            RaidkmIcons.UNKNOWN: RaidkmIcons.FAST,
            RaidkmIcons.MISSED: RaidkmIcons.FAST
        }
        chat_id = settings.GOAT_ADMIN_CHAT_ID if settings.GOAT_ADMIN_CHAT_ID == message.chat_id else update.invoker.chat_id
        access = []
        for group in update.player.liders:
            access.extend(group.members.filter((Player.is_active == True) & (Player.frozen == False)))
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

            raid_km_str = "\n".join(
                f'{x}км ({get_counter_formatted(RaidkmIcons.ACCEPTED, x)}): '
                f'{get_counter_formatted(RaidkmIcons.ON_PLACE, x)} | '
                f'{get_counter_formatted(RaidkmIcons.IN_PROCESS, x)} | '
                f'{get_counter_formatted(RaidkmIcons.FAST, x)}'
                for x in sorted(raid_counter)
            )
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Рейд-точки на *{next_raid_time.time().hour}:00* мск:\n\n'
                     f'{raid_km_str}',
                parse_mode=ParseMode.MARKDOWN
            )

        for arg in update.command.argument.split():
            res = []
            group = Group.get_by_name(arg)
            if group and group in update.player.liders:
                for player in group.members:
                    if player.actual_raid:
                        res.append(self.format_raid_km_line(player))

            elif arg.isdigit() and int(arg) in Wasteland.raid_kms:
                for raid_assigned in RaidAssign.select().where(
                    RaidAssign.km_assigned == int(arg),
                    RaidAssign.time == next_raid_time
                ):
                    res.append(self.format_raid_km_line(raid_assigned.player))

            self.message_manager.send_message(
                chat_id=message.chat_id,
                text='\n'.join(sorted(res))
            )

    @permissions(is_admin)
    @get_players(include_reply=True, break_if_no_players=False, callback_message=False)
    @command_handler()
    def _get_players_km_new(self, update: InnerUpdate, players, *args, **kwargs):
        message = update.telegram_update.message
        is_last = False
        raid_time = last_raid() if is_last else next_raid()
        argument_parts = update.command.argument.split()

        liders = [g.id for g in update.player.liders]

        radar_query_dates = Radar.select(Radar.player_id, peewee.fn.MAX(Radar.time).alias('MAXDATE')).group_by(Radar.player_id).alias('radar_max')

        radar_query = Radar.select(Radar.km, Radar.player_id, Radar.time).join(
            radar_query_dates, on=(
                Radar.player_id == radar_query_dates.c.player_id &
                Radar.time == radar_query_dates.c.MAXDATE
            )
        )

        time_30 = datetime.datetime.now() - datetime.timedelta(minutes=30)
        time_5 = datetime.datetime.now() - datetime.timedelta(minutes=5)
        time_delta_case = peewee.Case(
            None, (
                (radar_query.c.time < time_30, '⏳'),
                (radar_query.c.time > time_5, '🆕'),
                (radar_query.c.time.between(time_30, time_5), '🆗')
            )
        )
        status_case = peewee.Case(
            None, (
                (RaidAssign.status_id << [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED], 0),
                (RaidAssign.km_assigned == radar_query.c.km, 1),
                (radar_query.c.km == 0, 4),
                (RaidAssign.km_assigned > radar_query.c.km, 2)
            ), 3
        )

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
        )\
            .join(GroupPlayerThrough, on=(GroupPlayerThrough.player_id == Player.id))\
            .join(Group, on=(Group.id == GroupPlayerThrough.group_id))\
            .join(RaidAssign, on=(RaidAssign.player_id == Player.id)) \
            .join(radar_query, on=(radar_query.c.player_id == Player.id)) \
            .where(
                (
                    ((Group.name << argument_parts) | (Group.alias << argument_parts)) |
                    (RaidAssign.km_assigned << [int(x) for x in argument_parts if x.isdigit()]) |
                    (Player.id << [p.id for p in players])
                ) & (RaidAssign.time == raid_time)
            ) \
            .distinct() \
            .order_by(RaidAssign.km_assigned.desc(), status_case.asc(), radar_query.c.km.desc(), Player.sum_stat.desc(), Player.dzen.desc())

        formatter_report = f'<b>Рейд {raid_time}</b>\n\n'

        statuses = ['👊', '🏕', '🏃‍‍', '❔', '😴']

        raid_counter = Counter()
        power_counter = Counter()
        last_km = None
        for _player in _players.dicts():
            km_assigned, km_radar, delta, chat_id, nickname, dzen, status_id, informer = _player['km_assigned'], _player['km'], _player['delta'], _player['telegram_user'], _player[
                'nickname'], _player['dzen'], _player['status_id'], _player['informer']
            if last_km is None:
                last_km = km_assigned
            if last_km != km_assigned:
                last_km = km_assigned
                formatter_report += f'🎓{power_counter["sum_stat"]}к на {power_counter["peoples"]} человек\n\n'
                power_counter = Counter()

            emojie = '🚷' if km_assigned in Wasteland.raid_kms_tz else '🙀'
            sum_stat = round(_player['sum_stat'] / 1000, 1)
            emojie_speed = statuses[informer]
            raid_counter[emojie_speed] += 1
            power_counter['sum_stat'] += sum_stat
            power_counter['peoples'] += 1

            formatter_report += f'{emojie}{km_assigned:02}|{emojie_speed}{km_radar:02}|{delta}|🎓{sum_stat:03.1f}|🏵{dzen:02}|{mention_html(chat_id, nickname)}\n'
        formatter_report += f'🎓{power_counter["sum_stat"]}к на {power_counter["peoples"]} человек\n\n'

        formatter_report += (
            'Аналитика:\n'
            f'👊Прожаты: {raid_counter["👊"]}\n'
            f'🏕На точке: {raid_counter["🏕"]}\n'
            f'🏃‍‍В пути: {raid_counter["🏃‍‍"]}\n'
            f'❔Потерялись: {raid_counter["❔"]}\n'
            f'😴Спят: {raid_counter["😴"]}'
        )
        return message.reply_text(formatter_report, parse_mode='HTML')

    def _raidshort(self, is_last=False):
        @permissions(is_admin)
        @command_handler()
        def handler(self, update: InnerUpdate, *args, **kwargs):
            message = update.telegram_update.message
            kms = update.command.argument.split()
            if len(kms) == 0:
                return self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=f'Пришли команду в формате: /raidpin_short{"_l" if is_last else ""} КМ'
                )

            def format_line(raid_status):
                return f': <b>{raid_counts[raid_status]}</b> [{int(raid_counts[raid_status] / counts * 100)}%]({int(raid_power[raid_status] / 1000)}к💪)' \
                    if raid_power[raid_status] else ''

            for arg in kms:
                raid_power = defaultdict(int)
                raid_counts = defaultdict(int)
                time = last_raid() if is_last else next_raid()
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
                if time < next_raid():
                    lines.append(f'👊Подтвердили{format_line(RaidStatus.CONFIRMED)}')
                lines.append(f'❌Отказались{format_line(RaidStatus.REJECTED)}')
                if counts > 0:
                    lines.append(
                        f'Эффективность: <b>{int((raid_counts[RaidStatus.IN_PROCESS] + raid_counts[RaidStatus.CONFIRMED]) * 100 / counts)}%</b>'
                        f'[{raid_counts[RaidStatus.IN_PROCESS] + raid_counts[RaidStatus.CONFIRMED]}/{counts}ч]'
                    )
                    lines.append(
                        f'Эффективность: <b>{int((raid_power[RaidStatus.IN_PROCESS] + raid_power[RaidStatus.CONFIRMED]) / sum_stat * 100)}%</b>'
                        f'[{int((raid_power[RaidStatus.IN_PROCESS] + raid_power[RaidStatus.CONFIRMED]) / 1000)}к/{int(sum_stat / 1000)}к💪]'
                    )
                message_text = '\n'.join(lines)
                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=message_text,
                    parse_mode=ParseMode.HTML
                )

        return functools.partial(handler, self)

    def _masterpin(self, is_last=False):
        @command_handler()
        def handler(self, update: InnerUpdate, *args, **kwargs):
            """Счетчик по рейд статусам"""
            message = update.telegram_update.message
            chat_id = settings.GOAT_ADMIN_CHAT_ID if settings.GOAT_ADMIN_CHAT_ID == message.chat_id else update.invoker.chat_id
            access = []
            for group in update.player.liders:
                access.extend(group.members)
            if not access:
                return self.message_manager.send_message(chat_id=chat_id, text='Нет доступа.')

            def format_line(raid_status):
                return f'<b>{len(raid_users[raid_status])}</b>[{raid_power[raid_status]}]: ' \
                       f'{"; ".join(raid_users[raid_status])}' if raid_users[raid_status] else ''

            kms = update.command.argument.split()
            if len(kms) == 0:
                return self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=f'Пришли команду в формате: /raidpin_masterpin{"_l" if is_last else ""} КМ'
                )
            for arg in kms:
                raid_power = defaultdict(int)
                raid_users = defaultdict(list)

                time = last_raid() if is_last else next_raid()

                for raid_assign in RaidAssign.next_raid_players(km=int(arg), time=time):
                    if not ((raid_assign.player in access) or update.invoker.is_admin):
                        continue
                    player = raid_assign.player
                    raid_power[raid_assign.status] += player.sum_stat
                    raid_users[raid_assign.status].append(f"{mention_html(player.telegram_user_id, player.nickname)}")

                lines = [
                    f'ПИН на <b>{arg}км</b>\n(<b>{time})</b>',
                    f'😑Еще не смотрели {format_line(RaidStatus.HASNOTSEEN)}',
                    f'🌚Посмотрели и все {format_line(RaidStatus.ASSIGNED)}',
                    f'🐌Уже вышли {format_line(RaidStatus.ACCEPTED)}',
                    f'🏕Пришли на точку {format_line(RaidStatus.ON_PLACE)}',
                    f'👊Отметились на точке {format_line(RaidStatus.IN_PROCESS)}'
                ]
                if time < next_raid():
                    lines.append(f'👊Подтвердили участие {format_line(RaidStatus.CONFIRMED)}')

                lines.append(f'❌Отказались от участия {format_line(RaidStatus.REJECTED)}')
                message_text = '\n'.join(lines)
                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text=message_text,
                    parse_mode=ParseMode.HTML
                )

        return functools.partial(handler, self)

    @staticmethod
    def get_raidpin_status(player_raid: RaidAssign):
        if not player_raid:
            return
        if not player_raid.km_real:
            return RaidkmIcons.UNKNOWN
        if player_raid.km_real == player_raid.km_assigned:
            if player_raid.status == RaidStatus.IN_PROCESS:
                return RaidkmIcons.IN_PROCESS
            return RaidkmIcons.ON_PLACE
        return RaidkmIcons.FAST

    def format_raid_km_line(self, player):
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

        if message.date.astimezone(settings.timezone) - raid.time > datetime.timedelta(hours=8):
            return

        raid_assign = player.raid_near_time(raid.time - datetime.timedelta(seconds=5))
        if not (raid_assign and raid_assign.status == RaidStatus.IN_PROCESS):
            return

        raid_assign.status = RaidStatus.CONFIRMED
        self.message_manager.send_message(
            chat_id=message.chat_id,
            text='✅Вопрос закрыт!✅\n'
                 'Ты окончательно подтвердил своё участие на предыдущем рейде.\n'
                 f'<b>{raid_assign.time}</b>',
            parse_mode=ParseMode.HTML
        )
        raid_assign.last_update = update.date
        raid_assign.save()

    def _update_from_profile(self, update: PlayerParseResult):
        message = update.telegram_update.message
        player = update.player
        if not player:
            return

        raid_assign = player.raid_near_time(update.date)
        if not (raid_assign and raid_assign.last_update < update.date):
            return

        if raid_assign.status not in [RaidStatus.IN_PROCESS, RaidStatus.CONFIRMED] and not raid_assign.is_reported and raid_assign.km_assigned == update.profile.distance:
            if update.profile.on_raid:
                raid_assign.status = RaidStatus.IN_PROCESS
                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text='✊Вижу твой кулак!✊\n'
                         'Ты подтвердил участие в рейде, дождись результатов.\n'
                         f'<b>{raid_assign.time}</b>',
                    parse_mode=ParseMode.HTML
                )

            else:
                raid_assign.status = RaidStatus.ON_PLACE
                self.message_manager.send_message(
                    chat_id=message.chat_id,
                    text='❗️Покажи кулачок, боец!❗️\n'
                         'Ты на точке, но не записался на рейд.\n'
                         f'<b>{raid_assign.time}</b>',
                    parse_mode=ParseMode.HTML
                )

        elif raid_assign.status == RaidStatus.IN_PROCESS and raid_assign.km_assigned != update.profile.distance:
            raid_assign.status = RaidStatus.LEFTED
            self.message_manager.send_message(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                text=f'Игрок {mention_html(raid_assign.player.telegram_user_id, raid_assign.player.nickname)} покинул свою рейд точку [{raid_assign.km_assigned}]\n'
                     f'<b>{raid_assign.time}</b>',
                parse_mode=ParseMode.HTML
            )

            self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Эй, стой! Куда с рейда убежал?\n'
                     f'РЕЙД НА {raid_assign.km_assigned}км. !!!ОДУМАЙСЯ!!!\n'
                     f'<b>{raid_assign.time}</b>',
                parse_mode=ParseMode.HTML
            )
        raid_assign.last_update = update.date
        raid_assign.save()

    @staticmethod
    def get_assigned_message(raid_assigned):
        return 'Тебе выдан ПИН\n' \
               'Внимание на /my_raidpin\n' \
               f'{raid_assigned.time}'
