from telegram import Bot, Update
from telegram.ext import Dispatcher, Filters, MessageHandler

from src.core import EventManager, MessageManager
from src.models import TelegramChat, TelegramUser
from src.modules import BasicModule


class ActivityModule(BasicModule):
    """
    Tracks new users, chats, and user`s activity
    """

    module_name = "activity"
    group = 0

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_handler(MessageHandler(Filters.all, self._write_activity))
        super().__init__(event_manager, message_manager, dispatcher)

    def _write_activity(self, _: Bot, update: Update):
        user_data = update.effective_user
        if user_data is None:
            return

        chat_data = update.effective_chat

        telegram_user = {
            TelegramUser.user_id: user_data.id,
            TelegramUser.username: user_data.username,
            TelegramUser.first_name: user_data.first_name,
            TelegramUser.last_name: user_data.last_name,
        }
        telegram_user_update = {
            TelegramUser.username: user_data.username,
            TelegramUser.first_name: user_data.first_name,
            TelegramUser.last_name: user_data.last_name,
        }

        if chat_data.type == "private":
            telegram_user[TelegramUser.chat_id] = chat_data.id
            telegram_user_update[TelegramUser.chat_id] = chat_data.id

        TelegramUser.insert(telegram_user).on_conflict(
            conflict_target=[
                TelegramUser.user_id,
            ],
            update=telegram_user_update,
        ).execute()

        if chat_data.type == "private":
            return

        telegram_chat = {
            TelegramChat.chat_id: chat_data.id,
            TelegramChat.chat_type: chat_data.type,
            TelegramChat.title: chat_data.title,
        }
        telegram_chat_update = {TelegramChat.title: chat_data.title}

        TelegramChat.insert(telegram_chat).on_conflict(
            conflict_target=[
                TelegramChat.chat_id,
            ],
            update=telegram_chat_update,
        ).execute()
