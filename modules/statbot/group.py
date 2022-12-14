import functools
import re

from telegram import ParseMode
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

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
    is_lider,
    or_
)
from decorators.users import get_players
from models import (
    Group,
    Player,
    Settings
)
from modules import BasicModule
from modules.statbot.parser import GroupParseResult
from utils.functions import CustomInnerFilters
from ww6StatBotWorld import Wasteland


class GroupModule(BasicModule):
    """
    Handle player groups
    """
    module_name = 'group'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        # called on goat forward after it has been parsed in the parser module
        self.add_inner_handler(InnerHandler(UpdateFilter('goat'), self.goat_handler))
        # called on gang forward after it had been parsed in the parser module
        self.add_inner_handler(InnerHandler(UpdateFilter('gang'), self.gang_handler))

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_alias'), self.group_alias,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_rename'), self.group_rename,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_create'), self.group_create,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_delete'), self.group_delete(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_delete_with_players'), self.group_delete(force=True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_add'), self.group_add,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_kick'), self.group_kick,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_ls'), self.group_ls_new(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('group_ls_all'), self.group_ls_new(True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('visible'), self.visible,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('lider_set'), self.lider_set,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('lider_kick'), self.lider_kick,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('ping'), self._convene,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/ping ?????????? ????????????"')
    def _convene(self, update: Update, *args, **kwargs):  # TODO: ????????????????????????
        group_name = update.command.argument
        group = Group.get_by_name(group_name)
        if not group:
            return
        if not update.chat:
            return self.message_manager.send_message(chat_id=update.telegram_update.message.chat_id, text='?????? ?????????????? ?????????? ?????????????? ???????????? ?? ????????????')

        players = group.members.join(Settings, on=(Player.settings_id == Settings.id)) \
            .where(Settings.pings['ping'] == 'true')

        reply = update.telegram_update.message.reply_to_message.message_id if update.telegram_update.message.reply_to_message else False
        ping = [f'?????? ?????????? {update.player.nickname} ???????????????? ??????:']
        for idx, pl in enumerate(players, 1):
            ping.append(f'{idx}. {mention_html(pl.telegram_user_id, pl.nickname)}')
            self.message_manager.send_message(
                chat_id=pl.telegram_user.chat_id,
                text=f'???????? ?????????? ?????????????????? ????????! ???????????????? ?????????????????? ?? ???????? "{update.chat.title}"'
            )

        self.message_manager.send_split(
            chat_id=update.telegram_update.message.chat_id,
            msg='\n'.join(ping), n=5, reply=reply
        )

        self.message_manager.bot.delete_message(chat_id=update.telegram_update.message.chat_id, message_id=update.telegram_update.message.message_id)

    def goat_handler(self, update: GroupParseResult):
        message = update.telegram_update.message
        goat, created = Group.get_or_create(name=update.goat.name, type='goat')
        if not created and update.date < goat.last_update:
            return

        if update.goat.commander:
            pl, created = Player.get_or_create(nickname=update.goat.commander)
            if pl not in goat.liders:
                goat.liders.add(pl)

        query = Group.update(
            {
                Group.parent: None
            }
        ).where(
            Group.parent == goat
        ).execute()

        query = Group.update(
            {
                Group.parent: goat
            }
        ).where((Group.name << update.goat.gangs) & (Group.type == 'gang')).execute()

        gangs = [
            {
                'name': gang,
                'type': 'gang',
                'parent': goat,
                'is_active': goat.is_active,
                'last_update': update.date

            } for gang in update.goat.gangs
        ]
        query = Group.insert(gangs).on_conflict(
            conflict_target=[Group.name, Group.type],
            update={
                Group.parent: goat
            }
        ).execute()
        goat.last_update = update.date
        goat.league = update.goat.league if update.goat.league else goat.league
        goat.save()
        self.message_manager.send_message(text='???????????? ??????????????????.', chat_id=message.chat_id)

    def group_delete(self, force=False):
        @permissions(or_(is_admin, is_lider))
        @command_handler(argument_miss_msg='?????????? ????????????, ?????????????? ???????????? ??????????????')
        def handler(self, update: Update, *args, **kwargs):
            group_name = update.command.argument
            chat_id = update.telegram_update.message.chat_id

            group = Group.get_by_name(group_name)
            if not group:
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text='?? ???? ???????? ?????????? ????????????'
                )
            elif group.members or group.liders:
                if not force:
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        text=f'?? ???????????? ???????? {len(group.members) or len(group.liders)} ????????????????????, '
                             f'?????? ???? ???????????????? ???????????? ???????????? ??????????????'
                    )
                else:
                    group.members.clear()
                    group.liders.clear()
                    group.delete_instance()
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        text=f'???????????? {group_name} ?? ???? ?????????????????? ??????????????'
                    )
            else:
                group.delete_instance()
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'???????????? {group_name} ??????????????'
                )

        handler.__doc__ = f'?????????????? ???????????? {"?? ???????? ???? ????????????????????" if force else ""}'
        return functools.partial(handler, self)

    def gang_handler(self, update: GroupParseResult):  # TODO: ???????????????????????????? ???????????? ?? ?????????? => ????????????????????????
        parse_result = update
        message = parse_result.telegram_update.message
        gang = self.__handle_group(parse_result.gang, 'gang', message.forward_date)
        if not gang:
            return
        goat = self.__handle_group(parse_result.gang.goat, 'goat', message.forward_date)
        if not goat:
            return
        missed = []
        gang.members.clear()

        for gangster in parse_result.gang.players:
            player = Player.get_or_none(nickname=gangster.nickname)
            if not player:
                missed.append(gangster.nickname)
            else:
                player.add_to_group(gang)
                player.add_to_group(goat)
        self.message_manager.send_message(text='???????????? ??????????????????', chat_id=message.chat_id)
        if missed:
            self.message_manager.send_message(
                text=f'???????????? {", ".join(missed)} ???? ???????????????? ???????? ??????????',
                chat_id=message.chat_id
            )

    def group_ls(self, all_=False):
        @permissions(or_(is_admin, is_lider))
        def handler(self, update: Update, *args, **kwargs):
            """???????????????????? ???????????? ?????????? ?????? ???????????? ?????????????? ????????????, ???????? ??????????????"""
            if not update.command.argument:
                res = ['???????????? ???????? ??????????: \n']
                query = Group.select() if all_ else Group.select().where(Group.is_active == True)
                for index, group in enumerate(query.order_by(Group.name), 1):
                    alias = f'({group.alias})' if group.alias else ''
                    res.append(f'{index}. {Wasteland.group_type_icon.get(group.type, "")}{group.name}{alias} [{len(group.members)}??]')
                return self.message_manager.send_message(
                    chat_id=update.telegram_update.message.chat_id,
                    text='\n'.join(res)
                )
            else:
                group = Group.get_by_name(update.command.argument)
                if not group:
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text=f'?? ???? ???????? ???????????? {update.command.argument}'
                    )
                    return

                players_a = group.members \
                    .filter(Player.is_active == True) \
                    .order_by(Player.sum_stat.desc())
                players_b = group.members \
                    .filter(Player.is_active == False) \
                    .order_by(Player.sum_stat.desc())
                if players_a:
                    sum_stats = 0
                    liders = [mention_html(lider.telegram_user_id, lider.nickname) for lider in group.liders]
                    res = [f'???????????? ???????????? {group.name}\n', f'????????????: {";".join(liders)}\n']
                    for index, player in enumerate(players_a, 1):
                        res.append(f'{index}. {mention_html(player.telegram_user_id, player.nickname)} [????: {player.sum_stat}]')
                        sum_stats += player.sum_stat
                    res.append(f'?????????????????? ???????????? ????????: <b>{sum_stats}</b>')
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text='\n'.join(res),
                        parse_mode=ParseMode.HTML
                    )
                if players_b:
                    sum_stats = 0
                    liders = [mention_html(lider.telegram_user_id, lider.nickname) for lider in group.liders]
                    res = [f'???????????????? ???????????? {group.name}\n', f'????????????: {";".join(liders)}\n']
                    for index, player in enumerate(players_b, 1):
                        res.append(f'{index}. {mention_html(player.telegram_user_id, player.nickname)} [????: {player.sum_stat}]')
                        sum_stats += player.sum_stat
                    res.append(f'?????????????????? ???????????? ????????: <b>{sum_stats}</b>')
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text='\n'.join(res),
                        parse_mode=ParseMode.HTML
                    )

        return functools.partial(handler, self)

    def group_ls_new(self, all_=False):
        @permissions(or_(is_admin, is_lider))
        def handler(self, update: Update, *args, **kwargs):
            """???????????????????? ???????????? ?????????? ?????? ???????????? ?????????????? ????????????, ???????? ??????????????"""
            if not update.command.argument:
                res = '???????????? ???????? ??????????: \n'
                res += self._group_ls_text(all_)
                return self.message_manager.send_message(
                    chat_id=update.telegram_update.message.chat_id,
                    text=res
                )
            else:
                group = Group.get_by_name(update.command.argument)
                if not group:
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text=f'?? ???? ???????? ???????????? {update.command.argument}'
                    )
                    return

                players_a = group.members \
                    .filter(Player.is_active == True) \
                    .order_by(Player.sum_stat.desc())
                players_b = group.members \
                    .filter(Player.is_active == False) \
                    .order_by(Player.sum_stat.desc())
                if players_a:
                    sum_stats = 0
                    liders = [mention_html(lider.telegram_user_id, lider.nickname) or lider.nickname for lider in group.liders]
                    res = [f'???????????? ???????????? {group.name}\n', f'????????????: {";".join(liders)}\n']
                    for index, player in enumerate(players_a, 1):
                        res.append(f'{index}. {mention_html(player.telegram_user_id, player.nickname) or player.nickname} [????: {player.sum_stat}]')
                        sum_stats += player.sum_stat
                    res.append(f'?????????????????? ???????????? ????????: <b>{sum_stats}</b>')
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text='\n'.join(res),
                        parse_mode=ParseMode.HTML
                    )
                if players_b:
                    sum_stats = 0
                    liders = [mention_html(lider.telegram_user_id, lider.nickname) or lider.nickname for lider in group.liders]
                    res = [f'???????????????? ???????????? {group.name}\n', f'????????????: {";".join(liders)}\n']
                    for index, player in enumerate(players_b, 1):
                        res.append(f'{index}. {mention_html(player.telegram_user_id, player.nickname) or player.nickname} [????: {player.sum_stat}]')
                        sum_stats += player.sum_stat
                    res.append(f'?????????????????? ???????????? ????????: <b>{sum_stats}</b>')
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text='\n'.join(res),
                        parse_mode=ParseMode.HTML
                    )
                if not (players_a or players_b):
                    self.message_manager.send_message(
                        chat_id=update.telegram_update.message.chat_id,
                        text=f'???????????? "{group.name}" ??????????',
                        parse_mode=ParseMode.HTML
                    )

        return functools.partial(handler, self)

    def _group_ls_text(self, is_all=False):
        query = Group.select() if is_all else Group.select().where(Group.is_active == True)
        query = query.filter(Group.parent.is_null()).order_by(Group.type, Group.name)
        output = []
        for idx, group in enumerate(query, 1):
            alias = f'({group.alias})' if group.alias else ''
            output.append(f'{idx}. {Wasteland.group_type_icon.get(group.type, "")}{group.name}{alias} [{group.members.count()} ??]')
            if group.owners:
                output.append(self._group_owners_text(group))
        return '\n'.join(output)

    def _group_owners_text(self, group: Group, tab=1):
        output = []
        tabs = '\t\t' * tab
        for idx, group in enumerate(group.owners.order_by(Group.type, Group.name), 1):
            alias = f'({group.alias})' if group.alias else ''
            output.append(f'{tabs}{idx}. {Wasteland.group_type_icon.get(group.type, "")}{group.name}{alias} [{group.members.count()} ??]')
            if group.owners:
                output.append(self._group_owners_text(group, tab + 1))
        return '\n'.join(output)

    @permissions(is_admin)
    @command_handler(argument_miss_msg='???? ?????????????? ?????? ????????????.\n???????????? ?????????????????? ?? ?????????????? "/group_create ?????? ????????????"')
    def group_create(self, update: Update, *args, **kwargs):  # TODO: ????????????????????????, ???????? ???????????????????? ???? ??????????
        """?????????????? ?????????? ???????????? ??????????????"""
        group_name = update.command.argument
        group = Group.get_by_name(group_name)
        chat_id = update.telegram_update.message.chat_id
        if group:
            self.message_manager.send_message(
                chat_id=chat_id,
                text='?????????? ???????????? ?????? ????????????????????'
            )
        else:
            Group(name=group_name).save()
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'???????????? {group_name} ??????????????'
            )

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/group_add ?????????? @user1 @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def group_add(self, update: Update, players, *args, **kwargs):
        """
        ?????????????????? ?????????????? ??  ?????????????????? ????????????.
        ?????????????????? ?? ?????????????? '?????????? ???????????? @user1 @user2'.
        ???????????????? ?????? ???? ???? ???????????? ???? ??????????????????.
        """
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        chat_id = update.telegram_update.message.chat_id
        if not group:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'?? ???? ???????? ???????????? {group_name}'
            )
        else:
            err = []
            for player in players:
                if group.type in ['goat', 'gang']:
                    err.append(mention_html(player.telegram_user_id, player.nickname))
                    continue
                player.add_to_group(group)  # TODO: ???????????????????????????? ?? ?????????????? ?????????????? ??????????????.
            if err:
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'????????????: {", ".join(err)} ???? ?????????? ???????? ?????????????????????? ?? ???????????? ??????????/?????????? {group_name}'
                )
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'???????????? ?????????????????? ?? ???????????? {group_name}'
            )

    @permissions(or_(is_admin, is_lider))
    @command_handler(argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/group_kick ?????????? @user1 @user2"')
    @get_players(include_reply=True, break_if_no_players=True)
    def group_kick(self, update: Update, players, *args, **kwargs):
        """
        ?????????????? ?????????????? ???? ?????????????????? ????????????.
        ?????????????????? ?? ?????????????? '?????????? ???????????? @user1 @user2'.
        ???????????????? ?????? ???? ???? ???????????? ???? ??????????????????.
        """
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        chat_id = update.telegram_update.message.chat_id
        if not group:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'?? ???? ???????? ???????????? {group_name}'
            )
        else:
            for player in players:
                group.members.remove(player)  # TODO: ???????????????????????????? ?? ?????????????? ?????????????? ????????????????.
            group.save()
            # TODO: ????????????????????????????, ?????????????? ?????????????? ????????, ?? ???? Sentry

            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'???????????? ?????????????? ???? ???????????? {group_name}'
            )

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r'(?P<group_name>.+)\s+-\s+(?P<alias>.+)'),
        argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/group_alias ?????? ???????????? - ??????????"'
    )
    def group_alias(self, update: Update, match, *args, **kwargs):
        """?????????????? ?????????? ????????????, ?????????????????????? ?????????????????? ?? ???????? '?????? ???????????? - ??????????'"""
        group_name = match.group('group_name')
        alias = match.group('alias')
        group = Group.get_by_name(group_name)
        chat_id = update.telegram_update.message.chat_id
        if not group:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'?? ???? ???????? ???????????? "{group_name}"'
            )
        else:
            group.alias = alias
            group.save()
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'???????????? ?? ???????????? "{group.name}" ???????? ?????????? "{group.alias}"'
            )

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r'(?P<alias>.+)\s+-\s+(?P<group_name>.+)'),
        argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/group_rename ?????????? ???????????? - ?????????? ?????? ????????????"'
    )
    def group_rename(self, update: Update, match, *args, **kwargs):
        """?????????????????????????? ????????????, ?????????????????????? ?????????????????? ?? ???????? '?????????? - ?????????? ?????? ????????????'"""
        group_name = match.group('group_name')
        alias = match.group('alias')
        chat_id = update.telegram_update.message.chat_id
        if Group.get_by_name(group_name):
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=f'???????????? "{group_name}" ?????? ????????????????????'
            )
        group = Group.get_by_name(alias)
        if not group:
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'?? ???? ???????? ???????????? "{alias}"'
            )
        else:
            old_name = group.name
            group.name = group_name
            group.save()
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'???????????? "{old_name}" ?????????????????????????? ?? "{group.name}"'
            )

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r'(?P<alias>.+)'),
        argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/visible ?????????? ????????????"'
    )
    def visible(self, update: Update, match, *args, **kwargs):
        group_alias = match.group('alias')
        group = Group.get_by_name(group_alias)
        if not group:
            return self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f'???????????? "{group_alias}" ???? ????????????????????.'
            )
        group.type = None if group.type else 'squad'
        group.save()
        return self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'???????????? "{group_alias}" {"????????????" if group.type == "squad" else "???? ????????????"}.'
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/lider_set ?????????? ???????????? @user"')
    @get_players(include_reply=True, break_if_no_players=True)
    def lider_set(self, update: Update, players, *args, **kwargs):
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        if not group:
            return self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f'???????????? "{group_name}" ???? ????????????????????.'
            )
        liders = []
        for player in players:
            player.add_to_lider(group)
            liders.append(mention_html(player.telegram_user_id, player.nickname))

        return self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'????????????: {",".join(liders)} ?????????????????? ???????????????? ???????????? "{group_name}"',
            parse_mode=ParseMode.HTML
        )

    @permissions(is_admin)
    @command_handler(argument_miss_msg='???????????? ?????????????????? ?? ?????????????? "/lider_kick ?????????? ???????????? @user"')
    @get_players(include_reply=True, break_if_no_players=True)
    def lider_kick(self, update: Update, players, *args, **kwargs):
        group_name = update.command.argument.split()[0]
        group = Group.get_by_name(group_name)
        if not group:
            return self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text=f'???????????? "{group_name}" ???? ????????????????????.'
            )
        liders = []
        for player in players:
            group.liders.remove(player)
            liders.append(mention_html(player.telegram_user_id, player.nickname))

        return self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'????????????: {",".join(liders)} ?????????????? ???? ?????????????? ???????????? "{group_name}"',
            parse_mode=ParseMode.HTML
        )

    def __handle_group(self, group, type_, date) -> Group | None:
        commander = group.commander
        group, created = Group.get_or_create(name=group.name)
        if not created and date < group.last_update:
            return

        group.type = type_
        group.save()
        if commander:
            pl = Player.get_by_nickname(commander)
            if pl:
                pl.add_to_lider(group)
        return group
