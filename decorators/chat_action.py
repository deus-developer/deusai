import functools


def send_action(action):
    """Sends `action` while processing func command."""

    def decorator(func):
        @functools.wraps(func)
        def command_func(self, update, *args, **kwargs):
            self.message_manager.bot.send_chat_action(
                chat_id=update.telegram_update.effective_message.chat_id,
                action=action
            )
            return func(self, update, *args, **kwargs)

        return command_func

    return decorator
