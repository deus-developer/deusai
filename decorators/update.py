import functools
import telegram
from core import Update


def inner_update(UpdateType=Update):
    def wraper(func):
        """Creates inner update"""

        @functools.wraps(func)
        def decorator(self, bot: telegram.Bot, update: telegram.Update, *args, **kwargs):
            in_update = UpdateType(update)
            return func(self, update=in_update, *args, **kwargs)

        return decorator

    return wraper
