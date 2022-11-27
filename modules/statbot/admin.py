import functools
import re

from telegram import ParseMode
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
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
from decorators.permissions import (
    is_admin,
    is_developer
)
from decorators.users import get_players
from models import (
    Player,
    TelegramUser
)
from modules import BasicModule
from utils.functions import (
    CustomInnerFilters,
    user_id_decode
)


class AdminModule(BasicModule):
    """
    Admin commands
    """
    module_name = 'admin'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='ban', description='Забанить игрока'), self._ban(True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='unban', description='Разбанить игрока'), self._ban(False),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='ban_ls', description='Список забанненых'), self._ban_ls,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('rp_21'), self._remove_player,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('admin_add'), self._admin(True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('admin_remove'), self._admin(False),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('admin_ls'), self._admin_list,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command='crpt', description='Проверить сообщение на подпись'), self._crpt,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'[\s\S]*﻿(?P<secret_code>.+)﻿[\s\S]*'),
        argument_miss_msg='Пришли сообщение в формате "/crpt Текст"'
    )
    def _crpt(self, update: Update, match, *args, **kwargs):
        """
        Анализирует текст на предмет двоичного обозначения TelegramUser.user_id в двоичном виде
        Вызывать с любым текстом, где может быть такой "шифр"
        """
        code = match.group('secret_code')
        telegram_id = user_id_decode(code)
        tg_user = TelegramUser.get_by_user_id(telegram_id)
        if not tg_user:
            return self.message_manager.send_message(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                text='⚠Слушааай. Я не могу найти игрока с такой юзеркой.⚠'
            )
        self.message_manager.send_message(
            chat_id=settings.GOAT_ADMIN_CHAT_ID,
            text=f'✅Это соо {tg_user.get_link()},\n если он его слил то бань :)'
        )

    @permissions(is_developer)
    def _reverse_reduce(self, update: Update, *args, **kwargs):
        """
        Перерасчёт кармы на основе истории кармы, работает почему-то не коректно.
        После перерасчёта опросить людей на предмет "верности" нового значения
        """
        players = Player.select().where(Player.is_active == True)
        for player in players:
            self.logger.info(f'NICKNAME: {player.nickname}; KARMA: {player.karma}')
            recived = player.karma_recived
            final = 0
            for recive in recived:
                final += recive.amount
            player.add_stats(
                karma=final if final != 0 else 1,
                hp=player.hp,
                attack=player.attack,
                defence=player.defence,
                power=player.power,
                accuracy=player.accuracy,
                oratory=player.oratory,
                agility=player.agility,
                stamina=player.stamina,
                dzen=player.dzen,
                raids21=player.raids21, raid_points=player.raid_points, loose_raids=player.loose_raids, loose_weeks=player.loose_weeks,
                regeneration_l=player.regeneration_l, batcoh_l=player.batcoh_l
            )
            self.logger.info(f'FINAL: {final}')
            self.message_manager.send_message(chat_id=player.telegram_user.chat_id, text=f'Я проверил всю твою историю кармы и произвёл коррективы. Теперь у тебя {final} кармы.')

    @permissions(is_developer)
    @get_players(include_reply=True, break_if_no_players=False)
    def _remove_player(self, update: Update, players, *args, **kwargs):  # TODO: Придать функционал :)
        """
        Удаляет из базы игрока с ником из аргумента команды
        """
        chat_id = update.telegram_update.message.chat_id

        if not players:
            players = [Player.get_or_none(nickname=s.replace('|', ' ')) for s in update.command.argument.split(' ')]
        for player in players:  # group_type: Player
            if not player:
                continue
            player.members.clear()
            player.liders.clear()
            player.karma_recived.clear()
            player.karma_sended.clear()
            for stat in (player.history_stats if player.history_stats else []):
                stat.delete_instance()

            for raid in (player.raids_assign if player.raids_assign else []):
                raid.delete_instance()

            if player.settings:
                player.settings.delete_instance()
            if player.notebook:
                player.notebook.delete_instance()

            player.delete_instance()

        self.message_manager.send_message(
            chat_id=chat_id,
            text=f'*Юзеры убиты*',
            parse_mode=ParseMode.MARKDOWN
        )

    def _ban(self, is_banned):  # TODO: Дать доступ не только админам, но и лидерам его банды/альянса
        """
        Банит/Разбанивает игрока по юзерке
        """

        @permissions(is_admin)
        @get_players(include_reply=True, break_if_no_players=True)
        def handler(self, update: Update, players, *args, **kwargs):
            chat_id = update.telegram_update.message.chat_id
            state_text = f'{"за" if is_banned else "раз"}бан'
            for player in players:  # group_type: Player
                user = player.telegram_user
                if user == update.invoker:
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        text=f'⚠Ты не можешь {state_text}ить сам себя'
                    )
                    continue
                user.is_banned = is_banned
                user.save()

                status = player.delete_player() if is_banned else player.to_player()
                if not status:
                    update.telegram_update.message.reply_text(f'Действие над пользователем #{player.telegram_user_id} вызвало ошибку.')

                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'*@{user.username}* {state_text}ен',
                    parse_mode=ParseMode.MARKDOWN
                )

        handler.__doc__ = f'{is_banned and "За" or "Раз"}банить игрока'
        return functools.partial(handler, self)

    def _admin(self, become_admin):  # TODO: Оптимизировать смену статуса администратора
        """
        Даёт/Забирает полномочия администратора по юзеркам
        """

        @permissions(is_developer)
        @get_players(include_reply=True, break_if_no_players=True)
        def handler(self, update: Update, players, *args, **kwargs):
            chat_id = update.telegram_update.message.chat_id
            state_text = "" if become_admin else "не"
            for player in players:  # group_type: Player
                user = player.telegram_user
                user.is_admin = become_admin
                user.save()

                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'✅*@{user.username}* теперь {state_text} админ',
                    parse_mode=ParseMode.MARKDOWN
                )

        handler.__doc__ = f'{become_admin and "За" or "Раз"}админить игрока'
        return functools.partial(handler, self)

    @permissions(is_admin)
    def _admin_list(self, update: Update, *args, **kwargs):  # TODO: Оптимизировать формирование ссылок на профили
        """
        Показывает список администраторов
        """
        res = [f'<b>Список админов</b>:']
        for user in TelegramUser.filter(TelegramUser.is_admin == True):
            if not user.player:
                continue

            res.append(mention_html(user.user_id, user.player.get().nickname if user.player.exists() else f'{user.first_name} {user.last_name}'))
        chat_id = update.telegram_update.message.chat_id
        self.message_manager.send_message(
            chat_id=chat_id,
            text='\n'.join(res),
            parse_mode=ParseMode.HTML
        )

    @permissions(is_admin)
    def _ban_ls(self, update: Update, *args, **kwargs):  # TODO: Оптимизировать формирование ссылок на профили
        """
        Показывает список банов
        """
        res = [f'<b>Список банов</b>:']
        for user in TelegramUser.filter(TelegramUser.is_banned == True):
            if not user.player:
                continue
            res.append(mention_html(user.user_id, user.player.get().nickname if user.player.exists() else f'{user.first_name} {user.last_name}'))
        chat_id = update.telegram_update.message.chat_id
        self.message_manager.send_message(
            chat_id=chat_id,
            text='\n'.join(res),
            parse_mode=ParseMode.HTML
        )
