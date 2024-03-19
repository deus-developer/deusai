import functools
import logging

from config import settings
from core import InnerUpdate
from models import Group


def or_(*filters):
    def calc(update: InnerUpdate, *args, **kwargs):
        return any(
            func(update, *args, **kwargs)
            for func in filters
        )

    return calc


def and_(*filters):
    def calc(update: InnerUpdate, *args, **kwargs):
        return all(
            func(update, *args, **kwargs)
            for func in filters
        )

    return calc


def is_admin(update: InnerUpdate, *args, **kwargs):
    return update.invoker.is_admin


def is_lider(update: InnerUpdate, *args, **kwargs):
    grs = update.command.argument.split()
    if not grs:
        return False

    gr = Group.get_by_name(grs[0])
    return gr and gr in update.player.liders


def is_developer(update: InnerUpdate, *args, **kwargs):
    return update.invoker.chat_id == settings.ADMIN_CHAT_ID


def self_(update: InnerUpdate, *args, **kwargs):
    players = kwargs.get('players', [])
    users = kwargs.get('users', [])
    if not players and not users:
        return True

    if len(players) == 1 and players[0] == update.player:
        return True

    if len(users) == 1 and users[0] == update.invoker:
        return True

    return False


def permissions(permit_expression):
    def wrapper(func):
        logger = logging.getLogger(func.__module__)

        @functools.wraps(func)
        def decorator(self, update: InnerUpdate, *args, **kwargs):
            invoker = update.invoker
            player = update.player
            if not player:
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text='Я тебя не знаю, пришли свой полный пип-бой, '
                         'чтобы познакомиться'
                )

            if not permit_expression(update, *args, **kwargs):
                logger.info(f'Permission denied (@{invoker.username})')
                if update.effective_chat_id != invoker.chat_id:
                    return
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text='Доступ запрещен'
                )

            logger.info(f'Permission granted (@{invoker.username})')
            return func(self, update, *args, **kwargs)

        return decorator

    return wrapper
