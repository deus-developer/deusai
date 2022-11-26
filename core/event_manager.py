from apscheduler.schedulers.background import BackgroundScheduler

from .handler import Handler
from .update import Update


class EventManager:
    """this class broadcasts inside updates over modules"""

    def __init__(self, scheduler: BackgroundScheduler):
        self.scheduler = scheduler
        self.handlers = []

    def add_handler(self, handler: Handler):
        self.handlers.append(handler)

    def invoke_handler_update(self, update: Update):
        for handler in self.handlers:
            handler(update=update)
