import datetime
import telegram

from core import Command
import json


class Update:
    def __init__(
        self, telegram_update: telegram.Update = None, delay: datetime.timedelta = None,
        command: Command = None
    ):
        self.date = None
        self.timedelta = None
        self.telegram_update = None
        self.delay = delay
        self.command = command
        self.invoker = None
        self.player = None
        self.chat = None

        if telegram_update is not None:
            self.telegram_update = telegram_update
            if telegram_update.message:
                self.date = telegram_update.message.forward_date or telegram_update.message.date
                self.timedelta = telegram_update.message.date - telegram_update.message.forward_date \
                    if telegram_update.message.forward_date else datetime.timedelta(0)

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
