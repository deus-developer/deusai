import re

from telegram import (
    ChatAction,
    ParseMode
)
from telegram.ext import Dispatcher

from config import settings
from core import CallbackResults
from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import (
    command_handler,
    permissions,
    send_action
)
from decorators.permissions import is_admin
from decorators.users import (
    re_id,
    re_username
)
from models import (
    Group,
    GroupPlayerThrough,
    Player,
    Settings,
    TelegramChat,
    TelegramUser
)
from modules import BasicModule
from utils.functions import (
    CustomInnerFilters,
    get_link,
    user_id_encode
)


class EchoModule(BasicModule):
    """
    message sending
    """
    module_name = 'echo'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('echo'), self._echo,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('echo_n'), self._echo_new,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('pin'), self._pin,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def _error_send(self, cr: CallbackResults):  # TODO: Добавить отлов всех ошибок
        e = cr.error
        if not e:
            return
        block_list, obj = cr.args
        if "bot was blocked by the user" in e.message:
            block_list.append(get_link(obj))

    def _error_send_new(self, cr: CallbackResults):
        e = cr.error
        if not e:
            return
        block_list, obj = cr.args
        if "bot was blocked by the user" in e.message:
            block_list.append(obj)

    @permissions(is_admin)
    @send_action(ChatAction.TYPING)
    @command_handler(
        regexp=re.compile(r'(?P<group_name>.+)\s+\$\s+(?P<title>.+)\s*'),
        argument_miss_msg='Пришли сообщение в формате "/echo Группа или игроки $ заголовок сообщения\n Текст сообщения"'
    )
    def _echo(self, update: Update, match, *args, **kwargs):
        return update.telegram_update.message.reply_text('Ты используешь устаревшую версию /echo; Новая версия: /echo_n')

    @permissions(is_admin)
    @send_action(ChatAction.TYPING)
    @command_handler(
        regexp=re.compile(r'(?P<recipients>.+)'),
        argument_miss_msg='Пришли сообщение в формате "/echo Получатели\n Текст сообщения"'
    )
    def _echo_new(self, update: Update, match, *args, **kwargs):  # TODO: Убрать пометку сообщений, сделать её в самом методе ".message_manager.send_message"
        message = update.telegram_update.message
        recipients = match.group('recipients')
        group = Group.get_by_name(recipients)
        unknown = []
        users = []
        lines = message.text.split('\n')
        lines.pop(0)
        if not lines:
            return update.telegram_update.message.reply_text('Текст сообщения отсутствует!')
        lines = '\n'.join(lines)
        lines = lines[0] + '{}' + lines[1: -1] + '{}' + lines[-1] if len(lines) > 2 else lines
        if group:  # Если группа
            users = Player.select(Player.nickname, TelegramUser.chat_id, Settings.pings['sendpin'].alias('not_muted')) \
                .join(GroupPlayerThrough, on=(GroupPlayerThrough.player_id == Player.id)) \
                .join(TelegramUser, on=(TelegramUser.user_id == Player.telegram_user_id)) \
                .join(Settings, on=(Player.settings_id == Settings.id)) \
                .where(GroupPlayerThrough.group == group).dicts()
        else:  # Если чат или юзеры
            rid = message.reply_to_message.from_user.id if message.reply_to_message else None
            ids = re_id.findall(recipients)
            usernames = re_username.findall(recipients)
            if rid:
                ids.append(rid)
            if not (ids or usernames):
                # То эт чат.
                chat = TelegramChat.get_by_name(recipients)
                if not chat:
                    return self.message_manager.send_message(
                        chat_id=message.chat_id,
                        text=f'Не могу найти "{recipients}"'
                    )
                text = message.text
                text = text.split('\n')
                text.pop(0)
                text = '\n'.join(text)
                self.message_manager.send_message(
                    chat_id=chat.chat_id,
                    text=text, parse_mode='HTML'
                )
                return self.message_manager.send_message(chat_id=message.chat_id, text=f'Отправил сообщение в чат "{chat.title}"')
            users = TelegramUser.select(Player.nickname, TelegramUser.chat_id, Settings.pings['echo'].alias('not_muted')) \
                .join(Player, on=(Player.telegram_user_id == TelegramUser.user_id)) \
                .join(Settings, on=(Player.settings_id == Settings.id)) \
                .where((TelegramUser.user_id << ids) | (TelegramUser.username << usernames)).dicts()
        users_arr = []  # (Nickname, chat_id)
        block_list = []  # (Nickname, chat_id)
        mute_list = []
        text = lines
        for user in users:
            nickname, chat_id, muted = user.values()

            muted = ['true', 'false'].index(muted) == 1

            secret_code = user_id_encode(chat_id)
            obj = (nickname, chat_id)

            if muted:
                mute_list.append(obj)
                continue
            self.message_manager.send_message(
                chat_id=chat_id,
                text=text.format(secret_code, secret_code),
                parse_mode=ParseMode.HTML,
                callback=self._error_send_new,
                callback_args=(block_list, obj)
            )
            if obj not in block_list:
                users_arr.append(obj)

        if block_list:
            block_list = '\n'.join([f'<a href="tg://user?id={obj[1]}">{obj[0]}</a>' for obj in block_list])
            self.message_manager.send_split(
                chat_id=settings.GOAT_ADMIN_CHAT_ID,
                msg=f'❌Меня заблокировали эти игроки❌:\n{block_list}',
                n=30
            )
        if mute_list:
            mute_list = '\n'.join([f'<a href="tg://user?id={obj[1]}">{obj[0]}</a>' for obj in mute_list])
            self.message_manager.send_split(
                chat_id=message.chat_id,
                msg=f'⚠Рассылку отключили эти игроки❌:\n{mute_list}',
                n=30
            )
        if users_arr:
            users_arr = [f'<a href="tg://user?id={obj[1]}">{obj[0]}</a>' for obj in users_arr]
            self.message_manager.send_split(
                chat_id=message.chat_id,
                msg=f'✅Сообщение отправлено игрокам ({len(users_arr)}): \n{", ".join(users_arr)}',
                n=30
            )
        else:
            self.message_manager.send_message(
                chat_id=message.chat_id,
                text='⚠Кажется я никому не смог доставить сообщение.⚠'
            )

    @permissions(is_admin)
    @command_handler()
    def _pin(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        rid = message.reply_to_message.message_id if message.reply_to_message else None
        if not rid:
            self.message_manager.send_message(
                chat_id=message.chat_id,
                text='⚠Отправьте команду /pin в ответ на сообщение⚠'
            )
            return

        try:
            self.message_manager.bot.pin_chat_message(chat_id=message.chat_id, message_id=rid, disable_notification=False)
        except (Exception, ):
            self.message_manager.send_message(chat_id=message.chat_id, text="❌Я не смог запинить❌")
            return

        try:
            self.message_manager.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
        except (Exception, ):
            pass
