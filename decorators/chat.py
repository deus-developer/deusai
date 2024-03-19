import functools

from core import InnerUpdate as InnerUpdate
from models import TelegramChat


def get_chat(func):
    @functools.wraps(func)
    def wrapper(self, update: InnerUpdate, *args, **kwargs):
        if update.telegram_update.message and update.chat is None:
            update.chat = TelegramChat.get_or_none(
                TelegramChat.chat_id == update.effective_chat_id
            )

        return func(self, update, *args, **kwargs)

    return wrapper
