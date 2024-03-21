from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher

from src.core import (
    EventManager,
    MessageManager,
    InnerHandler,
    UpdateFilter,
    InnerUpdate,
    CommandFilter,
)
from src.modules import BasicModule
from src.modules.statbot.parser import PlayerParseResult
from src.utils.functions import CustomInnerFilters


class FractionModule(BasicModule):
    module_name = "fraction"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_inner_handler(
            InnerHandler(
                UpdateFilter("showdata"),
                self.show_data_handler,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter(command="showdata", description="Заглушка для /showdata"),
                self.show_data_missclick_handler,
                [
                    CustomInnerFilters.from_admin_chat_or_private,
                ],
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    def show_data_missclick_handler(self, update: InnerUpdate):
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text="Эту команду нужно слать в @WastelandWarsBot, а ответ отправлять мне.",
        )

    def show_data_handler(self, update: PlayerParseResult):
        if update.showdata.enabled:
            return self.message_manager.send_message(chat_id=update.effective_chat_id, text="Молодец, так держать!")

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="📊 Предоставить доступ",
                        url="https://t.me/share/url?url=/showdata",
                    )
                ]
            ]
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text="Оу, ты закрыл доступ к данным. Открой его обратно :)",
            reply_markup=reply_markup,
        )
