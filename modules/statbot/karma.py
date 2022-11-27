import re
import datetime
import math
import re

import peewee
from telegram import ParseMode
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update,
    UpdateFilter
)
from decorators import (
    command_handler,
    permissions
)
from decorators.permissions import (
    is_admin,
    is_developer
)
from decorators.users import get_players
from models import (
    Group,
    GroupPlayerThrough,
    KarmaTransition,
    Player,
    RaidAssign,
    RaidResult,
    RaidsInterval
)
from models.raid_assign import RaidStatus
from modules import BasicModule
from modules.statbot.parser import GroupParseResult
from utils.functions import (
    CustomInnerFilters,
    _loose_image,
    last_raid,
    round_b
)
from ww6StatBotWorld import Wasteland


class Karma:
    """docstring for Karma"""

    def __init__(self, module_name='unkown', recivier=None, sender=None, amount=0, description='developer'):
        super(Karma, self).__init__()
        self.module_name, self.recivier, self.sender, self.amount, self.description = \
            module_name, recivier, sender, amount, description


class KarmaModule(BasicModule):
    """
    Handle player groups
    """
    module_name = 'karma'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('gang'), self._update_from_panel_gang))

        self.add_inner_handler(InnerHandler(UpdateFilter('karma_'), self._karma))
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('karma_add'), self._karma_add,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('karma_reduce'), self._karma_reduce,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('sarr'), self._sarr,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('sakd'), self._sakd,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('salr'), self._loose_stat_c,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)
        self.event_manager.scheduler.add_job(self._auto_raid_rewards_n, 'cron', day_of_week='mon-sun', hour='1,9,17', minute='5')

        self.event_manager.scheduler.add_job(self._auto_karma_decline, 'cron', day_of_week='mon-sun', hour=0)

    def _karma(self, update: Update):
        karma_ = update.karma_
        self._karma_handler(
            module_name=karma_.module_name,
            sender=karma_.sender,
            recivier=karma_.recivier,
            amount=karma_.amount,
            description=karma_.description
        )

    def _karma_handler(self, module_name: str, sender: Player, recivier: Player, amount: int, description: str):
        karma = KarmaTransition(
            module_name=module_name,
            amount=amount,
            description=description
        )
        karma.save()
        if sender:
            sender.karma_sended.add(karma)

        if recivier:
            recivier.karma_recived.add(karma)
            recivier.add_stats(
                karma=recivier.karma + amount,
                hp=recivier.hp,
                attack=recivier.attack,
                defence=recivier.defence,
                power=recivier.power,
                accuracy=recivier.accuracy,
                oratory=recivier.oratory,
                agility=recivier.agility,
                stamina=recivier.stamina,
                dzen=recivier.dzen,
                raids21=recivier.raids21, raid_points=recivier.raid_points, loose_raids=recivier.loose_raids, loose_weeks=recivier.loose_weeks,
                regeneration_l=recivier.regeneration_l,
                batcoh_l=recivier.batcoh_l
            )
            recivier.save()

    def _update_from_panel_gang(self, update: GroupParseResult):
        # return
        message = update.telegram_update.message
        player = update.player
        if not player:
            return

        updates = 0
        for gangster in update.gang.players:
            pl = Player.get_by_nickname(gangster.nickname)
            if not pl:
                continue

            raid_assign = pl.raid_near_time(message.forward_date.astimezone(settings.timezone))
            if not (raid_assign and update.date > raid_assign.last_update):
                continue

            if raid_assign.km_assigned == gangster.distance and gangster.status == '👊' and raid_assign.status not in [RaidStatus.CONFIRMED, RaidStatus.IN_PROCESS]:
                raid_assign.status = RaidStatus.IN_PROCESS
                updates += 1
                self.message_manager.send_message(
                    chat_id=pl.telegram_user.chat_id,
                    text='Твоё участие в рейде подтвержденно, через панель банды.\n'
                         'Не забудь отправить <b>ПОЛНЫЙ</b> пип бой, после рейда.\n'
                         f'<b>{raid_assign.time}</b>',
                    parse_mode=ParseMode.HTML
                )

            elif raid_assign.status == RaidStatus.IN_PROCESS and ((raid_assign.km_assigned != gangster.distance) or (gangster.status != '👊')):
                raid_assign.status = RaidStatus.LEFTED
                updates += 1
                self.message_manager.send_message(
                    chat_id=pl.telegram_user.chat_id,
                    text=f'Эй, стой! Куда с рейда убежал?\n РЕЙД НА {raid_assign.km_assigned}км. !!!ОДУМАЙСЯ!!!\n{raid_assign.time}'
                )

            elif raid_assign.status == RaidStatus.ACCEPTED and raid_assign.km_assigned >= gangster.distance and gangster.status == '👟':
                raid_assign.status = RaidStatus.ACCEPTED
            raid_assign.last_update = update.date
            raid_assign.save()

        if updates == 0:
            return

        self._karma_handler('raid', update.player, update.player, updates * 2, f'Обновление рейд статусов(панель)[{updates}]')

        if updates == 1:
            end = ''
        elif 1 < updates < 5:
            end = 'а'
        else:
            end = 'ов'

        self.message_manager.send_message(
            chat_id=message.chat_id,
            text=f'Обновлен{"о" if updates > 1 else ""} {updates} статус{end}. Дарую тебе +{updates * 2}☯️ в карму.'
        )

    @permissions(is_developer)
    def _sarr(self, update: Update):
        self._auto_raid_rewards_n()

    @permissions(is_developer)
    def _sakd(self, update: Update):
        self._auto_karma_decline()

    def _auto_raid_rewards_n(self):
        now = datetime.datetime.now()
        interval = RaidsInterval.interval_by_date(now, offset=0)
        last_raid_time = last_raid(now - datetime.timedelta(hours=2))
        raid_assigns = RaidAssign.select().where(RaidAssign.time.between(interval.start_date, last_raid_time) & (RaidAssign.is_reported == False))

        _raid_results = RaidResult.select(
            RaidResult.date,
            RaidResult.km,
            RaidResult.wingoat
        ).where(RaidResult.date.between(interval.start_date, last_raid_time)).dicts()
        raid_results = {}
        for result in _raid_results:
            kms = raid_results.get(result['date'], {})
            kms.update(
                {
                    result['km']: result['wingoat']
                }
            )
            raid_results.update(
                {
                    result['date']: kms
                }
            )

        notify = []
        rewards = []

        info = Player.select(Player.id.alias('player_id'), Player.nickname, Player.telegram_user_id, Group.name.alias('goat_name')) \
            .join(GroupPlayerThrough, on=((GroupPlayerThrough.player_id == Player.id) & (Player.is_active == True))) \
            .join(Group, on=((GroupPlayerThrough.group_id == Group.id) & (Group.type == 'goat'))).distinct().dicts()
        info_by_player_id = {}
        for player in info:
            info_by_player_id.update(
                {
                    player['player_id']: {
                        'telegram_user_id': player['telegram_user'],
                        'nickname': player['nickname'],
                        'goat_name': player['goat_name']
                    }
                }
            )

        for assign in raid_assigns:
            kms = raid_results.get(assign.time, {})
            wingoat = kms.get(assign.km_assigned, None)
            if wingoat is None:
                self.logger.info(f'{assign.time} на {assign.km_assigned} нет козла победителя')
                continue

            player_info = info_by_player_id.get(assign.player_id, None)
            if not player_info:
                self.logger.info(f'{assign.time} игрок {assign.player_id} не имеет информации')
                continue

            if wingoat != player_info['goat_name'] and assign.status_id == RaidStatus.IN_PROCESS:
                assign.status_id = RaidStatus.CONFIRMED
                assign.save()

            if assign.status_id != RaidStatus.CONFIRMED:
                notify.append(
                    {
                        'chat_id': player_info['telegram_user_id'],
                        'text': f'Пропуск рейда {assign.time} замечен.'
                    }
                )
                continue

            karma = 30 if assign.km_assigned in Wasteland.raid_kms_tz else 10
            rewards.append(
                {
                    'player_id': assign.player_id,
                    'append': karma,
                    'description': f'Награда за рейд {assign.km_assigned}км. Отметка: Участвовал.'
                }
            )
            notify.append(
                {
                    'chat_id': player_info['telegram_user_id'],
                    'text': f'Успешный рейд {assign.time} засчитан.\nНачислено ☯️{karma} кармы.'
                }
            )

        q = RaidAssign.update(
            {
                RaidAssign.is_reported: True
            }
        ) \
            .where(RaidAssign.time.between(interval.start_date, last_raid_time)).execute()

        player_raid_stats = {}
        # {
        #     'points': 0,
        #     'raids21': 0,
        #     'loose_raids': 0
        # }

        cz_raids_q = RaidAssign.select(RaidAssign.player_id, peewee.fn.COUNT(RaidAssign.is_reported)) \
            .where((RaidAssign.is_reported == True) & RaidAssign.time.between(interval.start_date, last_raid_time)) \
            .filter(RaidAssign.km_assigned.not_in(Wasteland.raid_kms_tz)) \
            .filter(RaidAssign.status_id == RaidStatus.CONFIRMED) \
            .group_by(RaidAssign.player_id) \
            .order_by(RaidAssign.player_id.desc()) \
            .dicts()

        tz_raids_q = RaidAssign.select(RaidAssign.player_id, peewee.fn.COUNT(RaidAssign.is_reported)) \
            .where((RaidAssign.is_reported == True) & RaidAssign.time.between(interval.start_date, last_raid_time)) \
            .filter(RaidAssign.km_assigned << Wasteland.raid_kms_tz) \
            .filter(RaidAssign.status_id == RaidStatus.CONFIRMED) \
            .group_by(RaidAssign.player_id) \
            .order_by(RaidAssign.player_id.desc()) \
            .dicts()

        loose_raids = RaidAssign.select(RaidAssign.player_id, peewee.fn.COUNT(RaidAssign.is_reported)) \
            .where((RaidAssign.is_reported == True) & RaidAssign.time.between(interval.start_date, last_raid_time)) \
            .filter(RaidAssign.status_id != RaidStatus.CONFIRMED) \
            .group_by(RaidAssign.player_id) \
            .order_by(RaidAssign.player_id.desc()) \
            .dicts()

        for raid_stats in cz_raids_q:
            pl_stats = player_raid_stats.get(raid_stats['player'], {})
            pl_stats.update(
                {
                    'points': pl_stats.get('points', 0) + raid_stats['count'] * 0.75,
                    'raids21': pl_stats.get('raids21', 0) + raid_stats['count'],
                }
            )
            player_raid_stats.update(
                {
                    raid_stats['player']: pl_stats
                }
            )

        for raid_stats in tz_raids_q:
            pl_stats = player_raid_stats.get(raid_stats['player'], {})
            pl_stats.update(
                {
                    'points': pl_stats.get('points', 0) + raid_stats['count'] * 1,
                    'raids21': pl_stats.get('raids21', 0) + raid_stats['count'],
                }
            )
            player_raid_stats.update(
                {
                    raid_stats['player']: pl_stats
                }
            )

        for raid_stats in loose_raids:
            pl_stats = player_raid_stats.get(raid_stats['player'], {})
            pl_stats.update(
                {
                    'loose_raids': raid_stats['count'],
                }
            )
            player_raid_stats.update(
                {
                    raid_stats['player']: pl_stats
                }
            )

        player_raid_stats_update_q = [{
            'user_id': key,
            'raids21': value.get('raids21', 0),
            'raid_points': value.get('points', 0.0),
            'loose_raids': value.get('loose_raids', 0)
        }
            for key, value in player_raid_stats.items()]

        Player.insert(player_raid_stats_update_q).on_conflict(
            conflict_target=[Player.id],
            update={
                Player.raids21: peewee.EXCLUDED.raids21,
                Player.raid_points: peewee.EXCLUDED.raid_points,
                Player.loose_raids: peewee.EXCLUDED.loose_raids,
            }
        ).execute()

        for reward in rewards:
            player = Player.get_or_none(id=reward['player_id'])
            if not player:
                continue
            self._karma_handler('raid_rewards', player, player, reward['append'], reward['description'])

        for message in notify:
            self.message_manager.send_message(
                chat_id=message['chat_id'],
                text=message['text'],
                parse_mode='HTML'
            )

    def _auto_karma_decline(self):
        interval = RaidsInterval.interval_by_date(datetime.datetime.now(), offset=0)
        if interval.last_date - datetime.datetime.now() > datetime.timedelta(hours=2):
            return
        self._auto_raid_rewards_n()
        players = Player.get_iterator()
        for player in players:
            raids_c = player.raids21 + player.loose_raids
            norm = int(math.floor(raids_c * 1 / 2))
            player.raid_points = round_b(player.raid_points)
            if player.raid_points >= norm:
                player.loose_weeks = 0
                karma = int((player.raid_points - norm) * 20)
                prem = f'Я дал тебе дополнительные ☯️{karma} ед. кармы за первышение нормы'

                if player.settings.pings['weekly_report']:
                    self.message_manager.send_message(
                        chat_id=player.telegram_user.chat_id,
                        text=f'Ты выполнил недельную норму рейдов({norm}).\n'
                             f'{prem if karma > 0 else ""}'
                    )
            else:
                player.loose_weeks += 1
                karma = -int(math.floor(10 * 1.5 ** (norm - player.raid_points)))
                if player.settings.pings['weekly_report']:
                    self.message_manager.send_message(
                        chat_id=player.telegram_user.chat_id,
                        text=f'Ты не выполнил недельную норму рейдов({norm}).\n'
                             f'У тебя - {player.raid_points}\n'
                             f'Я забрал у тебя ☯️{karma} ед. кармы'
                    )
            player.save()
            self._karma_handler('raid_rewards', player, player, karma, f'Обработка недели рейдов.')

        self._loose_stats()

    @permissions(is_developer)
    def _loose_stat_c(self, update: Update):
        self._loose_stats()

    def _loose_stats(self):
        players_ = Player.select() \
            .filter(Player.is_active == True) \
            .filter((Player.frozen == False)) \
            .filter(Player.loose_weeks != 0) \
            .order_by(Player.loose_weeks.desc(), Player.loose_raids.desc())
        output = ['<b>Список игроков на отчисление</b>\n']
        for idx, player in enumerate(players_, 1):
            output.append(f'{idx}. {_loose_image(player.loose_weeks, player.loose_raids).format(mention_html(player.telegram_user_id, player.nickname))}')
        if len(output) == 1:
            output.append('\nОй.... А где они?')
        self.message_manager.send_message(chat_id=settings.GOAT_ADMIN_CHAT_ID, text='\n'.join(output), parse_mode='HTML')

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'\s*(?P<amount>\d+).*'),
        argument_miss_msg='Пришли сообщение в формате "/karma_add d+(кол-во) @user1, @user2"'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _karma_add(self, update: Update, match, players, *args, **kwargs):
        karma = int(match.group('amount'))
        pls = []
        for player in players:
            self._karma_handler('karma_add', update.player, player, karma, 'Админское начисление кармы.')
            pls.append(player.nickname)

        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'Карма успешно начислена(+{karma}☯️) игрокам: {"; ".join(pls)}'
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'\s*(?P<amount>\d+).*'),
        argument_miss_msg='Пришли сообщение в формате "/karma_reduce d+(кол-во) @user1, @user2"'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _karma_reduce(self, update: Update, match, players, *args, **kwargs):
        karma = int(match.group('amount'))
        pls = []
        for player in players:
            self._karma_handler('karma_reduce', update.player, player, -karma, 'Админское снятие кармы.')
            pls.append(player.nickname)

        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'Карма успешно снята(-{karma}☯️) игрокам: {"; ".join(pls)}'
        )
