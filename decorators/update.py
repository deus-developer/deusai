import functools

import telegram

from core import InnerUpdate


def inner_update(update_type=InnerUpdate):
    def wraper(func):
        """Creates inner update"""

        @functools.wraps(func)
        def decorator(self, _: telegram.Bot, update: telegram.Update, *args, **kwargs):
            inner_update_object = update_type(update)
            return func(self, update=inner_update_object, *args, **kwargs)

        return decorator

    return wraper
