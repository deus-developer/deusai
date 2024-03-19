import datetime
from typing import Optional, List

import telegram

from core import Command
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import TelegramUser, Player, TelegramChat, Pig


class InnerUpdate:
    def __init__(
        self,
        telegram_update: Optional[telegram.Update] = None,
        delay: Optional[datetime.timedelta] = None,
        command: Optional[Command] = None
    ):
        self.date: Optional[datetime.datetime] = None
        self.timedelta: Optional[datetime.timedelta] = None

        self.telegram_update = telegram_update
        self.effective_chat_id: Optional[int] = None

        self.delay = delay
        self.command = command

        self.invoker: Optional["TelegramUser"] = None
        self.player: Optional["Player"] = None
        self.chat: Optional["TelegramChat"] = None
        self.pig: Optional["Pig"] = None

        self.karma_transaction = None

        if self.telegram_update and self.telegram_update.message:
            self.effective_chat_id = self.telegram_update.message.chat_id
            
            self.date = telegram_update.message.forward_date or telegram_update.message.date

            if self.telegram_update.message.forward_date:
                self.timedelta = telegram_update.message.date - telegram_update.message.forward_date
            else:
                self.timedelta = datetime.timedelta(0)


class UpdateFilter:
    def __init__(self, attribute: Optional[str] = None):
        self.attributes: List[str] = [attribute] if attribute else []

    def __and__(self, other: "UpdateFilter") -> "UpdateFilter":
        result = UpdateFilter()
        result.attributes = [*self.attributes, *other.attributes]
        return result

    def __call__(self, update: InnerUpdate) -> bool:
        return all(
            getattr(update, attribute, False)
            for attribute in self.attributes
        )


class CommandFilter:
    def __init__(self, command: str, description: str = ''):
        self.command = command.lower()
        self.description = description

    def _match(self, update: InnerUpdate) -> bool:
        if update.command:
            return update.command.command.lower() == self.command

        return False

    def __call__(self, update: InnerUpdate) -> bool:
        return self._match(update)


class CommandNameFilter(CommandFilter):
    def __init__(self, command_name):
        super().__init__(command_name)

    def _match(self, update: InnerUpdate):
        if update.command:
            return update.command.name.lower() == self.command

        return False
