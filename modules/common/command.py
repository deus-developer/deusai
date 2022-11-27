from telegram.ext import (
    Dispatcher,
    Filters,
    MessageHandler
)

from core import (
    EventManager,
    MessageManager,
    Update
)
from decorators import command_parser
from decorators.chat import get_chat
from decorators.log import log_command
from decorators.users import get_player
from modules import BasicModule


class CommandModule(BasicModule):
    """
    parses commands and invokes event manager
    """
    module_name = 'command_module'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_handler(MessageHandler(Filters.command, self._command_filter))
        self.add_handler(MessageHandler(Filters.photo, self._command_filter))
        super().__init__(event_manager, message_manager, dispatcher)

    @command_parser
    @get_player
    @get_chat
    @log_command
    def _command_filter(self, update: Update, *args, **kwargs):
        self.event_manager.invoke_handler_update(update)
