import telegram
from telegram.ext import Dispatcher

from core import EventManager, MessageManager, CommandFilter, InnerHandler, InnerUpdate
from modules import BasicModule
from utils.functions import CustomInnerFilters


class StartModule(BasicModule):
    """
    start handler
    """
    module_name = 'start'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('start'),
                self._start,
                [CustomInnerFilters.private]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('help'),
                self._help,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def _help(self, update: InnerUpdate):
        """/help в боте"""
        text = '''<b>Справка по использованию Deus AI</b>
        - https://teletype.in/@deusdeveloper/xhu6oDMS6'''
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    def _start(self, update: InnerUpdate):
        """Приветствие в боте"""
        if not update.player:
            message_text = (
                "Привет, давай знакомиться!\n"
                "Перейди в игру, открой 📟 Пип-бой, "
                "нажми команду <code>/me</code> внизу и перешли мне сообщение с полным профилем"
            )
            reply_markup = telegram.InlineKeyboardMarkup(
                [
                    [
                        telegram.InlineKeyboardButton(
                            text="Перейти в игру",
                            url="https://t.me/WastelandWarsBot"
                        )
                    ]
                ]
            )
            return self.message_manager.send_message(
                chat_id=update.invoker.chat_id,
                text=message_text,
                reply_markup=reply_markup
            )

        reply_markup = telegram.ReplyKeyboardMarkup(
            keyboard=[
                ['📊 Статы', '📈 Прогресс', '🗓 Рейды'],
            ],
            one_time_keyboard=False,
            resize_keyboard=True
        )

        return self.message_manager.send_message(
            chat_id=update.invoker.chat_id,
            text="Рад тебя видеть",
            reply_markup=reply_markup
        )
