from functools import wraps

import telegram

from src.core import InnerUpdate


def inner_update(update_type=InnerUpdate):
    def wraper(func):
        """Creates inner update"""

        @wraps(func)
        def decorator(self, _: telegram.Bot, update: telegram.Update, *args, **kwargs):
            inner_update_object = update_type(update)
            return func(self, update=inner_update_object, *args, **kwargs)

        return decorator

    return wraper
