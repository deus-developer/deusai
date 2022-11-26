import functools
import re
import datetime

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from config import settings
from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, CommandNameFilter, Update
from modules.statbot.karma import Karma
from modules import BasicModule
from models import SPItem, SPProcess
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_player
from utils.functions import CustomInnerFilters, get_link
from decorators.update import inner_update
from decorators.log import log
from telegram.utils.helpers import mention_html

class ShopModule(BasicModule): #TODO: Ввести механизм скидок

    module_name = 'shop'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('sp_item_create'), self._create_item, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('sp_item_remove'), self._remove_item, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))

        self.add_inner_handler(InnerHandler(CommandFilter('shop'), self._shop_menu, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('my_purch'), self._crm_process_list(0), [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('my_process'), self._crm_process_list(1), [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('my_process_all'), self._crm_process_list(2), [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandNameFilter('sinfo'), self._info, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandNameFilter('sbuy'), self._buy, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))

        self._re_crm_accept = re.compile(r'crm_accept_(?P<user_id>\d+)')
        self._re_crm_refuse = re.compile(r'crm_refuse_(?P<user_id>\d+)')
        self._re_crm_confirm = re.compile(r'crm_confirm_(?P<user_id>\d+)')
        self._re_crm_return = re.compile(r'crm_return_(?P<user_id>\d+)')

        # self.add_handler(CallbackQueryHandler(self._crm_accept, pattern=self._re_crm_accept))
        # self.add_handler(CallbackQueryHandler(self._crm_refuse, pattern=self._re_crm_refuse))
        # self.add_handler(CallbackQueryHandler(self._crm_confirm, pattern=self._re_crm_confirm))
        # self.add_handler(CallbackQueryHandler(self._crm_return, pattern=self._re_crm_return))

        super().__init__(event_manager, message_manager, dispatcher)
        # self.event_manager.scheduler.add_job(self._crm_update_msgs, 'interval', minutes=5)

    def _shop_menu(self, update: Update, *args, **kwargs):
        output = ['ᗒ\t\t\t\t\tМагазин Deus Ex Machina\t\t\t\t\tᗕ']
        for item in SPItem.select().order_by(SPItem.price.desc()):
            output.append(f'\t\t➤{item.name} - {item.price}☯️')
            output.append(f'\t\t\t└──Информация: /sinfo_{item.id}')
            output.append(f'\t\t\t└──Купить: {"/sbuy_"+str(item.id) if update.player.karma >= item.price else "Недостаточно ресурсов"}\n')
        return self.message_manager.send_message(   chat_id=update.telegram_update.message.chat_id,
                                                    text='\n'.join(output),
                                                    parse_mode=ParseMode.HTML)

    def _buy(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        id = update.command.subcommand
        if not id:
            return

        if not id.isdigit():
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text='ID должен быть числом')
        id = int(id)

        item = SPItem.get_or_none(id=id)
        if not item:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text='Такого предмета не существует.')
        sex = update.player.settings.sex
        if not update.invoker.is_admin:
            return message.reply_text(f'Магазинчик закрыт мо{"й" if sex == 0 else "я"} хорош{"ий" if sex == 0 else "ая"} :)')
        if update.player.karma < item.price:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Увы, но тебе не хватает {item.price-update.player.karma}☯️.')
        player = update.player
        process = SPProcess(player=player, item=item, karma=player.karma-item.price, raids21=player.raids21, loose_raids_f=player.loose_raids_f)
        process.save()
        self._crm_task_edit(process)
        self.message_manager.send_message(  chat_id=message.chat_id,
                                            text=f'Заявка на покупку "{item.name}" отправлена Администрации\n'
                                                 'Ожидайте ответа....',
                                            parse_mode=ParseMode.HTML)
       	u = Update()
        u.karma_ = Karma(module_name='shop', recivier=update.player, sender=update.player,
                            amount=-item.price, description=f'Снятие за покупку товара {item.name}')
        self.event_manager.invoke_handler_update(u)

    def _info(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message
        id = update.command.subcommand
        if not id:
            return

        if not id.isdigit():
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text='ID должен быть числом')
        id = int(id)

        item = SPItem.get_or_none(id=id)
        if not item:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text='Такого предмета не существует.')

        text =  f'<b>Название</b>: {item.name}\n'\
                f'<b>Стоимость</b>: {item.price} ☯️\n'\
                f'<b>Описание</b>: {item.description}\n'\
                f'<b>Купить:</b> /sbuy_{item.id}'
        if item.photo_fp:
            return self.message_manager.bot.send_photo(chat_id=message.chat_id,
                                                        photo=open(item.photo_fp, 'rb'),
                                                        caption=text,
                                                        parse_mode=ParseMode.HTML)

        self.message_manager.send_message(  chat_id=message.chat_id,
                                            text=text,
                                            parse_mode=ParseMode.HTML)
    @permissions(is_admin)
    @command_handler(regexp=re.compile(r'\s*\[\s*(?P<name>.+)\s*\]\s*\[\s*(?P<price>\d+)\s*\]\s*(?P<description>[\s\S]*)'),
                     argument_miss_msg='Пришли сообщение в формате "/sp_item_create [Название] [Цена]\n Описание товара"')
    def _create_item(self, update: Update, match, *args, **kwargs):
        message = update.telegram_update.message

        name, description = match.group('name', 'description')
        price = int(match.group('price'))

        item, created = SPItem.get_or_create(name=name, price=price)
        if not created:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Товар "{name}" уже существует.')
        if message.photo:
            file = self.message_manager.bot.get_file(message.photo[-1].file_id)
            fp = f'files/shop/sp_item_photo_{item.id}.jpg'
            file.download(fp)
            item.photo_fp = fp

        item.description = description or 'Какая-то важная шняга'
        item.save()

        return self.message_manager.send_message(chat_id=message.chat_id,
                                                 text=f'Товар "{name}" помещён на прилавок.') 

    @permissions(is_admin)
    @command_handler(argument_miss_msg='Пришли сообщение в формате "/sp_item_remove Название"')
    def _remove_item(self, update: Update, *args, **kwargs):
        message = update.telegram_update.message

        name = update.command.argument

        item = SPItem.get_or_none(name=name)
        if not item:
            return self.message_manager.send_message(chat_id=message.chat_id,
                                                        text=f'Товар "{name}" не существует.')
        for process in item.process:
            process.delete_instance()
        item.delete_instance()
        return self.message_manager.send_message(chat_id=message.chat_id,
                                                 text=f'Товар "{name}" убран с прилавка.') 

    def _crm_task_edit(self, process: SPProcess):
        text = (
                f'{mention_html(process.player.telegram_user_id, process.player.nickname)} хочет купить "{process.item.name}"\n'
                f'Рейдов: <code>{process.raids21}/{process.raids21+process.loose_raids_f}</code>\n'
                f'Карма: <code>{process.karma}</code>\n'
                f'\nСтатус: <b>#{self._crm_status_text(process.status_id)}</b>\n'
                f'Исполнитель: {mention_html(process.executor.telegram_user_id, process.executor.nickname) if process.executor else "Не назначен"}\n'
                f'<code>Подана: {process.created_date.strftime("%Y-%m-%d %H:%M")}</code>\n'
                f'<code>#заявка #user_id{process.id}</code>'
            )
        if process.status_id == 0:
            markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text='Принять', callback_data=f'crm_accept_{process.id}')],
                    [InlineKeyboardButton(text='Отказать', callback_data=f'crm_refuse_{process.id}')]
                ])
        elif process.status_id == 2:
            markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text='Подтвердить', callback_data=f'crm_confirm_{process.id}')],
                    [InlineKeyboardButton(text='Вернуть', callback_data=f'crm_return_{process.id}')]
                ])
        else:
            markup = None
        if not process.message_id:
            message = self.message_manager.send_message(chat_id=settings.CRM_SHOP_CHAT_ID, reply_markup=markup,
                                                            text=text, parse_mode='HTML', is_queued=False)
            process.message_id = message.message_id
            process.save()
        else:
            self.message_manager.update_msg(chat_id=settings.CRM_SHOP_CHAT_ID, message_id=process.message_id,
                                                reply_markup=markup, text=text, parse_mode='HTML')

    def _crm_status_text(self, status_id):
        if status_id == 0:
            return 'Ожидает'
        elif status_id == 1:
            return 'Отказано'
        elif status_id == 2:
            return 'Принято'
        elif status_id == 3:
            return 'Выполнено'
        else:
            return 'Неизвестно'

    @log
    @inner_update()
    @get_player
    def _crm_accept(self, update: Update, *args, **kwargs):
        if not update.player:
            return
        id_ = self._re_crm_accept.search(update.telegram_update.callback_query.data)
        process = SPProcess.get_or_none(id=int(id_.group('user_id')))
        if not process:
            return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Такой заявки нет в базе.")
        process.status_id = 2
        process.executor = update.player
        process.save()

        self._crm_task_edit(process)
        self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Ты принял заявку, удачи тебе.")
        self.message_manager.send_message(chat_id=process.player.telegram_user.chat_id, text=   f'Заявка на покупку "{process.item.name}" принята.\n'
                                                                                                f'<i>©{mention_html(update.invoker.user_id, update.player.nickname)}</i>', parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    def _crm_refuse(self, update: Update, *args, **kwargs):
        if not update.player:
            return
        id_ = self._re_crm_refuse.search(update.telegram_update.callback_query.data)
        process = SPProcess.get_or_none(id=int(id_.group('user_id')))
        if not process:
            return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Такой заявки нет в базе.")
        process.status_id = 1
        process.executor = update.player
        process.save()

        u = Update()
        u.karma_ = Karma(module_name='shop', recivier=process.player, sender=update.player,
                            amount=process.item.price, description=f'Возврат за покупку товара {process.item.name}')
        self.event_manager.invoke_handler_update(u)

        self._crm_task_edit(process)
        self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Отклонил заявку.")
        item = process.item
        self.message_manager.send_message(chat_id=process.player.telegram_user.chat_id, text=   f'Заявка на покупку "{item.name}" отклонена.\n'
                                                                                                f'Возврат: {item.price}☯️\n'
                                                                                                f'<i>©{mention_html(update.invoker.user_id, update.player.nickname)}</i>', parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    def _crm_confirm(self, update: Update, *args, **kwargs):
        if not update.player:
            return
        id_ = self._re_crm_confirm.search(update.telegram_update.callback_query.data)
        process = SPProcess.get_or_none(id=int(id_.group('user_id')))
        if not process:
            return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Такой заявки нет в базе.")
        if process.executor != update.player:
            return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Это не твоя заявка.")
        process.status_id = 3
        process.save()

        self._crm_task_edit(process)
        self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Красавчик)")

    @log
    @inner_update()
    @get_player
    def _crm_return(self, update: Update, *args, **kwargs):
        if not update.player:
            return
        id_ = self._re_crm_return.search(update.telegram_update.callback_query.data)
        process = SPProcess.get_or_none(id=int(id_.group('user_id')))
        if not process:
            return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Такой заявки нет в базе.")
        if process.executor != update.player:
            return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Это не твоя заявка.")
        process.status_id = 0
        process.executor = None
        process.save()

        self._crm_task_edit(process)

        self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id,
                                                                    show_alert=False, text="Вернул заявку, ты лохъ.")

    def _crm_process_list(self, type_=0):
        def handler(self, update: Update, *args, **kwargs):
            if type_ == 0:
                output = ['<b>ᗒМои заявки на товарыᗕ</b>']
                model = update.player.spitems
            elif type_ == 1 and update.invoker.is_admin:
                output = ['<b>ᗒПринятые мной заявки на товарыᗕ</b>']
                model = update.player.spprocess
            elif type_ == 2 and update.invoker.is_admin:
                output = ['<b>ᗒЗаявки игроков на товарыᗕ</b>']
                model = SPProcess.select()
            else:
                return self.message_manager.send_message(chat_id=update.telegram_update.message.chat_id, text='Нет доступа.')

            now = datetime.datetime.now()

            list_ = model.order_by(SPProcess.created_date.desc()).filter(SPProcess.status_id.not_in([1, 3]))
            for process in list_:
                name = process.item.name
                name = f'<i><a href="t.me/c/{abs(settings.CRM_SHOP_CHAT_ID)-1000000000000}/{process.message_id}">{name}</a></i>' if type_ != 0 else name
                output.append(f'\t\t➤{mention_html(process.player.telegram_user_id, process.player.nickname) + " ── " if type_ != 0 else ""}{name} [{(now-process.created_date).seconds//3600}час.]')
                if type_ == 0:
                    output.append(f'\t\t\t<i>©{mention_html(process.executor.telegram_user_id, process.executor.nickname)}</i>\n')
            if len(output) == 1:
                output.append('\nА заявочек то нету....')
            self.message_manager.send_message(chat_id=update.telegram_update.message.chat_id, text='\n'.join(output), parse_mode='HTML')
        return functools.partial(handler, self)

    def _crm_update_msgs(self):
        process_ = SPProcess.select()\
                            .where(SPProcess.status_id.not_in([1, 3]))\
                            .filter((SPProcess.last_update < datetime.datetime.now() - datetime.timedelta(hours=12)))
        for process in process_:
            self.message_manager.bot.delete_message(chat_id=settings.CRM_SHOP_CHAT_ID, message_id=process.message_id)
            process.message_id = None
            process.last_update = datetime.datetime.now()
            process.save()

            self._crm_task_edit(process)