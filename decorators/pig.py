from functools import wraps

from core import InnerUpdate
from .users import get_invoker
from .chat import get_chat
from models import Pig


def get_pig(func):
    @wraps(func)
    @get_invoker
    @get_chat
    def wrapper(self, update: InnerUpdate, *args, **kwargs):
        if (
            update.invoker and
            update.chat and
            update.pig is None
        ):
            update.pig = Pig.get_or_none(
                Pig.telegram_user == update.invoker,
                Pig.telegram_chat == update.chat
            )
        return func(self, update, *args, **kwargs)
    return wrapper
