from telegram.ext import Dispatcher, MessageHandler, Filters
from core import EventManager, MessageManager, Update
from modules import BasicModule
from decorators.users import get_player
from decorators.update import inner_update
import telegram

class ButtonsList:
    class INFO_BUTTON_C:
        def __init__(self):
            self.name = '🛈ИНФО'

        def filter(self, update: Update):
            message = update.telegram_update.message
            if not message:
                return False
            if message.text != self.name:
                return False
            update.command = Command()
            return True

    class STAT_BUTTON_C:
        def __init__(self):
            self.name = '📟Статистика'

        def filter(self, update: Update):
            message = update.telegram_update.message
            if not message:
                return False
            if message.text != self.name:
                return False
            update.command = Command()
            return True

    class PROGRESS_BUTTON_C:
        def __init__(self):
            self.name = '📈Прогресс'

        def __call__(self, update: Update):
            message = update.telegram_update.message
            if not message:
                return False
            if message.text != self.name:
                return False
            update.command = Command()
            return True

    buttons = [INFO_BUTTON, STAT_BUTTON, PROGRESS_BUTTON]

class KeyBoardButton(BasicModule):
    """
    parses commands and invokes event manager
    """
    module_name = 'keyboard_module'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_handler(MessageHandler(Filters.text, self._keyboard_filter))
        super().__init__(event_manager, message_manager, dispatcher)

    @inner_update()
    @get_player
    def _keyboard_filter(self, update: Update, *args, **kwargs):
        state = update.invoker.keyboard_state
        if not ( state >= 0 and state < len(ButtonsList.menus) ):
            return

        buttons = ButtonsList.menus[state]
        for button in buttons:
            button(update)