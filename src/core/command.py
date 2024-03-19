import re
from dataclasses import dataclass
from typing import Optional, Pattern, Match, Self

from telegram import Message

command_regexp = re.compile(
    r"/(?P<command>(?P<name>[^\s_@]+)_?(?P<subcomand>[^\s@]*))@?(?P<botname>\S*)\s*(?P<args>.*)", re.DOTALL
)


@dataclass
class Command:
    command: Optional[str] = None
    name: Optional[str] = None
    subcommand: Optional[str] = None
    bot_name: Optional[str] = None
    argument: Optional[str] = None

    @classmethod
    def from_message(cls, message: Message) -> Self:
        text = message.text or message.caption or ""
        match = command_regexp.match(text)
        if match is None:
            return cls()

        command, name, subcommand, bot_name, argument = match.groups()
        argument = argument.strip()
        return cls(command=command, name=name, subcommand=subcommand, bot_name=bot_name, argument=argument)

    def is_valid(self) -> bool:
        return bool(self.command)

    def match(self, regexp: Pattern[str]) -> Optional[Match[str]]:
        return regexp.match(self.argument)
