from core import Command, Update as InnerUpdate
class ButtonsList:
    class INFO_BUTTON_C:
        def __init__(self):
            self.name = '🛈ИНФО'

        def filter(self, update: InnerUpdate):
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

        def filter(self, update: InnerUpdate):
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

        def filter(self, update: InnerUpdate):
            print('filtering')
            message = update.telegram_update.message
            print(message.text)
            if not message:
                return False
            if message.text != self.name:
                return False
            update.command = Command()
            return True


    INFO_BUTTON = INFO_BUTTON_C()
    STAT_BUTTON = STAT_BUTTON_C()
    PROGRESS_BUTTON = PROGRESS_BUTTON_C()

    buttons = [INFO_BUTTON, STAT_BUTTON, PROGRESS_BUTTON]