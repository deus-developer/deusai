from typing import List

from apscheduler.schedulers.background import BackgroundScheduler

from .handler import InnerHandler
from .update import InnerUpdate


class EventManager:
    """this class broadcasts inside updates over modules"""

    def __init__(self, scheduler: BackgroundScheduler):
        self.scheduler = scheduler
        self.handlers: List[InnerHandler] = []

    def add_handler(self, handler: InnerHandler) -> None:
        self.handlers.append(handler)

    def invoke_handler_update(self, update: InnerUpdate) -> None:
        for handler in self.handlers:
            handler(update=update)
