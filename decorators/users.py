import functools
import re

from core import Update as InnerUpdate
from models import (
    TelegramUser,
    database
)

re_id = re.compile(r'#(?P<user_id>\d+)', re.MULTILINE)
re_username = re.compile(r'@(?P<username>\w+)', re.MULTILINE)


def get_users_from_text(text, reply_id=None):
    ids = re_id.findall(text)
    usernames = re_username.findall(text)
    if reply_id:
        ids.append(reply_id)
    users_arr = []
    unknown = []

    ids_c, usernames_c = ids.copy(), usernames.copy()
    with database.atomic():

        for user in TelegramUser.select().where((TelegramUser.user_id << ids) | (TelegramUser.username << usernames)):
            if user.user_id in ids:
                ids.remove(user.user_id)
            elif user.username in usernames:
                usernames.remove(user.username)
            users_arr.append(user)
        unknown = [f'#{x}' for x in ids] + [f'@{x}' for x in usernames]
    return ids_c, usernames_c, users_arr, unknown


def get_users(include_reply: bool = True, break_if_no_users: bool = True, callback_message: bool = True):
    """
    Parse users from input by ids, usernames, etc. from commands
    """

    def wrapper(func):
        @functools.wraps(func)
        def decorator(self, update: InnerUpdate, *args, **kwargs):
            message = update.telegram_update.message
            message_text = update.command.argument
            chat_id = message.chat_id
            rid = message.reply_to_message.from_user.id if (include_reply and message.reply_to_message) else None
            ids, usernames, users_arr, unknown = get_users_from_text(message_text, rid)

            if len(ids) == 0 and len(usernames) == 0:
                if break_if_no_users:
                    self.message_manager.send_message(
                        chat_id=chat_id,
                        text='Не вижу ни одного упоминания пользователя в формате <code>#user_id</code> '
                             'или <code>@username</code>',
                        parse_mode='HTML'
                    )
                    return
                else:
                    return func(self, update=update, users=[], *args, **kwargs)

            if callback_message and len(unknown) > 0:
                ends = 'и', 'ы' if len(unknown) > 1 else '', ''
                lost = ', '.join(unknown)
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'Игрок{ends[0]} {lost} не найден{ends[1]}',
                )
            if break_if_no_users and len(users_arr) == 0:
                return

            return func(self, update=update, users=users_arr, *args, **kwargs)

        return decorator

    return wrapper


def get_players(include_reply: bool = True, break_if_no_players: bool = True, callback_message: bool = True):
    """
    Parse players from input by ids, usernames, etc. from commands
    """

    def wrapper(func):
        @functools.wraps(func)
        @get_users(include_reply, break_if_no_players, callback_message)
        def decorator(self, update: InnerUpdate, users: list, *args, **kwargs):
            chat_id = update.telegram_update.message.chat_id
            players_arr = []
            unknown = []
            with database.atomic():
                for user in users:
                    if user.player.exists():
                        players_arr.append(user.player.get())
                    else:
                        unknown.append(f'@{user.username}')

            if callback_message and len(unknown) > 0:
                end = 'и' if len(unknown) > 1 else ''
                lost = ', '.join(unknown)
                self.message_manager.send_message(
                    chat_id=chat_id,
                    text=f'Игрок{end} {lost} ещё не прислал{end} пипк{end}',
                )
            if break_if_no_players and len(players_arr) == 0:
                return
            return func(self, update=update, players=players_arr, *args, **kwargs)

        return decorator

    return wrapper


def get_invoker(func):
    @functools.wraps(func)
    def wrapper(self, update: InnerUpdate, *args, **kwargs):
        user = update.telegram_update.effective_user
        user = TelegramUser.get_by_id(user.id)
        update.invoker = user
        return func(self, update, *args, **kwargs)

    return wrapper


def get_player(func):
    @functools.wraps(func)
    @get_invoker
    def wrapper(self, update: InnerUpdate, *args, **kwargs):
        update.player = update.invoker.player.get() if update.invoker.player else None
        return func(self, update=update, *args, **kwargs)

    return wrapper
