from telegram.ext import Dispatcher, MessageHandler, Filters

from src.core import EventManager, MessageManager, InnerUpdate
from src.decorators import command_parser
from src.decorators.chat import get_chat
from src.decorators.log import log_command
from src.decorators.users import get_player
from src.modules import BasicModule


class CommandModule(BasicModule):
    """
    parses commands and invokes event manager
    """

    module_name = "command_module"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_handler(MessageHandler(Filters.command, self._command_filter))
        self.add_handler(MessageHandler(Filters.photo, self._command_filter))
        super().__init__(event_manager, message_manager, dispatcher)

    @command_parser
    @get_player
    @get_chat
    @log_command
    def _command_filter(self, update: InnerUpdate):
        self.event_manager.invoke_handler_update(update)
