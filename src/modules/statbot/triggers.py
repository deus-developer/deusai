import datetime
import html
import os
import re
import time
from functools import partial
from pathlib import Path
from typing import Dict, List, Tuple, Pattern, Match, Optional

from pytils import dt
from telegram.ext import MessageHandler, Dispatcher
from telegram.ext.filters import Filters

from src.core import (
    EventManager,
    MessageManager,
    InnerHandler,
    CommandFilter,
    CommandNameFilter,
    InnerUpdate,
)
from src.decorators import command_handler, permissions
from src.decorators.chat import get_chat
from src.decorators.permissions import is_admin
from src.decorators.update import inner_update
from src.decorators.users import get_player
from src.models import Trigger, TelegramUser
from src.modules import BasicModule
from src.utils.functions import CustomInnerFilters


class TriggersModule(BasicModule):
    """
    message sending
    """

    module_name = "triggers"

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("trigger_add"),
                self._trigger_add,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("trigger_remove"),
                self._trigger_remove,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("triggers"),
                self._triggers_ls(),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("triggers_r"),
                self._triggers_ls(remove=True),
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter("trigger_help"),
                self._trigger_help,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandNameFilter("trrem"),
                self._trigger_remove_id,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat],
            )
        )

        self.add_handler(MessageHandler(Filters.text | Filters.command, self._triggered))
        self.add_handler(MessageHandler(Filters.status_update.new_chat_members, self._triggered_actions))

        self.regexps: Dict[int, List[Tuple[Pattern[str], int, Dict[str, bool]]]] = {}

        super().__init__(event_manager, message_manager, dispatcher)

    def startup(self):
        self.refresh_regexes()

    def refresh_regexes(self):
        self.regexps.clear()

        for trigger in Trigger.select():
            regexp = self._generate_regexp(trigger)
            options = {
                "is_admin": trigger.admin_only,
                "pin": trigger.pin_message,
                "repling": trigger.repling,
            }

            regexes = self.regexps.get(trigger.chat.chat_id)
            if regexes is None:
                regexes = []

            regexes.append((regexp, trigger.id, options))
            self.regexps[trigger.chat.chat_id] = regexes

    def _generate_regexp(self, trigger):
        regex = r"[\s\S]*(?P<trigger>{})[\s\S]*" if trigger.in_message else r"(?P<trigger>{})"
        trigger_regex = regex.format(re.escape(trigger.request))

        if trigger.ignore_case:
            return re.compile(trigger_regex, re.IGNORECASE)

        return re.compile(trigger_regex)

    @permissions(is_admin)
    def _trigger_help(self, update: InnerUpdate):
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text="<b>Инструкция по флагам</b>\n"
            'Флаги прописывать под общим "-", пример: -rma\n'
            "1. <code>-r</code> Привязка к регистру\n"
            "2. <code>-m</code> Возможность нахождения внутри какого-то текста\n"
            "3. <code>-a</code> Триггер только для админов\n"
            "4. <code>-p</code> Запинить сообщение после отправки\n"
            "5. <code>-u</code> Проверить уникальность триггера при создании\n"
            "6. <code>-n</code> Отправлять ответ не реплаем на сообщение",
        )

    @inner_update()
    @get_player
    @get_chat
    def _triggered(self, update: InnerUpdate):
        message = update.telegram_update.message

        if not update.chat:
            return

        triggers = self.regexps.get(message.chat_id)
        if not triggers:
            return

        trigger_string = message.text
        if trigger_string in ["!welcome-new", "!welcome-old"]:
            return

        for pattern, trigger_id, options in triggers:
            match = pattern.match(trigger_string)
            if match is None:
                continue

            if options.get("is_admin", False) > update.invoker.is_admin:
                continue

            trigger = Trigger.get_or_none(Trigger.id == trigger_id)
            if trigger is None:
                continue

            repling = options.get("repling", True)
            pin = options.get("pin", False)
            mess = self._send_answer(update, trigger, repling)
            if not mess:
                return

            if pin:
                try:
                    self.message_manager.bot.pin_chat_message(
                        chat_id=mess.chat_id,
                        message_id=mess.message_id,
                        disable_notification=False,
                    )
                except (Exception,):
                    self.logger.warning(f"Не смог запинить триггер {trigger_id}")

    def _trigger_formatter(
        self,
        text: str,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        is_admin_flag: Optional[bool],
        is_banned_flag: Optional[bool],
        last_seen_date: Optional[datetime.datetime],
        user_id: Optional[int],
        chat_id: Optional[int],
    ):
        if is_admin_flag is None:
            is_admin_emoji = ""
        elif is_admin_flag:
            is_admin_emoji = "✅"
        else:
            is_admin_emoji = "❌"

        if is_banned_flag is None:
            is_banned_emoji = ""
        elif is_banned_flag:
            is_banned_emoji = "✅"
        else:
            is_banned_emoji = "❌"

        if last_seen_date is None:
            last_seen_at_text = ""
        else:
            last_seen_at_text = dt.distance_of_time_in_words(last_seen_date, to_time=time.time())

        user_id_text = str(user_id) if user_id else ""
        chat_id_text = str(chat_id) if chat_id else ""

        return (
            text.replace("{username}", html.escape(username or ""))
            .replace("{first_name}", html.escape(first_name or ""))
            .replace("{last_name}", html.escape(last_name or ""))
            .replace("{is_admin}", is_admin_emoji)
            .replace("{is_banned}", is_banned_emoji)
            .replace("{last_seen}", last_seen_at_text)
            .replace("{user_id}", user_id_text)
            .replace("{chat_id}", chat_id_text)
        )

    @inner_update()
    @get_player
    @get_chat
    def _triggered_actions(self, update: InnerUpdate):
        message = update.telegram_update.message
        if update.chat is None:
            return

        triggers = self.regexps.get(message.chat_id)
        if not triggers:
            return

        new_player_triggers: List[Tuple[int, Dict[str, bool]]] = []
        old_player_triggers: List[Tuple[int, Dict[str, bool]]] = []

        for regexp, trigger_id, options in triggers:
            if regexp.match("!welcome-new"):
                new_player_triggers.append((trigger_id, options))

            if regexp.match("!welcome-old"):
                old_player_triggers.append((trigger_id, options))

        for user in message.new_chat_members:
            telegram_user = TelegramUser.get_or_none(user_id=user.id)
            if telegram_user and telegram_user.username:
                formatter = partial(
                    self._trigger_formatter,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    is_admin=telegram_user.is_admin,
                    is_banned=telegram_user.is_banned,
                    last_seen_date=telegram_user.last_seen_date,
                    user_id=telegram_user.user_id,
                    chat_id=telegram_user.chat_id,
                )
            else:
                formatter = partial(
                    self._trigger_formatter,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_admin=False,
                    is_banned=False,
                    last_seen_date=None,
                    user_id=user.id,
                    chat_id=user.id,
                )

            if telegram_user is None:
                player = None
            else:
                player = telegram_user.player.get_or_none()

            if player and player.is_active:
                triggers_ = old_player_triggers
            else:
                triggers_ = new_player_triggers

            for trigger_id, options in triggers_:
                trigger = Trigger.get_or_none(Trigger.id == trigger_id)
                if trigger is None:
                    continue

                repling = options.get("repling", True)
                self._send_answer(update, trigger, reply=repling, formatter=formatter)

    def _send_answer(self, update, trigger, reply: bool = True, formatter=None):
        message = update.telegram_update.message

        def format_text(text):
            return (
                text.replace("{username}", update.invoker.username)
                .replace("{first_name}", update.invoker.first_name or "")
                .replace("{last_name}", update.invoker.last_name or "")
                .replace("{is_admin}", "✅" if update.invoker.is_admin else "❌")
                .replace("{is_banned}", "✅" if update.invoker.is_banned else "❌")
                .replace(
                    "{last_seen}",
                    dt.distance_of_time_in_words(update.invoker.last_seen_date, to_time=time.time()),
                )
                .replace("{user_id}", str(update.invoker.user_id))
                .replace("{chat_id}", str(update.invoker.chat_id))
            )

        if not formatter:
            formatter = format_text

        kwargs = {
            "chat_id": message.chat_id,
            "is_queued": False,
            "caption": formatter(trigger.answer),
            "text": formatter(trigger.answer),
            "title": formatter(trigger.answer),
        }
        if reply:
            kwargs.update({"reply_to_message_id": message.message_id})

        if trigger.type == "text":
            m = self.message_manager.send_message(parse_mode="HTML", **kwargs)
        elif trigger.type == "audio":
            m = self.message_manager.bot.send_audio(audio=open(trigger.file_path, "rb"), **kwargs)
        elif trigger.type == "document":
            m = self.message_manager.bot.send_document(
                document=open(trigger.file_path, "rb"),
                filename=f"{formatter(trigger.answer)}{Path(trigger.file_path).suffix}",
                **kwargs,
            )
        elif trigger.type == "photo":
            m = self.message_manager.bot.send_photo(photo=open(trigger.file_path, "rb"), **kwargs)
        elif trigger.type == "sticker":
            m = self.message_manager.bot.send_sticker(sticker=open(trigger.file_path, "rb"), **kwargs)
        elif trigger.type == "video":
            m = self.message_manager.bot.send_video(video=open(trigger.file_path, "rb"), **kwargs)
        else:
            m = False
        return m

    def _triggers_ls(self, remove=False):
        def handler(self, update: InnerUpdate):
            if not update.chat:
                return
            output = ["<b>Список триггеров:</b>"]
            for idx, trigger in enumerate(Trigger.select().where(Trigger.chat == update.chat), 1):
                output.append(f"\t\t\t\t{idx}. {trigger.request} - {trigger.type}")
                if remove:
                    output.append(f"\t\t\t\t\t-> /trrem_{trigger.id}")
            self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text="\n".join(output),
                parse_mode="HTML",
            )

        return partial(handler, self)

    @permissions(is_admin)
    @command_handler(
        regexp=re.compile(r"(-(?P<flags>\w+))?\s*(?P<trigger>.+)"),
        argument_miss_msg='Пришли сообщение в формате "/trigger_add -flags '
        'Текст триггер"\nПодробнее про флаги: /trigger_help',
    )
    def _trigger_add(self, update: InnerUpdate, match: Match):
        message = update.telegram_update.message
        reply = message.reply_to_message
        if not update.chat:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Команду /trigger_add можно вызвать <b>только в ГРУППЕ</b>",
            )

        if not reply:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Команду /trigger_add можно вызвать <b>только в ответ на текст триггера(ответ)</b>",
            )

        flags, trigger_r = match.group("flags", "trigger")
        if not flags:
            flags = ""

        admin_only = "a" in flags
        ignore_case = "r" not in flags
        pin_message = "p" in flags
        unique_trigger = "u" in flags
        repling = "n" not in flags
        in_message = "m" in flags

        if (
            unique_trigger
            and Trigger.select().where((Trigger.chat == update.chat) & (Trigger.request == trigger_r)).count()
        ):
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Триггер реагирующий на:\n\t{trigger_r}\n\t<i>Уже существует.</i>",
            )

        audio_ = reply.audio
        document_ = reply.document
        photo_ = reply.photo
        sticker_ = reply.sticker
        video_ = reply.video

        answer_text = (reply.caption_html if (photo_ or video_) else reply.text_html) or trigger_r
        voice_ = reply.voice

        file = None
        type_ = "text"
        if audio_:
            file = self.download_file(audio_)
            type_ = "audio"
        elif document_:
            file = self.download_file(document_)
            type_ = "document"
        elif photo_:
            file = self.download_file(photo_[-1])
            type_ = "photo"
        elif sticker_:
            file = self.download_file(sticker_)
            type_ = "sticker"
        elif video_:
            file = self.download_file(video_)
            type_ = "video"
        elif voice_:
            file = self.download_file(voice_)
            type_ = "audio"
        elif not answer_text:
            answer_text = "Триггер!"

        if ignore_case:
            trigger_r = trigger_r.lower()

        Trigger.create(
            request=trigger_r,
            type=type_,
            file_path=file if file else "",
            answer=answer_text,
            chat=update.chat,
            admin_only=admin_only,
            ignore_case=ignore_case,
            pin_message=pin_message,
            repling=repling,
            in_message=in_message,
        )

        self.message_manager.send_message(
            chat_id=message.chat_id,
            text="Вжух и я добавил триггер!\n\tСписок триггеров: /triggers",
        )

        self.refresh_regexes()

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/trigger_remove Название"')
    def _trigger_remove(self, update: InnerUpdate):
        message = update.telegram_update.message
        if not update.chat:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Команду /trigger_remove можно вызвать <b>только в ГРУППЕ</b>",
            )
        trigger_r = update.command.argument

        trigger = Trigger.select().where((Trigger.chat == update.chat) & (Trigger.request == trigger_r))

        if not trigger:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Триггера "{trigger_r}" <b>не существует!</b>',
            )

        if len(trigger) > 1:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Триггеров "{trigger_r}" <b>много!</b>\nУдали его, через /triggers_r',
            )

        trigger = trigger[0]
        trigger.delete_instance()

        if trigger.file_path:
            os.remove(trigger.file_path)

        self.message_manager.send_message(
            chat_id=message.chat_id,
            text=f'Триггер "{trigger_r}" <b>удалён навсегда!</b>',
        )
        self.refresh_regexes()

    @permissions(is_admin)
    def _trigger_remove_id(self, update: InnerUpdate):
        message = update.telegram_update.message
        if not update.chat:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Команду /trrem можно вызвать <b>только в ГРУППЕ</b>",
            )

        trigger_id = update.command.subcommand
        if not trigger_id:
            return

        if not trigger_id.isdigit():
            return self.message_manager.send_message(chat_id=message.chat_id, text="ID должен быть числом")

        trigger_id = int(trigger_id)

        trigger = Trigger.get_or_none(Trigger.id == trigger_id)
        if not trigger:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f"Триггера с id = {trigger_id} <b>не существует!</b>",
            )

        trigger.delete_instance()

        self.message_manager.send_message(
            chat_id=message.chat_id,
            text=f"Триггер с id={trigger_id} <b>удалён навсегда!</b>",
        )
        self.refresh_regexes()

    def download_file(self, object_):
        file = object_.get_file()
        custom_path = f"static/triggers/{file.file_id}{Path(file.file_path).suffix}"
        try:
            file.download(custom_path=custom_path)
        except (Exception,):
            self.logger.warning(f"Ошибка скачивания файла {file.file_id}")
            return

        return custom_path
