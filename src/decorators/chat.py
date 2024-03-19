from functools import wraps

from src.core import InnerUpdate as InnerUpdate
from src.models import TelegramChat


def get_chat(func):
    @wraps(func)
    def wrapper(self, update: InnerUpdate, *args, **kwargs):
        if update.effective_chat_id and update.chat is None:
            update.chat = TelegramChat.get_or_none(TelegramChat.chat_id == update.effective_chat_id)

        return func(self, update, *args, **kwargs)

    return wrapper
