import functools
import telegram
from core import (
    Command,
    Update
)


def command_parser(func):
    """Parse command message"""

    @functools.wraps(func)
    def decorator(self, bot: telegram.Bot, update: telegram.Update, *args, **kwargs):
        command = Command(update.message)
        if not command.is_valid():
            return
        if command.bot_name and f'@{command.bot_name.lower()}' != bot.name.lower():
            return
        inner_update = Update(update, command=command)
        return func(self, update=inner_update, *args, **kwargs)

    return decorator


def command_handler(argument_miss_msg=None, regexp=None):
    """Parse command argument"""

    def wrapper(func):
        @functools.wraps(func)
        def decorator(self, update: Update, *args, **kwargs):
            command = update.command
            if command is None:
                return
            m = command.match(regexp) if regexp else None
            if argument_miss_msg and ((not command.argument and not regexp) or (regexp and m is None)):
                return self.message_manager.send_message(
                    chat_id=update.telegram_update.message.chat_id,
                    text=argument_miss_msg
                )
            if m:
                return func(self, update=update, match=m, *args, **kwargs)
            return func(self, update=update, *args, **kwargs)

        return decorator

    return wrapper
