import functools
from core import Update as InnerUpdate
from models import TelegramChat


def get_chat(func):
    @functools.wraps(func)
    def wrapper(self, update: InnerUpdate, *args, **kwargs):
        if update.telegram_update.message:
            update.chat = TelegramChat.get_or_none(
                TelegramChat.chat_id == update.telegram_update.message.chat_id
            )

        return func(self, update, *args, **kwargs)

    return wrapper
