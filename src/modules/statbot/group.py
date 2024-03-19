import datetime
import re
from functools import partial
from typing import Optional, Match, List

from telegram.ext import Dispatcher

from src.core import (
    EventManager,
    MessageManager,
    InnerHandler,
    UpdateFilter,
    CommandFilter,
    InnerUpdate,
)
from src.decorators import command_handler, permissions
from src.decorators.permissions import is_admin, is_lider, or_
from src.decorators.users import get_players
from src.models import Group, Player, GroupPlayerThrough
from src.modules import BasicModule
from src.modules.statbot.parser import GroupParseResult
from src.utils import format_number, format_number_padded
from src.utils.functions import CustomInnerFilters
from src.wasteland_wars import constants


class GroupModule(BasicModule):
    """
    Handle player groups
    """

    module_name = "group"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_inner_handler(InnerHandler(UpdateFilter("goat"), self.goat_handler))
        self.add_inner_handler(InnerHandler(UpdateFilter("gang"), self.gang_handler))

        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_alias", description="Установить alias для группы"),
                self.group_alias,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_rename", description="Переименовать группу"),
                self.group_rename,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_create", description="Создать группу"),
                self.group_create,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_delete", description="Удалить группу"),
                partial(self.group_delete, force=False),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_delete_with_players", description="Удалить группу с игроками"),
                partial(self.group_delete, force=True),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_add", description="Добавить игрока в группу"),
                self.group_add,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_kick", description="Удалить игрока из группы"),
                self.group_kick,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_clear", description="Очистить группу от игроков"),
                self.group_clear,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_ls", description="Список групп[ы]"),
                self.group_ls(),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="group_ls_all", description="Полный список групп[ы]"),
                self.group_ls(True),
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="visible", description="Видимость группу"),
                self.visible,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="lider_set", description="Установить лидера группы"),
                self.lider_set,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="lider_kick", description="Удалить лидера группы"),
                self.lider_kick,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def goat_handler(self, update: GroupParseResult):
        if update.goat is None:
            return

        message = update.telegram_update.message

        goat = self.__handle_group(
            leader_nickname=update.goat.leader_nickname,
            group_name=update.goat.name,
            group_type="goat",
            date=update.date,
        )

        Group.update({Group.parent: None}).where(Group.parent == goat, Group.type == "gang").execute()

        gang_names: List[str] = [gang.gang_name for gang in update.goat.gangs]

        gangs = [
            {
                "name": gang,
                "type": "gang",
                "parent": goat,
                "is_active": goat.is_active,
                "last_update": update.date,
            }
            for gang in gang_names
        ]

        Group.insert(gangs).on_conflict(conflict_target=[Group.name, Group.type], update={Group.parent: goat}).execute()

        goat.last_update = update.date
        goat.league = update.goat.league_name

        goat.save()

        return self.message_manager.send_message(text="Данные сохранены.", chat_id=message.chat_id)

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg="Укажи группу, которую хочешь удалить")
    def group_delete(self, update: InnerUpdate, force: bool):
        group_name = update.command.argument
        chat_id = update.effective_chat_id

        group = Group.get_by_name(group_name)
        if group is None:
            return self.message_manager.send_message(chat_id=chat_id, text="Я не знаю такой группы")

        if group.members or group.liders:
            if not force:
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f"В группе есть {len(group.members) or len(group.liders)} участников, "
                    f"для их удаления выбери другую команду",
                )
            else:
                group.members.clear()
                group.liders.clear()
                group.delete_instance()
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f"Группа {group_name} и ее участники удалены",
                )
        else:
            group.delete_instance()
            self.message_manager.send_message(chat_id=chat_id, text=f"Группа {group_name} удалена")


    def _group_unique_gansters(self, group_types: List[str], gangster_ids: List[int]):
        subquery = (
            GroupPlayerThrough.select(GroupPlayerThrough.id)
            .join(Group, on=(Group.id == GroupPlayerThrough.group_id))
            .join(Player, on=(Player.id == GroupPlayerThrough.player_id))
            .where((Group.type << group_types) & (Player.id << gangster_ids))
        )

        query = GroupPlayerThrough.delete().where(GroupPlayerThrough.id << subquery)
        return query.execute()

    def gang_handler(self, update: GroupParseResult) -> None:
        if update.gang is None:
            return

        message = update.telegram_update.message
        gang = self.__handle_group(update.gang.leader_nickname, update.gang.name, "gang", message.forward_date)
        if gang is None:
            return

        goat = self.__handle_group(None, update.gang.goat_name, "goat", message.forward_date)

        gangster_nicknames: List[str] = [gangster.nickname for gangster in update.gang.members]

        gangster_ids: List[int] = []
        for player in Player.select().where(Player.nickname << gangster_nicknames):
            gangster_nicknames.remove(player.nickname)
            gangster_ids.append(player.id)

        self._group_unique_gansters(["gang", "goat"], gangster_ids)

        gang.members.add(gangster_ids)

        if goat:
            goat.members.add(gangster_ids)

        missed: List[str] = gangster_nicknames.copy()

        self.message_manager.send_message(text="Данные сохранены", chat_id=message.chat_id)

        if missed:
            self.message_manager.send_message(
                text=f'Игроки {", ".join(missed)} не добавили свою пипку',
                chat_id=message.chat_id,
            )

    def group_ls(self, show_all_groups: bool = False):
        def friendly_players_handler(self, chat_id: int, group: Group, players: List[Player]):
            total_combat_power = 0
            total_dzens = 0

            liders: List[str] = [lider.mention_html() for lider in group.liders]

            text: List[str] = [
                f"<b>Список группы:</b> <code>{group.name}</code>",
                f'<b>Лидеры:</b> {";".join(liders)}\n',
            ]
            for index, player in enumerate(players, 1):
                fraction_emoji = constants.fraction_icons.get(player.fraction, "❓")
                combat_power_formatted = format_number_padded(player.sum_stat, 3, 5)
                text.append(
                    f"{index:02d}|🏵<code>{player.dzen:02d}</code>|"
                    f"🎓<code>{combat_power_formatted}</code>"
                    f"|{fraction_emoji}|{player.mention_html()}"
                )
                total_combat_power += player.sum_stat
                total_dzens += player.dzen

            text.append(
                f"\n<b>Итого:</b> 🏵 <code>{total_dzens}</code> " f"🎓<code>{format_number(total_combat_power)}</code>"
            )
            self.message_manager.send_message(chat_id=chat_id, text="\n".join(text))

        def enemy_players_handler(self, chat_id: int, group: Group, players: List[Player]):
            total_combat_power = 0
            total_dzens = 0

            liders: List[str] = [lider.mention_html() for lider in group.liders]

            text: List[str] = [
                f"<b>👿 Список группы:</b> <code>{group.name}</code>",
                f'<b>Лидеры:</b> {";".join(liders)}\n',
            ]
            for index, player in enumerate(players, 1):
                text.append(
                    f"{index:02d}|🏵<code>{player.dzen:02d}</code>|"
                    f"🎓<code>{format_number_padded(player.sum_stat, 3, 5)}</code>"
                    f"|{player.mention_html()}"
                )
                total_combat_power += player.sum_stat
                total_dzens += player.dzen

            text.append(
                f"\n<b>Итого:</b> 🏵 <code>{total_dzens}</code> " f"🎓<code>{format_number(total_combat_power)}</code>"
            )
            self.message_manager.send_message(chat_id=chat_id, text="\n".join(text))

        @permissions(or_(is_admin, is_lider))
        def handler(self, update: InnerUpdate):
            """Возвращает список групп или список игроков группы, если указано"""
            if not update.command.argument:
                text = "<b>Список всех групп:</b>\n"
                text += self._group_ls_text(show_all_groups)
                return self.message_manager.send_message(chat_id=update.effective_chat_id, text=text)

            group = Group.get_by_name(update.command.argument)
            if group is None:
                return self.message_manager.send_message(
                    chat_id=update.effective_chat_id,
                    text=f"Я не знаю группы {update.command.argument}",
                )

            friendly_players: List[Player] = []
            enemy_players: List[Player] = []

            for player in group.members.order_by(Player.dzen.desc(), Player.sum_stat.desc()):  # type: Player
                if player.is_active:
                    friendly_players.append(player)
                else:
                    enemy_players.append(player)

            if not (friendly_players or enemy_players):
                return self.message_manager.send_message(
                    chat_id=update.effective_chat_id,
                    text=f'Группа "{group.name}" пуста',
                )

            if friendly_players:
                friendly_players_handler(self, update.effective_chat_id, group, friendly_players)

            if enemy_players:
                enemy_players_handler(self, update.effective_chat_id, group, enemy_players)

        return partial(handler, self)

    def _group_ls_text(self, show_all_groups: bool = False) -> str:
        query = Group.select()

        if not show_all_groups:
            query = query.where(Group.is_active == True)

        query = query.filter(Group.parent.is_null()).order_by(Group.type, Group.name)

        text: List[str] = []
        for idx, group in enumerate(query, 1):
            alias = f"({group.alias})" if group.alias else ""
            text.append(
                f'{idx}. {constants.group_type_icon.get(group.type, "")}'
                f'<b>{group.name}</b> {alias} [<code>{group.members.count()} ч</code>]'
            )

            if group.owners:
                text.append(self._group_owners_text(group))

        return "\n".join(text)

    def _group_owners_text(self, group: Group, tab: int = 1) -> str:
        text: List[str] = []
        tabs = "\t\t" * tab

        for idx, group in enumerate(group.owners.order_by(Group.type, Group.name), 1):
            alias = f"({group.alias})" if group.alias else ""
            text.append(
                f'{tabs}{idx}. {constants.group_type_icon.get(group.type, "")}'
                f'<b>{group.name}</b> {alias} [<code>{group.members.count()} ч</code>]'
            )

            if group.owners:
                text.append(self._group_owners_text(group, tab + 1))

        return "\n".join(text)

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Не указано имя группы.\nПришли сообщение в формате "/group_create Имя группы"')
    def group_create(self, update: InnerUpdate):
        """Создает новую группу игроков"""
        group_name = update.command.argument
        group = Group.get_by_name(group_name)
        chat_id = update.effective_chat_id
        if group:
            return self.message_manager.send_message(chat_id=chat_id, text="Такая группа уже существует")

        Group(name=group_name).save()
        self.message_manager.send_message(chat_id=chat_id, text=f"Группа {group_name} создана")

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/group_add Алиас @user1 @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def group_add(self, update: InnerUpdate, players: List[Player]):
        """
        Добавляет игроков в  указанную группу.
        Сообщение в формате 'Алиас группы @user1 @user2'.
        Работает так же на реплай на сообщение.
        """
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        chat_id = update.effective_chat_id
        if group is None:
            return self.message_manager.send_message(chat_id=chat_id, text=f"Я не знаю группы {group_name}")

        errors: List[str] = []
        for player in players:
            if group.type in {"goat", "gang"}:
                errors.append(player.mention_html())
                continue
            player.add_to_group(group)

        if errors:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'Игроки: {", ".join(errors)} не могут быть перемещенны в другую банду/козёл {group_name}',
            )
        self.message_manager.send_message(chat_id=chat_id, text=f"Игроки добавлены в группу {group_name}")

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/group_clear Алиас"')
    def group_clear(self, update: InnerUpdate):
        """
        Удаляет игроков из указанной группы.
        Сообщение в формате 'Алиас группы'.
        Работает так же на реплай на сообщение.
        """
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        chat_id = update.effective_chat_id
        if group is None:
            return self.message_manager.send_message(chat_id=chat_id, text=f"Я не знаю группы {group_name}")

        group.members.clear()

        self.message_manager.send_message(chat_id=chat_id, text=f"Игроки удалены из группы {group_name}")

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/group_kick Алиас @user1 @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def group_kick(self, update: InnerUpdate, players: List[Player]):
        """
        Удаляет игроков из указанной группы.
        Сообщение в формате 'Алиас группы @user1 @user2'.
        Работает так же на реплай на сообщение.
        """
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        chat_id = update.effective_chat_id
        if group is None:
            return self.message_manager.send_message(chat_id=chat_id, text=f"Я не знаю группы {group_name}")

        for player in players:
            group.members.remove(player)
        group.save()

        self.message_manager.send_message(chat_id=chat_id, text=f"Игроки удалены из группы {group_name}")

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r"(?P<group_name>.+)\s+-\s+(?P<alias>.+)"),
        argument_miss_msg='Пришли сообщение в формате "/group_alias Имя группы - алиас"',
    )
    def group_alias(self, update: InnerUpdate, match: Match):
        """Указать алиас группы, принимается сообщение в виде 'Имя группы - алиас'"""
        group_name = match.group("group_name")
        alias = match.group("alias")
        group = Group.get_by_name(group_name)
        chat_id = update.effective_chat_id
        if group is None:
            return self.message_manager.send_message(chat_id=chat_id, text=f'Я не знаю группу "{group_name}"')

        group.alias = alias
        group.save()
        self.message_manager.send_message(
            chat_id=chat_id,
            text=f'Теперь у группы "{group.name}" есть алиас "{group.alias}"',
        )

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r"(?P<alias>.+)\s+-\s+(?P<group_name>.+)"),
        argument_miss_msg='Пришли сообщение в формате "/group_rename Алиас группы - Новое имя группы"',
    )
    def group_rename(self, update: InnerUpdate, match: Match):
        """Переименовать группу, принимается сообщение в виде 'Алиас - Новое имя группы'"""
        group_name = match.group("group_name")
        alias = match.group("alias")
        chat_id = update.effective_chat_id
        if Group.get_by_name(group_name):
            return self.message_manager.send_message(chat_id=chat_id, text=f'Группа "{group_name}" уже существует')

        group = Group.get_by_name(alias)
        if group is None:
            return self.message_manager.send_message(chat_id=chat_id, text=f'Я не знаю группу "{alias}"')

        old_name = group.name
        group.name = group_name
        group.save()
        self.message_manager.send_message(chat_id=chat_id, text=f'Группа "{old_name}" переименована в "{group.name}"')

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r"(?P<alias>.+)"),
        argument_miss_msg='Пришли сообщение в формате "/visible Алиас группы"',
    )
    def visible(self, update: InnerUpdate, match: Match):
        group_alias = match.group("alias")
        group = Group.get_by_name(group_alias)
        if group is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'Группа "{group_alias}" не существует.',
            )

        group.type = None if group.type else "squad"
        group.save()
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Группа "{group_alias}" {"видима" if group.type == "squad" else "не видима"}.',
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/lider_set Алиас группы @user"')
    @get_players(include_reply=True, break_if_no_players=True)
    def lider_set(self, update: InnerUpdate, players: List[Player]):
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        if group is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'Группа "{group_name}" не существует.',
            )

        liders: List[str] = []
        for player in players:
            player.add_to_lider(group)
            liders.append(player.mention_html())

        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Игроки: {",".join(liders)} назначены лидерами группы "{group_name}"',
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/lider_kick Алиас группы @user"')
    @get_players(include_reply=True, break_if_no_players=True)
    def lider_kick(self, update: InnerUpdate, players: List[Player]):
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        if group is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'Группа "{group_name}" не существует.',
            )

        liders: List[str] = []
        for player in players:
            group.liders.remove(player)
            liders.append(player.mention_html())

        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=f'Игроки: {",".join(liders)} удалены из лидеров группы "{group_name}"',
        )

    def __handle_group(
        self,
        leader_nickname: Optional[str],
        group_name: Optional[str],
        group_type: Optional[str],
        date: datetime.datetime,
    ) -> Optional[Group]:
        if group_name is None:
            return

        group, created = Group.get_or_create(name=group_name)
        if not created and date <= group.last_update:
            return

        group.type = group_type
        group.save()

        if leader_nickname:
            player = Player.get_by_nickname(leader_nickname)
            if player:
                player.add_to_lider(group)

        return group
