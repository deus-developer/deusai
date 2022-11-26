import re
from telegram import Message

command_pattern = r"/(?P<command>(?P<name>[^\s_@]+)_?(?P<subcomand>[^\s@]*))@?(?P<botname>\S*)\s*(?P<args>.*)"
command_regexp = re.compile(command_pattern, re.DOTALL)


class Command:
    def __init__(self, message: Message):
        self.command = None
        self.name = None
        self.subcommand = None
        self.bot_name = None
        self.argument = None
        if not message:
            return
        text = message.text or message.caption or ''

        m = command_regexp.match(text)
        if m:
            self.command, self.name, self.subcommand, self.bot_name, self.argument = m.groups()
            self.argument = self.argument.strip()

    def __repr__(self):
        bot = '@' + self.bot_name if self.bot_name else ''
        args = ' ' + self.argument if self.argument else ''
        return f"{self.command}{bot}{args}"

    def is_valid(self):
        return self.command is not None

    def match(self, regexp):
        return regexp.match(self.argument)
