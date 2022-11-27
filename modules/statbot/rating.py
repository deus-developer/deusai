import functools
from io import (
    RawIOBase,
    StringIO
)

import telegram
from jinja2 import Template
from telegram import ChatAction
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from core import (
    CommandFilter,
    EventManager,
    Handler,
    MessageManager,
    Update
)
from decorators.permissions import (
    is_admin,
    permissions
)
from models import (
    Group,
    Player
)
from modules import BasicModule
from utils.functions import CustomInnerFilters


class BytesIOWrapper(RawIOBase):
    def __init__(self, file, encoding='utf-8', errors='strict'):
        self.file, self.encoding, self.errors = file, encoding, errors
        self.buf = b''

    def readinto(self, buf):
        if not self.buf:
            self.buf = self.file.read(4096).encode(self.encoding, self.errors)
            if not self.buf:
                return 0
        length = min(len(buf), len(self.buf))
        buf[:length] = self.buf[:length]
        self.buf = self.buf[length:]
        return length

    def readable(self):
        return True


class RatingAbstractModule(BasicModule):
    stream: StringIO

    COMMANDS = {
        'bmtop': {
            'field': Player.sum_stat,
            'label': 'Топ игроков',
            'visible': False
        },
        'rushtop': {
            'field': Player.attack,
            'label': 'Топ дамагеров',
            'visible': False
        },
        'hptop': {
            'field': Player.hp,
            'label': 'Топ танков',
            'visible': False
        },
        'acctop': {
            'field': Player.accuracy,
            'label': 'Топ снайперов',
            'visible': False
        },
        'agtop': {
            'field': Player.agility,
            'label': 'Топ ловкачей',
            'visible': False
        },
        'ortop': {
            'field': Player.oratory,
            'label': 'Топ дипломатов',
            'visible': False
        },
        'karmatop': {
            'field': Player.karma,
            'label': 'Топ святых',
            'visible': True
        },
        'raidtop': {
            'field': Player.raid_points,
            'label': 'Топ рейдеров',
            'visible': True
        },
        'dzentop': {
            'field': Player.dzen,
            'label': 'Топ дзенистых',
            'visible': False
        },
        'ranktop': {
            'field': Player.rank_id,
            'label': 'Топ ранговых',
            'visible': False
        },
        'rewardtop': {
            'field': Player.raid_reward,
            'label': 'Топ профитных',
            'visible': False
        },
        'armortop': {
            'field': Player.defence,
            'label': 'Топ укреплённых',
            'visible': False
        },
    }

    def _top(self, field_data):
        def handler(self, update: Update):
            with StringIO() as self.stream:
                chat_id = update.telegram_update.message.chat_id
                from_player = update.player
                self._send_message(chat_id, from_player, field_data, update.command.argument)

        handler.__doc__ = f'Выдает {field_data["label"].lower()}'
        return functools.partial(handler, self)

    def _send_message(self, *args, **kwargs):
        raise NotImplementedError


class RatingModule(RatingAbstractModule):
    """
    responds to different rating commands
    """
    module_name = 'rating'
    TOP_SIZE = 5

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        for command in self.COMMANDS:
            self.add_inner_handler(
                Handler(
                    CommandFilter(command), self._top(self.COMMANDS[command]),
                    [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
                )
            )
        self.add_inner_handler(
            Handler(
                CommandFilter('top_ls'), self._top_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def _top_ls(self, update: Update):
        return self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text='\n'.join([f'/{command} - {_dict.get("label", "топ")}' for command, _dict in self.COMMANDS.items()])
        )

    def _send_message(self, chat_id, from_player: Player, field_data, group):
        group = Group.get_by_name(group)
        if group and not from_player.telegram_user.is_admin and group not in from_player.members:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text='Доступ запрещен',
            )
        elif not from_player.telegram_user.is_admin and not group:
            group = from_player.members.where(Group.type == 'goat').first() \
                    or from_player.members.where(Group.type == 'gang').first()
            if not group:
                return self.message_manager.send_message(
                    chat_id=chat_id,
                    text='Что-то я не вижу твоего козла, скинь панельку своей банды или обратись к админам'
                )
        label = field_data['label']
        if group:
            label = f'{label} группы {group.name}'
        self._write_msg(from_player, Player.get_top(field_data['field'], group), label, field_data['visible'])
        self.stream.seek(0)
        self.message_manager.send_message(
            chat_id=chat_id,
            text=self.stream.read(),
            parse_mode=telegram.ParseMode.HTML,
            disable_web_page_preview=True
        )

    def _write_msg(self, player_called: Player, query, label, visible):
        res = [f'<b>{label}</b>:']
        for index, player in enumerate(query, 1):
            if index < self.TOP_SIZE or player_called.nickname == player.nickname:
                if index > self.TOP_SIZE:
                    res.append('    ... ')
                res.append(self._format_record(index, player, player_called, visible))

        self.stream.write('\n'.join(res))

    def _format_record(self, index, player: Player, called, visible):
        nickname = player.nickname
        if player.nickname == called.nickname:
            nickname = mention_html(player.telegram_user_id, player.nickname)
        return f'{player.idx}) {nickname}: {getattr(player, "value", 0)}' if visible else f'{player.idx}) {player.nickname}'


class AdminRatingModule(RatingAbstractModule):
    module_name = 'rating_admin'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher = None):

        for command in self.COMMANDS:
            self.add_inner_handler(
                Handler(
                    CommandFilter(f'{command}_all'), self._top(self.COMMANDS[command]),
                    [CustomInnerFilters.from_player]
                )
            )
            self.add_inner_handler(
                Handler(
                    CommandFilter(f'{command}_all_u'),
                    self._top(self.COMMANDS[command], by_username=True),
                    [CustomInnerFilters.from_player]
                )
            )

        super().__init__(event_manager, message_manager, dispatcher)

    def _top(self, field_data, by_username=False):
        @permissions(is_admin)
        def handler(self, update: Update):
            with StringIO() as self.stream:
                chat_id = update.telegram_update.message.chat_id
                from_player = update.player
                self._send_message(chat_id, from_player, field_data, by_username)

        return functools.partial(handler, self)

    def _send_message(self, chat_id, from_player, field_data, by_username):
        self.message_manager.send_message(
            chat_id=chat_id,
            text='Подожди, сейчас подготовлю файл',
            parse_mode=telegram.ParseMode.HTML,
            disable_web_page_preview=True
        )

        self._write_msg(from_player, Player.get_top(field_data['field']), field_data['label'], by_username)

        self.stream.seek(0)

        self.message_manager.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.UPLOAD_DOCUMENT
        )

        self.message_manager.bot.send_document(
            chat_id=chat_id, document=BytesIOWrapper(self.stream), filename='top.html'
        )

    def _write_msg(self, player_called: Player, query, label, by_username=False):
        template = Template(open('files/templates/admin_top.html', 'r', encoding='utf-8').read())
        total = 0
        tops = []
        for index, player in enumerate(query, 1):
            tops.append(
                {
                    'rank': player.idx,
                    'link': self.link_to_player(player, by_username),
                    'value': player.value
                }
            )
            total += player.value
        self.stream.write(template.render(tops=tops, total=total, caption=label))

    def _format_record(self, index, player: Player, by_username=False):
        return (f'<tr>'
                f'    <td>{player.idx}) {player.get_activity_flag()}</td>'
                f'    <td>{self.link_to_player(player, by_username)}</td>'
                f'    <td>{player.value}</td>'
                f'</tr>')

    @staticmethod
    def link_to_player(player: Player, by_username=False):
        return f'<a href="tg://resolve?domain={player.telegram_user.username}">' \
               f'{player.nickname if not by_username else player.telegram_user.username}' \
               f'</a>'
