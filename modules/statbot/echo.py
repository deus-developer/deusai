import html
import re
from typing import Match, List, Tuple, Set, Optional, Dict

from telegram.ext import Dispatcher

from config import settings
from core import CallbackResults
from core import EventManager, MessageManager, InnerHandler, CommandFilter, InnerUpdate
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import re_id, re_username
from models import TelegramChat, Group, Player, TelegramUser, GroupPlayerThrough
from modules import BasicModule
from utils.functions import CustomInnerFilters, telegram_user_id_encode


class EchoModule(BasicModule):
    """
    message sending
    """
    module_name = 'echo'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('echo'),
                self._echo,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('pin'),
                self._pin,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def _error_send_callback(self, callback_results: CallbackResults):
        error = callback_results.error
        if not error:
            return

        blocked_list, chat_id = callback_results.args
        blocked_list.append(chat_id)

    def _get_text_from_template(self, template: str, chat_id: int) -> str:
        chat_id_secret = telegram_user_id_encode(chat_id)
        return template.replace('{secret}', chat_id_secret)

    def _get_recipients_chat_ids_from_group(self, group: Group) -> List[Tuple[str, int]]:
        query = (
            Player.select(
                Player.nickname,
                Player.telegram_user_id.alias('user_id')
            )
            .join(GroupPlayerThrough, on=(GroupPlayerThrough.player_id == Player.id))
            .where(GroupPlayerThrough.group == group)
            .dicts()
        )

        result: List[Tuple[str, int]] = []
        for row in query:
            nickname = row['nickname']
            telegram_user_id = row['user_id']
            result.append((nickname, telegram_user_id))

        return result

    def _get_recipients_chat_ids_from_users(
        self,
        user_id_mentions: Set[int],
        username_mentions: Set[str]
    ) -> List[Tuple[str, int]]:
        query = (
            TelegramUser.select(
                Player.nickname,
                TelegramUser.user_id
            )
            .join(Player, on=(Player.telegram_user_id == TelegramUser.user_id))
            .where(
                (TelegramUser.user_id << user_id_mentions) |
                (TelegramUser.username << username_mentions)
            )
            .dicts()
        )

        result: List[Tuple[str, int]] = []
        for row in query:
            nickname = row['nickname']
            telegram_user_id = row['user_id']
            result.append((nickname, telegram_user_id))

        return result

    def _get_recipients_chat_ids_from_chat(self, chat: TelegramChat) -> List[Tuple[str, int]]:
        return [
            (chat.title, chat.chat_id)
        ]

    def _get_recipients_chat_ids(
        self,
        recipients: str,
        reply_to_message_user_id: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        group = Group.get_by_name(recipients)

        if group:  # Если группа
            return self._get_recipients_chat_ids_from_group(group)

        user_id_mentions: Set[int] = set()
        username_mentions: Set[str] = set()

        for username in re_username.findall(recipients):
            username_mentions.add(username)

        for user_id in map(int, re_id.findall(recipients)):
            user_id_mentions.add(user_id)

        if reply_to_message_user_id:
            user_id_mentions.add(reply_to_message_user_id)

        if user_id_mentions or username_mentions:
            return self._get_recipients_chat_ids_from_users(user_id_mentions, username_mentions)

        chat = TelegramChat.get_by_name(recipients)
        if chat:
            return self._get_recipients_chat_ids_from_chat(chat)

        return []

    def _get_recipient_mention(self, name: str, chat_id: int) -> str:
        if chat_id >= 0:
            return f'<a href="tg://user?id={chat_id}">{html.escape(name)}</a>'
        return html.escape(name)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r'(?P<recipients>.+)'),
        argument_miss_msg='Пришли сообщение в формате "/echo Получатели\n Текст сообщения"'
    )
    def _echo(self, update: InnerUpdate, match: Match):
        message = update.telegram_update.message

        message_lines: List[str] = message.text_html.split('\n')
        message_lines.pop(0)
        message_text_template = '\n'.join(message_lines)

        if not message_text_template:
            return update.telegram_update.message.reply_text('Текст сообщения отсутствует!')

        if message.reply_to_message and message.reply_to_message.from_user:
            reply_to_message_user_id = message.reply_to_message.from_user.id
        else:
            reply_to_message_user_id = None

        recipients_list = self._get_recipients_chat_ids(match.group('recipients'), reply_to_message_user_id)

        name_by_chat_id: Dict[int, str] = {}
        blocked_list: List[int] = []

        for name, chat_id in recipients_list:
            name_by_chat_id[chat_id] = name

            text = self._get_text_from_template(message_text_template, chat_id)
            self.message_manager.send_message(
                chat_id=chat_id,
                text=text,
                callback=self._error_send_callback,
                callback_args=(blocked_list, chat_id)
            )

        blocked_mentions: List[str] = []
        for chat_id in blocked_list:
            name = name_by_chat_id[chat_id]
            mention = self._get_recipient_mention(name, chat_id)
            blocked_mentions.append(mention)

        success_mentions: List[str] = []
        for name, chat_id in recipients_list:
            if chat_id in blocked_list:
                continue

            mention = self._get_recipient_mention(name, chat_id)
            success_mentions.append(mention)

        if blocked_mentions:
            blocked_mentions_text = '\n'.join(blocked_mentions)
            self.message_manager.send_message_splitted(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                text=f'❌ Не смог доставить сообщение в эти чаты ❌\n\n{blocked_mentions_text}',
                n=30
            )

        if success_mentions:
            success_mentions_text = '\n'.join(success_mentions)
            self.message_manager.send_message_splitted(
                chat_id=message.chat_id,
                text=f'✅ Сообщение отправлено в эти чаты ✅\n\n{success_mentions_text}',
                n=30
            )
        else:
            self.message_manager.send_message(
                chat_id=message.chat_id,
                text='⚠ Кажется я никуда не смог доставить сообщение ⚠'
            )

    @permissions(is_admin)
    @command_handler()
    def _pin(self, update: InnerUpdate):
        message = update.telegram_update.message
        rid = message.reply_to_message.message_id if message.reply_to_message else None
        if not rid:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text='⚠Отправьте команду /pin в ответ на сообщение⚠'
            )

        try:
            self.message_manager.bot.pin_chat_message(
                chat_id=message.chat_id,
                message_id=rid
            )
        except (Exception,):
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text="❌Я не смог запинить❌"
            )

        try:
            self.message_manager.bot.delete_message(
                chat_id=message.chat_id,
                message_id=message.message_id
            )
        except (Exception,):
            pass
