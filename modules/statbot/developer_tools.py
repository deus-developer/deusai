import datetime

import peewee
from telegram.ext import Dispatcher

from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import (
    permissions
)
from decorators.permissions import is_developer
from models import (
    KarmaTransition,
    Player,
    PlayerRecivedThrough,
    RaidsInterval
)
from modules import BasicModule
from modules.statbot.karma import Karma
from utils.functions import CustomInnerFilters


def pings_default():
    return {
        'sendpin': True,
        'echo': True,
        'drop_head': True,
        'ping': True,
        'weekly_report': True,
        'notify_raid_3': True,
        'notify_raid_tz_10': True,
        'notify_raid_tz': True,
        'notify_raid_tz_report': True,
    }


class DeveloperToolsModule(BasicModule):

    module_name = 'dev_tools'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='duplicating_players', description='Выводит игроков с похожими никами'),
                self._duplicating_players,
                custom_filters=[CustomInnerFilters.private]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('commands'),
                self._commands,
                custom_filters=[CustomInnerFilters.private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raids_optimize'),
                self._raids_optimize,
                custom_filters=[CustomInnerFilters.private]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_developer)
    def _raids_optimize(self, update: Update):
        now = datetime.datetime.now()
        interval = RaidsInterval.interval_by_date(now, offset=0)

        players_ids = [x.id for x in Player.select().where(Player.is_active == True)]

        players_q = KarmaTransition.select(
            peewee.fn.SUM(KarmaTransition.amount).alias('total'),
            PlayerRecivedThrough.player_id.alias('player_id'),
        ) \
            .join(PlayerRecivedThrough, on=(PlayerRecivedThrough.transition_id == KarmaTransition.id)) \
            .where(
            (PlayerRecivedThrough.player_id << players_ids) &
            (KarmaTransition.created_date.between('2020-09-12 20:48:10', '2020-09-12 20:48:19')) &
            (KarmaTransition.module_name == 'raid_rewards') &
            (KarmaTransition.description == 'Обработка недели рейдов.')
        ) \
            .group_by(PlayerRecivedThrough.player_id) \
            .dicts()
        interval_text = f'с {interval.start_date.strftime("%d.%m %H-%M")} по {interval.last_date.strftime("%d.%m %H-%M")}'

        for player in players_q:
            pl = Player.get_or_none(id=player['player_id'])
            if not pl:
                print(f'{player["player_id"]} error (:')
                continue

            u = Update()
            u.karma_ = Karma(module_name='raids_optimize', recivier=pl, sender=pl, amount=-player['total'], description=f'Аннулирование наград за рейды')
            self.event_manager.invoke_handler_update(u)
            self.message_manager.send_message(
                chat_id=pl.telegram_user_id, text='Я аннулировал все зачисления/списания кармы по рейдам.\n'
                                                  f'За период {interval_text}.\n'
                                                  f'Прибавил тебе = {-player["total"]}☯️'
            )

    @permissions(is_developer)
    def _commands(self, update: Update):  # TODO: Добавить вывод описания всех обработчиков
        output = f'Всего обработчиков в боте: {len(self.event_manager.handlers)}\n'
        output += 'Те что являются командами ниже:\n'
        for handler in self.event_manager.handlers:
            if isinstance(handler.filter, CommandFilter):
                output += f'▫️ /{handler.filter.command}'
                if handler.filter.description:
                    output += f'\t▫️{handler.filter.description}'
                output += '\n'

        update.telegram_update.message.reply_text(text=output)

    @permissions(is_developer)
    def _duplicating_players(self, update: Update):
        message = update.telegram_update.message
        remaster = []
        for player in Player.select():
            duplings = Player.select().where(peewee.fn.LOWER(Player.nickname).contains(player.nickname))
            if duplings.count() == 1:
                continue
            duplings_ = []
            for x in duplings:
                if x.nickname != player.nickname:
                    duplings_.append(f'\t\t\t{x.nickname}')

            duplings_ = '\n'.join(duplings_)
            remaster.append(f'{player.nickname}:\n{duplings_}')
        if not remaster:
            remaster = ['Упс, нет таких']
        self.message_manager.send_split(chat_id=message.chat_id, msg='\n'.join(remaster), n=50)
