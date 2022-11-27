import datetime
import re
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

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
    GroupPlayerThrough,
    Player
)
from modules import BasicModule
from utils.functions import CustomInnerFilters


class FreezeModule(BasicModule):
    """
    Freeze commands
    """
    module_name = 'freeze'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('freeze'), self._freeze,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('unfreeze'), self._unfreeze,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('unfreeze_a'), self._auto_unfreeze,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('freeze_ls'), self._freeze_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

        self.event_manager.scheduler.add_job(self._auto_unfreeze, 'interval', hours=1)

    @permissions(is_admin)
    @command_handler()
    def _freeze_ls(self, update: Update, *args, **kwargs):  # TODO: Оптимизировать формирование ссылки на профиль
        groups = update.command.argument.split()
        now = datetime.datetime.now()

        players = []
        if groups:
            groups = Group.select() \
                .where((Group.name << groups) | (Group.alias << groups))

            players = Player.select() \
                .join(GroupPlayerThrough, on=(Player.id == GroupPlayerThrough.player_id)) \
                .where(GroupPlayerThrough.group << groups) \
                .filter(Player.frozen == True) \
                .order_by(Player.frozendate.desc()) \
                .distinct()
        else:
            players = Player.select() \
                .where((Player.is_active == True) & (Player.frozen == True)) \
                .order_by(Player.frozendate.desc())

        output = ['Список людей в отпуске:']
        for idx, player in enumerate(players, 1):
            delta = player.frozendate - now
            time = delta.days * 24 + delta.seconds // 3600
            time = time if time > 0 else 0
            output.append(f'{idx}. {mention_html(player.telegram_user_id, player.nickname)} [{time} час.]')

        self.message_manager.send_split(
            chat_id=update.telegram_update.message.chat_id,
            msg='\n'.join(output), n=30
        )

    @command_handler(
        regexp=re.compile(r'\s*(?P<days>\d+).*'),
        argument_miss_msg='Пришли сообщение в формате "/freeze d+(дней) @user1, @user2"'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _freeze(self, update: Update, match, players, *args, **kwargs):  # TODO: Оптимизировать процесс работы с базой; Оптимизировать генерацию ссылок на профиль
        message = update.telegram_update.message
        player = update.player
        """
        Имеет параметры: d+(кол-во дней) @user1, @user2
        Выдаёт отпуск игроку(Player.frozen)
        """
        days = int(match.group('days'))
        if days <= 0:
            return

        if not player.telegram_user.is_admin:
            groups = player.liders
            access = []
            for group in groups:
                access.extend(group.members)

            pls = []
            for pl in players:
                if pl in access:
                    pls.append(pl)

            if len(pls) == 0:
                return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')
        else:
            pls = players
        last_frozen_date = datetime.datetime.now() + datetime.timedelta(days=days)
        for pl in pls:
            pl.frozen = True
            pl.frozendate = last_frozen_date
            pl.save()
        pls = [mention_html(pl.telegram_user_id, pl.nickname) for pl in pls]
        self.message_manager.send_message(chat_id=message.chat_id, text=f'✅Отпуска выданы игрокам: {"; ".join(pls)}', parse_mode='HTML')

    @command_handler(argument_miss_msg='Пришли сообщение в формате "/unfreeze @user1, @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def _unfreeze(self, update: Update, players, *args, **kwargs):  # TODO: Оптимизировать процесс работы с базой; Оптимизировать генерацию ссылок на профиль
        """
        Имеет параметры: @user1, @user2...
        Снимает отпуск игроку(Player.frozen)
        """
        message = update.telegram_update.message
        player = update.player

        if not player.telegram_user.is_admin:
            groups = player.liders
            access = []
            for group in groups:
                access.extend(group.members)

            pls = []
            for pl in players:
                if pl in access:
                    pls.append(pl)

            if len(pls) == 0:
                self._auto_unfreeze()
                return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')
        else:
            pls = players

        last = datetime.datetime.now()

        for pl in pls:
            pl.frozen = False
            pl.frozendate = last
            pl.save()
        pls = [mention_html(pl.telegram_user_id, pl.nickname) for pl in pls]
        self.message_manager.send_message(
            chat_id=message.chat_id,
            text=f'✅Отпуска сняты у игроков: {"; ".join(pls)}', parse_mode='HTML'
        )

    def _auto_unfreeze(self, *args, **kwargs):  # TODO: Оптимизировать процесс работы с базой
        last = datetime.datetime.now()
        frozen_players = Player.select() \
            .where(Player.frozendate <= last) \
            .filter(Player.frozen == True)

        for pl in frozen_players:
            pl.frozen = False
            pl.frozendate = last
            pl.save()
