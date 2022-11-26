import functools

from core import Update
import logging
from config import settings
from models import (
    Rank,
    Group
)


def or_(*args):
    def calc(update: Update, **kwargs):
        return any(map(lambda x: x(update, **kwargs), args))

    return calc


def and_(*args):
    def calc(update: Update, **kwargs):
        return all(map(lambda x: x(update, **kwargs), args))

    return calc


def is_admin(update: Update, **kwargs):
    return update.invoker.is_admin


def is_rank(rank_name='Полковник'):
    def handler(update: Update = None, **kwargs):
        if not (update or kwargs.get('player', None)):
            return False

        rank = Rank.get_or_none(name=rank_name)
        if not rank:
            return False
        player = kwargs.get('player', None) or update.player

        if player.rank.priority < rank.priority:
            return False

        return True

    return functools.partial(handler)


def is_lider(update: Update, **kwargs):
    grs = update.command.argument.split()
    if not grs:
        return False

    gr = Group.get_by_name(grs[0])
    return gr and gr in update.player.liders


def is_developer(update: Update, **kwargs):
    return update.invoker.chat_id == settings.ADMIN_CHAT_ID


def self_(update: Update, **kwargs):
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
        def decorator(self, update: Update, *args, **kwargs):
            invoker = update.invoker
            player = update.player
            if not player:
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text='Я тебя не знаю, пришли свой полный пип-бой, '
                         'чтобы познакомиться'
                )
            if not permit_expression(update, **kwargs):
                logger.info(f'Permission denied (@{invoker.username})')
                if update.telegram_update.message.chat_id != invoker.chat_id:
                    return
                return self.message_manager.send_message(
                    chat_id=invoker.chat_id,
                    text='Доступ запрещен'
                )
            logger.info(f'Permission granted (@{invoker.username})')
            return func(self, update=update, *args, **kwargs)

        return decorator

    return wrapper
