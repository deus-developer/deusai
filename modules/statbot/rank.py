import functools
import re
import datetime

from telegram import ParseMode
from telegram.ext import Dispatcher

from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, Update

from modules import BasicModule
from models import Rank
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_players
from utils.functions import CustomInnerFilters, get_link
from telegram.utils.helpers import mention_html

class RankModule(BasicModule): #TODO: Полностью переработать

    module_name = 'rank'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('rank_ls'), self._rank_ls,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('rank_create'), self._rank_create,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('rank_remove'), self._rank_remove,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('promote'), self._promote,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_goat_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('demote'), self._demote,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_goat_chat]))

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(regexp=re.compile(r'\s*\[(?P<emoji>.+)\]\s*\[(?P<name>.+)\]\s*\[(?P<priority>\d+)\]\s*(?P<text>[\s\S]*)'),
                     argument_miss_msg='Пришли сообщение в формате "/rank_create [Эмодзи] [Название] [Приоритет(число)]\n Текст поздравления"')
    def _rank_create(self, update: Update, match, *args, **kwargs):
        message = update.telegram_update.message
        emoji, name, text = match.group('emoji', 'name', 'text')
        priority = int(match.group('priority'))

        rank, created = Rank.get_or_create(name=name, emoji=emoji, description=text, priority=priority)
        if not created:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Ранг "{name}" уже существует.')
        rankp = Rank.select().where(Rank.priority == priority).count()

        if rankp > 1:
            rank.delete_instance()
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Приоритет {priority} уже существует.') 
        rank.emoji = emoji
        rank.priority = priority
        rank.description = text
        rank.save()
        return self.message_manager.send_message(chat_id=message.chat_id,
                                                text=f'Ранг "{name}" создан.')

    @permissions(is_admin)
    @command_handler(regexp=re.compile(r'(?P<name>.+)'),
                     argument_miss_msg='Пришли сообщение в формате "/rank_remove Название"')
    def _rank_remove(self, update: Update, match, *args, **kwargs):
        message = update.telegram_update.message
        name = match.group('name')
        rank = Rank.get_or_none(name=name)
        if not rank:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Ранга "{name}" не существует.')
        rank.remove_()
        return self.message_manager.send_message(chat_id=message.chat_id,
                                                text=f'Ранг "{name}" удалён, а все его носители понижены в ранге.')

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/promote @User1 @User2 ..."')
    def _promote(self, update: Update, players, *args, **kwargs):
        message = update.telegram_update.message
        if update.invoker.is_admin:
            access = players
        else:
            access = []
            for group in update.player.liders:
                access.extend([pl.nickname for pl in group.members])
        if not access:
            return self.message_manager.send_message(chat_id = message.chat_id,
                                                    text=f'Нет доступа.')
        pls = []
        for pl in players:
            rank = Rank.select()\
                    .where(Rank.priority > pl.rank.priority)\
                    .order_by(Rank.priority)\
                    .limit(1)
            if not rank:
                self.message_manager.send_message(chat_id=message.chat_id,
                                                    text=f'У игрока {mention_html(pl.telegram_user_id, pl.nickname)} предельный ранг ({pl.rank.name}).',
                                                    parse_mode=ParseMode.HTML)
                continue
            pl.rank = rank[0]
            pl.save()
            pls.append(pl)
        if not pls:
            return
        self.message_manager.send_message(chat_id=message.chat_id,
                                            text=f'Игроки: {", ".join([mention_html(pl.telegram_user_id, pl.nickname) for pl in pls])} получили повышение',
                                            parse_mode=ParseMode.HTML)
        self._promote_message(players=pls)

    def _promote_message(self, players=None):
        for player in players:
            self.message_manager.send_message(  chat_id=player.telegram_user.chat_id,
                                                text=player.rank.description,
                                                parse_mode=ParseMode.HTML)
            
    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/demote @User1 @User2 ..."')
    def _demote(self, update: Update, players, *args, **kwargs):
        message = update.telegram_update.message
        if update.invoker.is_admin:
            access = players
        else:
            access = []
            for group in update.player.liders:
                access.extend([pl.nickname for pl in group.members])
        if not access:
            return self.message_manager.send_message(chat_id = message.chat_id,
                                                    text=f'Нет доступа.')
        pls = []
        for pl in players:
            rank = Rank.select()\
                    .where(Rank.priority < pl.rank.priority)\
                    .order_by(Rank.priority.desc())\
                    .limit(1)
            if not rank:
                self.message_manager.send_message(chat_id=message.chat_id,
                                                    text=f'У игрока {mention_html(pl.telegram_user_id, pl.nickname)} минимальный ранг ({pl.rank.name}).\n Можешь удалить его, через /remove_player',
                                                    parse_mode=ParseMode.HTML)
                continue
            pl.rank = rank[0]
            pl.save()
            pls.append(pl)

        if not pls:
            return

        self._promote_message(players=pls)
        self.message_manager.send_message(chat_id=message.chat_id,
                                            text=f'Игроки: {", ".join([mention_html(pl.telegram_user_id, pl.nickname) for pl in pls])} получили понижение',
                                            parse_mode=ParseMode.HTML)

    def _rank_ls(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        if not (update.invoker or update.player.liders):
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Нет доступа.')
        output = ['Список рангов:\n']
        for idx, rank in enumerate(Rank.select().order_by(Rank.priority.desc()), 1):
            output.append(f'{idx}. {rank.name} [{rank.emoji}] - {len(rank.players)}ч.')
        if len(output) == 1:
            output.append('Ой, а где они???')
        self.message_manager.send_split(chat_id=message.chat_id, msg='\n'.join(output), n=30)