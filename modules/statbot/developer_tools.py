from telegram.ext import Dispatcher

from core import EventManager, MessageManager, InnerHandler, CommandFilter, InnerUpdate
from decorators import permissions
from decorators.permissions import is_developer
from modules import BasicModule
from utils.functions import CustomInnerFilters


class DeveloperToolsModule(BasicModule):
    module_name = 'dev_tools'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('commands'),
                self._commands,
                [CustomInnerFilters.private]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_developer)
    def _commands(self, update: InnerUpdate):
        output = f'Всего обработчиков в боте: {len(self.event_manager.handlers)}\n'
        output += 'Те что являются командами ниже:\n'
        for handler in self.event_manager.handlers:
            if isinstance(handler.filter, CommandFilter):
                output += f'▫️ /{handler.filter.command}'
                if handler.filter.description:
                    output += f'\t▫️{handler.filter.description}'
                output += '\n'

        update.telegram_update.message.reply_text(text=output)
