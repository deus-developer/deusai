import logging
from typing import Optional

from telegram.ext import Dispatcher, Handler

from src.core import EventManager, MessageManager
from src.core import InnerHandler


class BasicModule:
    """
    Basic class for bot modules.
    All modules must be subclasses of this class
    """

    module_name: Optional[str] = None
    group: int = 10

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_manager = event_manager
        self.message_manager = message_manager

        if not hasattr(self, "_handler_list"):
            self._handler_list = []

        if not hasattr(self, "_inner_handler_list"):
            self._inner_handler_list = []

        if dispatcher:
            self.set_handlers(dispatcher)

    def add_handler(self, handler: Handler) -> None:
        if not hasattr(self, "_handler_list"):
            self._handler_list = []
        self._handler_list.append(handler)

    def add_inner_handler(self, handler: InnerHandler) -> None:
        if not hasattr(self, "_inner_handler_list"):
            self._inner_handler_list = []
        self._inner_handler_list.append(handler)

    def set_handlers(self, dispatcher: Dispatcher) -> None:
        for handler in self._handler_list:
            dispatcher.add_handler(handler, group=self.group)

        for handler in self._inner_handler_list:
            self.event_manager.add_handler(handler)

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def __str__(self) -> str:
        return self.module_name
