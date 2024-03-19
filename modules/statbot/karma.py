import re
from dataclasses import dataclass
from typing import List, Dict, Match

from telegram.ext import Dispatcher

from core import EventManager, MessageManager, InnerHandler, UpdateFilter, CommandFilter, InnerUpdate
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_players
from models import Player, KarmaTransition
from models.raid_assign import RaidStatus
from modules import BasicModule
from modules.statbot.parser import GroupParseResult
from utils.functions import CustomInnerFilters
from wasteland_wars.schemas import GangMember


@dataclass
class Karma:
    module_name: str
    recivier: Player
    sender: Player
    amount: int
    description: str


class KarmaModule(BasicModule):
    """
    Handle player groups
    """
    module_name = 'karma'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('gang'), self._update_from_panel_gang))
        self.add_inner_handler(InnerHandler(UpdateFilter('karma_transaction'), self._karma))

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('karma_add'),
                self._karma_add,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('karma_reduce'),
                self._karma_reduce,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    def _karma(self, update: InnerUpdate):
        karma_transaction: Karma = update.karma_transaction

        self._karma_handler(
            module_name=karma_transaction.module_name,
            sender=karma_transaction.sender,
            recivier=karma_transaction.recivier,
            amount=karma_transaction.amount,
            description=karma_transaction.description
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
                raids21=recivier.raids21,
                raid_points=recivier.raid_points,
                loose_raids=recivier.loose_raids,
                loose_weeks=recivier.loose_weeks
            )
            recivier.save()

    def _update_from_panel_gang(self, update: GroupParseResult):
        message = update.telegram_update.message

        updates = 0

        ganster_by_nickname: Dict[str, GangMember] = {
            gangster.nickname: gangster
            for gangster in update.gang.members
        }

        for gangster_player in Player.select().where(Player.nickname << list(ganster_by_nickname.keys())):
            if not (gangster := ganster_by_nickname.get(gangster_player.nickname)):
                continue

            raid_assign = gangster_player.raid_near_time(message.forward_date)
            if not (raid_assign and update.date > raid_assign.last_update):
                continue

            if (
                raid_assign.km_assigned == gangster.kilometr and
                gangster.status == '👊' and
                raid_assign.status not in (RaidStatus.CONFIRMED, RaidStatus.IN_PROCESS)
            ):
                raid_assign.status = RaidStatus.IN_PROCESS
                updates += 1
                self.message_manager.send_message(
                    chat_id=gangster_player.telegram_user_id,
                    text='Твоё участие в рейде подтвержденно, через панель банды.\n'
                         'Не забудь отправить <b>ПОЛНЫЙ</b> пип бой, после рейда.\n'
                         f'<b>{raid_assign.time}</b>',
                )
            elif (
                raid_assign.status == RaidStatus.IN_PROCESS and
                (
                    raid_assign.km_assigned != gangster.kilometr or
                    gangster.status != '👊'
                )
            ):
                raid_assign.status = RaidStatus.LEFTED
                updates += 1
                self.message_manager.send_message(
                    chat_id=gangster_player.telegram_user_id,
                    text=f'Эй, стой! Куда с рейда убежал?\n РЕЙД НА {raid_assign.km_assigned}км. '
                         f'!!!ОДУМАЙСЯ!!!\n{raid_assign.time}'
                )
            elif (
                raid_assign.status == RaidStatus.ACCEPTED and
                raid_assign.km_assigned >= gangster.kilometr and
                gangster.status == '👟'
            ):
                raid_assign.status = RaidStatus.ACCEPTED

            raid_assign.last_update = update.date
            raid_assign.save()

        if updates < 1:
            return

        if update.player is None:
            return

        self._karma_handler(
            'raid',
            update.player,
            update.player,
            updates * 2,
            f'Обновление рейд статусов(панель)[{updates}]'
        )

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

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'\s*(?P<amount>\d+).*'),
        argument_miss_msg='Пришли сообщение в формате "/karma_add d+(кол-во) @user1, @user2"'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _karma_add(self, update: InnerUpdate, match: Match, players: List[Player]):
        karma = int(match.group('amount'))

        nicknames: List[str] = []
        for player in players:
            self._karma_handler(
                'karma_add',
                update.player,
                player,
                karma,
                'Админское начисление кармы.'
            )
            nicknames.append(player.nickname)

        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Карма успешно начислена(+{karma}☯️) игрокам: {"; ".join(nicknames)}'
        )

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'\s*(?P<amount>\d+).*'),
        argument_miss_msg='Пришли сообщение в формате "/karma_reduce d+(кол-во) @user1, @user2"'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _karma_reduce(self, update: InnerUpdate, match: Match, players: List[Player]):
        karma = int(match.group('amount'))

        nicknames: List[str] = []
        for player in players:
            self._karma_handler(
                'karma_reduce',
                update.player,
                player,
                -karma,
                'Админское снятие кармы.'
            )
            nicknames.append(player.nickname)

        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Карма успешно снята(-{karma}☯️) игрокам: {"; ".join(nicknames)}'
        )
