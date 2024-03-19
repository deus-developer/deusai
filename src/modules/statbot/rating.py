import html
from functools import partial
from io import StringIO, RawIOBase
from typing import Optional, List, Dict, Any, TypedDict

import peewee
from jinja2 import Template
from telegram.ext import Dispatcher

from src.core import (
    EventManager,
    MessageManager,
    InnerHandler,
    CommandFilter,
    InnerUpdate,
)
from src.decorators.permissions import permissions, is_admin
from src.models import Player, Group
from src.modules import BasicModule
from src.utils.functions import CustomInnerFilters


class RatingFieldInfo(TypedDict):
    field: peewee.Field
    label: str
    visible: bool


class BytesIOWrapper(RawIOBase):
    def __init__(self, file, encoding="utf-8", errors="strict"):
        self.file, self.encoding, self.errors = file, encoding, errors
        self.buffer = b""

    def readinto(self, buffer):
        if not self.buffer:
            self.buffer = self.file.read(4096).encode(self.encoding, self.errors)
            if not self.buffer:
                return 0

        length = min(len(buffer), len(self.buffer))
        buffer[:length] = self.buffer[:length]
        self.buffer = self.buffer[length:]
        return length

    def readable(self):
        return True


class RatingAbstractModule(BasicModule):
    stream: StringIO

    COMMANDS: Dict[str, RatingFieldInfo] = {
        "bmtop": {"field": Player.sum_stat, "label": "Топ игроков", "visible": False},
        "rushtop": {"field": Player.attack, "label": "Топ дамагеров", "visible": False},
        "hptop": {"field": Player.hp, "label": "Топ танков", "visible": False},
        "acctop": {
            "field": Player.accuracy,
            "label": "Топ снайперов",
            "visible": False,
        },
        "agtop": {"field": Player.agility, "label": "Топ ловкачей", "visible": False},
        "ortop": {"field": Player.oratory, "label": "Топ дипломатов", "visible": False},
        "raidtop": {
            "field": Player.raid_points,
            "label": "Топ рейдеров",
            "visible": True,
        },
        "dzentop": {"field": Player.dzen, "label": "Топ дзенистых", "visible": False},
        "armortop": {
            "field": Player.defence,
            "label": "Топ укреплённых",
            "visible": False,
        },
    }

    def _top(self, field_data: RatingFieldInfo):
        def handler(self, update: InnerUpdate):
            with StringIO() as self.stream:
                self._send_message(
                    update.effective_chat_id,
                    update.player,
                    field_data,
                    update.command.argument,
                )

        handler.__doc__ = f'Выдает {field_data["label"].lower()}'
        return partial(handler, self)

    def _send_message(self, *args, **kwargs):
        raise NotImplementedError


class RatingModule(RatingAbstractModule):
    """
    responds to different rating commands
    """

    module_name = "rating"
    TOP_SIZE = 5

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        for command in self.COMMANDS:
            self.add_inner_handler(
                InnerHandler(
                    CommandFilter(command),
                    self._top(self.COMMANDS[command]),
                    [
                        CustomInnerFilters.from_player,
                        CustomInnerFilters.from_active_chat,
                    ],
                )
            )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter("top_ls"),
                self._top_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def _top_ls(self, update: InnerUpdate):
        text = "\n".join(f'/{command} - {field_info["label"]}' for command, field_info in self.COMMANDS.items())

        return self.message_manager.send_message(chat_id=update.effective_chat_id, text=text)

    def _send_message(
        self,
        chat_id: int,
        player: Player,
        field_data: RatingFieldInfo,
        group_name: Optional[str],
    ):
        if group_name:
            group = Group.get_by_name(group_name)
        else:
            group = None

        if group and not player.telegram_user.is_admin and group not in player.members:
            return self.message_manager.send_message(
                chat_id=chat_id,
                text="Доступ запрещен",
            )

        if group is None:
            group = player.members.where(Group.type == "goat").get_or_none()
            if group is None:
                group = player.members.where(Group.type == "gang").get_or_none()

            if not group:
                return self.message_manager.send_message(
                    chat_id=chat_id,
                    text="Что-то я не вижу твоего козла, скинь панельку своей банды или обратись к админам",
                )

        label = field_data["label"]
        if group:
            label = f"{label} группы {group.name}"

        self._write_msg(
            player,
            Player.get_top(field_data["field"], group),
            label,
            field_data["visible"],
        )
        self.stream.seek(0)

        self.message_manager.send_message(chat_id=chat_id, text=self.stream.read())

    def _write_msg(self, player_called: Player, query, label: str, visible: bool):
        rating: List[str] = [f"<b>{html.escape(label)}</b>:"]
        for index, player in enumerate(query, 1):
            if index < self.TOP_SIZE or player_called.nickname == player.nickname:
                if index > self.TOP_SIZE:
                    rating.append("    ... ")
                rating.append(self._format_record(index, player, player_called, visible))

        text = "\n".join(rating)
        self.stream.write(text)

    def _format_record(self, _: int, player: Player, called: Player, visible: bool) -> str:
        if player.nickname == called.nickname:
            mention = player.mention_html()
        else:
            mention = html.escape(player.nickname)

        if visible:
            return f'{player.idx}) {mention}: {getattr(player, "value", 0)}'
        return f"{player.idx}) {mention}"


class AdminRatingModule(RatingAbstractModule):
    module_name = "rating_admin"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        for command in self.COMMANDS:
            self.add_inner_handler(
                InnerHandler(
                    CommandFilter(f"{command}_all"),
                    self._top(self.COMMANDS[command]),
                    [CustomInnerFilters.from_player],
                )
            )

        self._rating_template = Template(open("static/templates/admin_top.html", "r", encoding="utf-8").read())
        super().__init__(event_manager, message_manager, dispatcher)

    def _top(self, field_data: RatingFieldInfo):
        @permissions(is_admin)
        def handler(self, update: InnerUpdate):
            with StringIO() as self.stream:
                self._send_message(update.effective_chat_id, update.player, field_data)

        return partial(handler, self)

    def _send_message(self, chat_id: int, from_player: Player, field_data: RatingFieldInfo):
        self.message_manager.send_message(chat_id=chat_id, text="Подожди, сейчас подготовлю файл")

        self._write_msg(from_player, Player.get_top(field_data["field"]), field_data["label"])

        self.stream.seek(0)

        self.message_manager.bot.send_document(
            chat_id=chat_id, document=BytesIOWrapper(self.stream), filename="top.html"
        )

    def _write_msg(self, _: Player, query, label: str):
        total = 0
        tops: List[Dict[str, Any]] = []

        for player in query:
            tops.append(
                {
                    "rank": player.idx,
                    "link": self.link_to_player(player),
                    "value": player.value,
                }
            )
            total += player.value

        text = self._rating_template.render(tops=tops, total=total, caption=label)
        self.stream.write(text)

    def _format_record(self, _: int, player: Player) -> str:
        activity_flag = player.get_activity_flag()
        mention = self.link_to_player(player)

        return (
            f"<tr>"
            f"    <td>{player.idx}) {activity_flag}</td>"
            f"    <td>{mention}</td>"
            f"    <td>{player.value}</td>"
            f"</tr>"
        )

    @staticmethod
    def link_to_player(player: Player) -> str:
        return player.mention_html()
