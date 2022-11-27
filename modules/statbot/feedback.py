from telegram import ParseMode
from telegram.ext import Dispatcher
from telegram.utils.helpers import mention_html

from config import settings
from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import (
    command_handler,
    permissions
)
from decorators.permissions import is_admin
from models import Feedback
from modules import BasicModule
from utils.functions import CustomInnerFilters


class FeedbackModule(BasicModule):

    module_name = 'feedback'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('ans'), self._answer,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_goat_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('fb'), self._feedback,
                [CustomInnerFilters.from_player, CustomInnerFilters.private]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_admin)
    @command_handler()
    def _answer(self, update: Update, *args, **kwargs):  # TODO: Добавить поддержку медиавложений
        message = update.telegram_update.message
        if not message.reply_to_message:
            return
        if not message.reply_to_message.from_user.id == message.bot.id:
            return self.message_manager.send_message(chat_id=message.chat_id, text='⚠Команда должна быть использована на feedback пользователя.⚠')
        message_text = f'<b>Администрация</b> отвечает вам:\n 	{update.command.argument}'
        message_id = message.reply_to_message.message_id
        feedback = Feedback.get_or_none(message_id=message_id)
        if not feedback:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text='⚠Такого фидбэка не существует⚠'
            )
        feedback.status = 1
        feedback.save()
        self.message_manager.send_message(chat_id=feedback.original_chat_id, text=message_text, parse_mode=ParseMode.HTML)
        self.message_manager.send_message(chat_id=message.chat_id, reply_to_message_id=message.message_id, text='Ответил этому человеку.')

    @command_handler(argument_miss_msg='Тут какая-то ошибочка')
    def _feedback(self, update: Update, *args, **kwargs):  # TODO: Добавить поддержку медиавложений, оптимизировать процесс => переработать
        message = update.telegram_update.message
        feedback = Feedback(original_chat_id=message.chat_id)
        message_text = f'Игрок {mention_html(update.invoker.user_id, update.player.nickname)} пишет:\n 	{update.command.argument}'
        m = self.message_manager.send_message(
            chat_id=settings.GOAT_ADMIN_CHAT_ID,
            text=message_text,
            parse_mode=ParseMode.HTML,
            is_queued=False
        )
        if not m:
            return
        feedback.message_id = m.message_id
        feedback.save()
        self.message_manager.send_message(chat_id=message.chat_id, text='Сообщение отправлено в Администрацию.', reply_to_message_id=message.message_id)
