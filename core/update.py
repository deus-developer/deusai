import datetime
import telegram

from config import settings
from core import Command
import json


class Update:
    def __init__(
        self, telegram_update: telegram.Update = None, delay: datetime.timedelta = None,
        command: Command = None
    ):
        self.taking = None
        self.taking_success = None
        self.message = None
        self.scuffle = None
        self.lynch = None
        self.pokemob_dead = None
        self.dzen_enhancement = None
        self.notebook = None
        self.stock = None
        self.date = None
        self.timedelta = None
        self.telegram_update = telegram_update
        self.delay = delay
        self.command = command
        self.invoker = None
        self.player = None
        self.chat = None

        if telegram_update and telegram_update.message and telegram_update.message.forward_date:
            self.date = telegram_update.message.forward_date.astimezone(settings.timezone)
            self.timedelta = self.telegram_update.message.date.astimezone(settings.timezone) - self.date
        elif telegram_update and telegram_update.message:
            self.date = telegram_update.message.date.astimezone(settings.timezone)
            self.timedelta = datetime.timedelta(0)

    def to_json(self):
        from utils.functions import dict_serialize
        return json.dumps(dict_serialize(self.__dict__))


class UpdateFilter:
    def __init__(self, attribute: str = None):
        self.attributes = [attribute] if attribute else []

    def __and__(self, other):
        ret = UpdateFilter()
        ret.attributes = [*self.attributes, *other.attributes]
        return ret

    def __call__(self, update: Update):
        return all(
            [
                bool(getattr(update, attr, False)) for attr in self.attributes]
        )


class CommandFilter:
    def __init__(self, command: str, description: str = ''):
        self.command = command.lower()
        self.description = description

    def _match(self, update: Update):
        return update.command.command.lower() == self.command if update.command else False

    def __call__(self, update: Update):
        return self._match(update)


class CommandNameFilter(CommandFilter):
    def __init__(self, command_name):
        super().__init__(command_name)

    def _match(self, update: Update):
        return update.command.name.lower() == self.command if update.command else False


class UpdateCallableFilter:
    def __init__(self, attribute: callable = None):
        self.attributes = [attribute] if attribute else []

    def __and__(self, other):
        ret = UpdateCallableFilter()
        ret.attributes = [*self.attributes, *other.attributes]
        return ret

    def __call__(self, update: Update):
        return all([bool(attr(update)) for attr in self.attributes])
