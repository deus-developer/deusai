import logging

from telegram.ext import Dispatcher, Handler

from core import EventManager, MessageManager
from core import Handler as InnerHandler


class BasicModule(object):
    """
    Basic class for bot modules.
    All modules must be subclasses of this class
    """
    module_name = None
    group = 10

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_manager = event_manager
        self.message_manager = message_manager
        if not hasattr(self, '_handler_list'):
            self._handler_list = []
        if not hasattr(self, '_inner_handler_list'):
            self._inner_handler_list = []
        if dispatcher:
            self.set_handlers(dispatcher)

    def add_handler(self, handler: Handler):
        if not hasattr(self, '_handler_list'):
            self._handler_list = []
        self._handler_list.append(handler)

    def add_inner_handler(self, handler: InnerHandler):
        if not hasattr(self, '_inner_handler_list'):
            self._inner_handler_list = []
        self._inner_handler_list.append(handler)

    def set_handlers(self, dispatcher: Dispatcher):
        if not self._handler_list and not self._inner_handler_list:
            raise ValueError('You must set at least one handler')
        for handler in self._handler_list:
            dispatcher.add_handler(handler, group=self.group)
        for handler in self._inner_handler_list:
            self.event_manager.add_handler(handler)

    def __str__(self) -> str:
        return self.module_name
