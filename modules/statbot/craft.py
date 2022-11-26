import telegram
from telegram.ext import Dispatcher

from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, Update
from modules import BasicModule
from utils.functions import CustomInnerFilters
from models import Craft, Item

class CraftModule(BasicModule):
    """
    craft handler
    """
    module_name = 'craft'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('craft'), self._craft))
        self.add_inner_handler(InnerHandler(CommandFilter('uncraft'), self._uncraft))

        self.add_inner_handler(InnerHandler(UpdateFilter('craft'), self._craft_update))
        self.add_inner_handler(InnerHandler(UpdateFilter('inventory'), self._inventory_update))
        super().__init__(event_manager, message_manager, dispatcher)

    def _craft(self, update: Update):
        message = update.telegram_update.message
        craft = update.invoker.craft_works.filter(Craft.verified == False).order_by(Craft.last_update.desc()).limit(1)
        if not craft:
            craft = Craft.select().where((Craft.verified == False) & (Craft.executor is None)).order_by(Craft.last_update.desc()).limit(1)

        if not craft:
            return self.message_manager.send_message(chat_id=message.chat_id, text='У меня нет для тебя крафта.')
        craft = craft.get()
        craft.executor = update.invoker
        craft.save()

        output_items = "\n".join([f'<code>/bench_{item.item.item_id}_{item.amount}</code>' for item in craft.items])

        output = (
                f'<b>У меня есть для тебя крафт ({len(output_items)})</b>\n'
                f'{output_items}\n'
                f'Отказаться от крафта: /uncraft\n'
                f'<code>У тебя есть 5 минут не его выполнение!</code>'
            )
        return self.message_manager.send_message(chat_id=message.chat_id, text=output, parse_mode='HTML')

    def _uncraft(self, update: Update):
        message = update.telegram_update.message
        craft = update.invoker.craft_works.filter(Craft.verified == False).order_by(Craft.last_update.desc()).limit(1)
        if not craft:
            return self.message_manager.send_message(chat_id=message.chat_id, text='У тебя нет активного крафта.\nВзять крафт: /craft')

        craft = craft.get()
        craft.executor = None
        craft.save()

        return self.message_manager.send_message(chat_id=message.chat_id, text='Ты отказался от крафта.')


    def _craft_update(self, update: Update):
        message = update.telegram_update.message
        craft_ = update.craft
        craft = update.invoker.craft_works.filter(Craft.verified == False).order_by(Craft.last_update.desc()).limit(1)
        if not craft:
            return self.message_manager.send_message(chat_id=message.chat_id, text='У тебя нет активного крафта.\nВзять крафт: /craft')
        craft = craft.get()

        if not craft_.result:
            craft.verified = True
            craft.save()
            self.message_manager.send_message(chat_id=message.chat_id, text='Ты молодец, что постарался!')

        item = craft_.item
        item, created = Item.get_or_create(name=item.name)
        if not created:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Крафт этого предмета уже найден. Ты меня обманываешь.')
        craft.verified = True
        craft.result = item
        craft.save()

        self.message_manager.send_message(chat_id=message.chat_id, text=f'Молодец, ты нашёл крафт "{item.name}"!\n Просто грац')

        output_items = "\n".join([f'<code>/bench_{item.item.item_id}_{item.amount}</code>' for item in craft.items])

        output = (
                f'<b>У меня есть для вас крафт "{item.name}"</b>\n'
                f'{output_items}\n'
                f'Его нашёл: {update.invoker.get_link()}. Похлопаем ему!'
            )

        self.message_manager.send_message(chat_id=settings.NII_CHAT_ID, text=output, parse_mode='HTML')

    def _inventory_update(self, update: Update):
        message = update.telegram_update.message
        items = update.inventory.items
        if not items:
            return

        inventory = update.invoker.inventory
        for item in items:
            item_, created = Item.get_or_create(name=item.name, item_id=item.id, benchable=item.benchable)
            item__ = inventory.get_or_none(item=item_)
            if not item__:
                InventoryItem(telegram_user=update.invoker, item=item_, amount=item.amount)
        return self.message_manager.send_message(chat_id=message.chat_id, text='Запомнил ресурсы!')