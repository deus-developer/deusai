import functools
import re
import time
import os

from telegram import ParseMode
from telegram.ext import MessageHandler, Dispatcher
from telegram.ext.filters import Filters
from pathlib import Path as path_file
from pytils import dt

from core import EventManager, MessageManager, Handler as InnerHandler, CommandFilter, CommandNameFilter, Update
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_player
from decorators.chat import get_chat
from decorators.update import inner_update
from utils.functions import CustomInnerFilters, get_link
from modules import BasicModule
from models import Trigger, TelegramUser


class TriggersModule(BasicModule): #TODO: Переработать
    """
    message sending
    """
    
    module_name = 'triggers'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('trigger_add'), self._trigger_add,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('trigger_remove'), self._trigger_remove,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('triggers'), self._triggers_ls(),
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('triggers_r'), self._triggers_ls(remove=True),
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandFilter('trigger_help'), self._trigger_help,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandNameFilter('trrem'), self._trigger_remove_id,
                                                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))

        self.add_handler(MessageHandler(Filters.text | Filters.command, self._triggered))
        self.add_handler(MessageHandler(Filters.status_update.new_chat_members, self._triggered_actions))

        self.regexps = {

        }
        self._load_regexps()
        super().__init__(event_manager, message_manager, dispatcher)

    def _load_regexps(self):
        self.regexps = {}
        for trigger in Trigger.select():
            regexp = self._generate_regexp(trigger)
            options = {
                'is_admin': trigger.admin_only,
                'pin': trigger.pin_message,
                'repling': trigger.repling
            }
            lst = self.regexps.get(trigger.chat.chat_id, None)
            if not lst:
                lst = []
            lst.append((regexp, trigger.id, options))
            self.regexps.update({trigger.chat.chat_id: lst})
# left_chat_member
# new_chat_members
    def _generate_regexp(self, trigger):
        re_ = r'[\s\S]*(?P<trigger>{})[\s\S]*' if trigger.in_message else r'(?P<trigger>{})'
        regexp = re.compile(re_.format(re.escape(trigger.request)), re.IGNORECASE) if trigger.ignore_case else re.compile(re_.format(re.escape(trigger.request)))
        return regexp

    @permissions(is_admin)
    def _trigger_help(self, update: Update):
        self.message_manager.send_message(chat_id=update.telegram_update.message.chat_id, 
                                                text='<b>Инструкция по флагам</b>\n'
                                                        'Флаги прописывать под общим "-", пример: -rma\n'
                                                        '1. <code>-r</code> Привязка к регистру\n'
                                                        '2. <code>-m</code> Возможность нахождения внутри какого-то текста\n'
                                                        '3. <code>-a</code> Триггер только для админов\n'
                                                        '4. <code>-p</code> Запинить сообщение после отправки\n'
                                                        '5. <code>-u</code> Проверить уникальность триггера при создании\n'
                                                        '6. <code>-n</code> Отправлять ответ не реплаем на сообщение', parse_mode='HTML')
    @inner_update()
    @get_player
    @get_chat
    def _triggered(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message

        if not update.chat:
            return

        triggers = self.regexps.get(message.chat_id, None)
        if not triggers:
            return

        trigger_r = message.text
        if trigger_r in ['!welcome-new', '!welcome-old']:
            return
        for regexp, id_, options in triggers:
            m = regexp.match(trigger_r)
            if not m:
                continue
            if options.get('is_admin', False) > update.invoker.is_admin:
                continue

            trigger = Trigger.get_or_none(Trigger.id == id_)
            if not trigger:
                continue

            repling = options.get('repling', True)
            pin = options.get('pin', False)
            mess = self._send_answer(update, trigger, repling)
            if not mess:
                return
            if pin:
                try:
                    self.message_manager.bot.pin_chat_message(  chat_id=mess.chat_id,
                                                                message_id=mess.message_id,
                                                                disable_notification=False)
                except:
                    self.logger.warning(f'Не смог запинить триггер {id_}')

    @inner_update()
    @get_player
    @get_chat
    def _triggered_actions(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        if not update.chat:
            return
        triggers = self.regexps.get(message.chat_id, None)
        if not triggers:
            return

        triggers_new = []
        triggers_old = []
        for regexp, id_, options in triggers:
            new = regexp.match('!welcome-new')
            old = regexp.match('!welcome-old')
            if new:
                triggers_new.append((id_, options))
            if old:
                triggers_old.append((id_, options))

        for user in message.new_chat_members:
            tguser = TelegramUser.get_or_none(user_id = user.id)
            if tguser and tguser.username:
                formatter = lambda x: x.replace('{username}', tguser.username or 'It`s Username')\
                                        .replace('{first_name}', tguser.first_name or '')\
                                        .replace('{last_name}', tguser.last_name or '')\
                                        .replace('{is_admin}', '✅' if tguser.is_admin else '❌')\
                                        .replace('{is_banned}', '✅' if tguser.is_banned else '❌')\
                                        .replace('{last_seen}', dt.distance_of_time_in_words(tguser.last_seen_date, to_time=time.time()))\
                                        .replace('{user_id}', str(tguser.user_id))\
                                        .replace('{chat_id}', str(tguser.chat_id))
            else:
                formatter = lambda x: x.replace('{username}', user.username or 'It`s Username')\
                                        .replace('{first_name}', user.first_name or '')\
                                        .replace('{last_name}', user.last_name or '')\
                                        .replace('{is_admin}', '❌')\
                                        .replace('{is_banned}', '❌')\
                                        .replace('{last_seen}', '')\
                                        .replace('{user_id}', str(user.id))\
                                        .replace('{chat_id}', str(user.id))
            for id_, options in triggers_new if not (tguser and tguser.player.exists() and tguser.player.get().is_active) else triggers_old:
                trigger = Trigger.get_or_none(Trigger.id == id_)
                if not trigger:
                    continue
                repling = options.get('repling', True)
                pin = options.get('pin', False)
                self._send_answer(update, trigger, reply=repling, formatter=formatter)

    def _send_answer(self, update, trigger, reply = True, formatter = None):
        message = update.telegram_update.message
        def format_text(text):
            return text.replace('{username}', update.invoker.username)\
                        .replace('{first_name}', update.invoker.first_name or '')\
                        .replace('{last_name}', update.invoker.last_name or '')\
                        .replace('{is_admin}', '✅' if update.invoker.is_admin else '❌')\
                        .replace('{is_banned}', '✅' if update.invoker.is_banned else '❌')\
                        .replace('{last_seen}', dt.distance_of_time_in_words(update.invoker.last_seen_date, to_time=time.time()))\
                        .replace('{user_id}', str(update.invoker.user_id))\
                        .replace('{chat_id}', str(update.invoker.chat_id))
        if not formatter:
            formatter = format_text
        kwargs = {
            'chat_id': message.chat_id,
            'is_queued': False,
            'caption': formatter(trigger.answer),
            'text': formatter(trigger.answer),
            'title': formatter(trigger.answer),
        }
        if reply:
            kwargs.update({'reply_to_message_id': message.message_id})

        m = False
        if trigger.type == 'text':
            m = self.message_manager.send_message(parse_mode='HTML', **kwargs)
        elif trigger.type == 'audio':
            m = self.message_manager.bot.send_audio(audio=open(trigger.file_path, 'rb'), **kwargs)
        elif trigger.type == 'document':
            m = self.message_manager.bot.send_document( document=open(trigger.file_path, 'rb'),
                                                        filename=f'{formatter(trigger.answer)}{path_file(trigger.file_path).suffix}',
                                                        **kwargs)
        elif trigger.type == 'photo':
            m = self.message_manager.bot.send_photo(photo=open(trigger.file_path, 'rb'), **kwargs)
        elif trigger.type == 'sticker':
            m = self.message_manager.bot.send_sticker(sticker=open(trigger.file_path, 'rb'), **kwargs)
        elif trigger.type == 'video':
            m = self.message_manager.bot.send_video(video=open(trigger.file_path, 'rb'), **kwargs)
        else:
            m = False
        return m

    def _triggers_ls(self, remove=False):
        def handler(self, update: Update, *args, **kwargs):
            if not update.chat:
                return
            output = ['<b>Список триггеров:</b>']
            for idx, trigger in enumerate(Trigger.select().where(Trigger.chat == update.chat), 1):
                output.append(f'\t\t\t\t{idx}. {trigger.request} - {trigger.type}')
                if remove:
                    output.append(f'\t\t\t\t\t-> /trrem_{trigger.id}')
            self.message_manager.send_message(chat_id=update.telegram_update.message.chat_id,
                                                text='\n'.join(output),
                                                parse_mode='HTML')
        return functools.partial(handler, self)
    @permissions(is_admin)
    @command_handler(regexp=re.compile(r'(-(?P<flags>\w+))?\s*(?P<trigger>.+)'),
                     argument_miss_msg='Пришли сообщение в формате "/trigger_add -flags Текст триггер"\nПодробнее про флаги: /trigger_help')
    def _trigger_add(self, update: Update, match, *args, **kwargs):
        message = update.telegram_update.message
        reply = message.reply_to_message
        if not update.chat:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Команду /trigger_add можно вызвать <b>только в ГРУППЕ</b>',
                                                        parse_mode='HTML')

        if not reply:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Команду /trigger_add можно вызвать <b>только в ответ на текст триггера(ответ)</b>',
                                                        parse_mode='HTML') 
 
        flags, trigger_r = match.group('flags', 'trigger')
        if not flags:
            flags = ''

        admin_only = 'a' in flags
        ignore_case = 'r' not in flags
        pin_message = 'p' in flags
        unique_trigger = 'u' in flags
        repling = 'n' not in flags
        in_message = 'm' in flags

        if unique_trigger and Trigger.select().where((Trigger.chat == update.chat) & (Trigger.request == trigger_r)).count():
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Триггер реагирующий на:\n\t{trigger_r}\n\t<i>Уже существует.</i>',
                                                        parse_mode='HTML')
        audio_ = reply.audio
        document_ = reply.document
        photo_ = reply.photo
        sticker_ = reply.sticker
        video_ = reply.video

        answer_text = (reply.caption_html if (photo_ or video_) else reply.text_html) or trigger_r
        voice_ = reply.voice

        file = None
        type_ = 'text'
        if audio_:
            file = self.download_file(audio_)
            type_ = 'audio'
        elif document_:
            file = self.download_file(document_)
            type_ = 'document'
        elif photo_:
            file = self.download_file(photo_[-1])
            type_ = 'photo'
        elif sticker_:
            file = self.download_file(sticker_)
            type_ = 'sticker'
        elif video_:
            file = self.download_file(video_)
            type_ = 'video'
        elif voice_:
            file = self.download_file(voice_)
            type_ = 'audio'
        elif not answer_text:
            answer_text = 'Триггер!'
            
        if ignore_case:
            trigger_r = trigger_r.lower()

        Trigger.create(request=trigger_r,
                        type = type_,
                        file_path=file if file else '',
                        answer=answer_text,
                        chat = update.chat,
                        admin_only = admin_only,
                        ignore_case = ignore_case,
                        pin_message = pin_message,
                        repling = repling,
                        in_message = in_message
                    )

        self.message_manager.send_message(chat_id=message.chat_id,
                                            text='Вжух и я добавил триггер!\n\tСписок триггеров: /triggers')

        self._load_regexps()

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/trigger_remove Название"')
    def _trigger_remove(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        if not update.chat:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Команду /trigger_remove можно вызвать <b>только в ГРУППЕ</b>',
                                                        parse_mode='HTML')
        trigger_r = update.command.argument

        trigger = Trigger.select().where((Trigger.chat == update.chat) & (Trigger.request == trigger_r))

        if not trigger:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Триггера "{trigger_r}" <b>не существует!</b>',
                                                        parse_mode='HTML') 
        if len(trigger) > 1:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Триггеров "{trigger_r}" <b>много!</b>\nУдали его, через /triggers_r',
                                                        parse_mode='HTML')
        trigger = trigger[0]
        trigger.delete_instance()

        if trigger.file_path:
            os.remove(trigger.file_path)

        self.message_manager.send_message(  chat_id=message.chat_id,
                                            text=f'Триггер "{trigger_r}" <b>удалён навсегда!</b>',
                                            parse_mode='HTML')
        self._load_regexps()

    @permissions(is_admin)
    def _trigger_remove_id(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        if not update.chat:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Команду /trrem можно вызвать <b>только в ГРУППЕ</b>',
                                                        parse_mode='HTML')
        trigger_id = update.command.subcommand
        if not trigger_id:
            return

        if not trigger_id.isdigit():
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text='ID должен быть числом')
        trigger_id = int(trigger_id)

        trigger = Trigger.get_or_none(Trigger.id == trigger_id)
        if not trigger:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Триггера с user_id = {trigger_id} <b>не существует!</b>',
                                                        parse_mode='HTML')
        trigger.delete_instance()

        self.message_manager.send_message(  chat_id=message.chat_id,
                                            text=f'Триггер с user_id={trigger_id} <b>удалён навсегда!</b>',
                                            parse_mode='HTML')
        self._load_regexps()

    def download_file(self, object_):
        file = object_.get_file()
        custom_path = f'files/triggers/{file.file_id}{path_file(file.file_path).suffix}'
        try:
            file.download(custom_path=custom_path)
        except:
            self.logger.warning(f'Ошибка скачивания файла {file.file_id}')
            return False

        return custom_path