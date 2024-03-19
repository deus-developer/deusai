from functools import wraps

import telegram

from src.core import Command, InnerUpdate


def command_parser(func):
    """Parse command message"""

    @wraps(func)
    def decorator(self, bot: telegram.Bot, update: telegram.Update, *args, **kwargs):
        command = Command.from_message(update.message)
        if not command.is_valid():
            return

        if command.bot_name and command.bot_name.lower() != bot.username.lower():
            return

        inner_update = InnerUpdate(update, command=command)
        return func(self, inner_update, *args, **kwargs)

    return decorator


def command_handler(argument_miss_msg=None, regexp=None):
    """Parse command argument"""

    def wrapper(func):
        @wraps(func)
        def decorator(self, update: InnerUpdate, *args, **kwargs):
            command = update.command
            if command is None:
                return

            m = command.match(regexp) if regexp else None
            if argument_miss_msg and ((not command.argument and not regexp) or (regexp and m is None)):
                return self.message_manager.send_message(chat_id=update.effective_chat_id, text=argument_miss_msg)

            if m:
                return func(self, update, match=m, *args, **kwargs)
            return func(self, update, *args, **kwargs)

        return decorator

    return wrapper
