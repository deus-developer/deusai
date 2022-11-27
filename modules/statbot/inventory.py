import datetime
import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    CallbackQueryHandler,
    Dispatcher
)
from telegram.utils.helpers import mention_html

from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update as InnerUpdate,
    UpdateFilter
)
from decorators import (
    command_handler,
    permissions
)
from decorators.log import log
from decorators.permissions import (
    is_admin,
    is_developer,
    or_,
    self_
)
from decorators.update import inner_update
from decorators.users import get_player
from decorators.users import get_players
from models import (
    InventoryItem,
    Item,
    Player
)
from modules import BasicModule
from utils.functions import CustomInnerFilters
from ww6StatBotWorld import Wasteland


class InventoryModule(BasicModule):  # TODO: ДОВЕСТИ ДО КОНЦА, НАВЕРНОЕ ПОЛНОСТЬЮ ПЕРЕРАБОТАТЬ
    module_name = 'inventory'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('inventory'), self._inventory,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('inventory_add_item'), self._inventory_add_item,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        self.add_inner_handler(InnerHandler(UpdateFilter('stock'), self._ww_inventory_handler))

        self._re_player_inventory = re.compile(r'^show_inventory_(?P<player_id>\d+)_(?P<category>\w+)$')

        self.add_handler(CallbackQueryHandler(self._show_player_inventory_inline, pattern=self._re_player_inventory))
        super().__init__(event_manager, message_manager, dispatcher)

    @get_players(include_reply=True, break_if_no_players=False, callback_message=True)
    @permissions(or_(is_admin, self_))
    def _inventory(self, update: InnerUpdate, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        players_list = players or ([update.player] if update.command.argument == '' else [])
        if not players_list:
            return
        for player in players_list:
            self._show_player_inventory(player, chat_id, update.invoker.is_admin)

    def _show_player_inventory(self, player: Player, chat_id, editable=False):
        formatted_report = '<b>🎒Инвентарь</b>' if not editable else f'<b>🎒Инвентарь</b> игрока {mention_html(player.telegram_user_id, player.nickname)}'
        category, label = Wasteland.inventory_types[0]
        formatted_report += f'\n\n▪️<b>{label}</b>\n'

        items = InventoryItem.select() \
            .join(Item, on=(InventoryItem.item_id == Item.id)) \
            .where((InventoryItem.owner == player) & (Item.type == category)) \
            .order_by(InventoryItem.amount.desc())
        if not items:
            formatted_report += '\t\t\t\t\t\t<code>ТУТ ПУСТА</code>'
            return self.message_manager.send_message(
                chat_id=chat_id,
                text=formatted_report,
                parse_mode='HTML',
            )
        for item in items:
            formatted_report += f'\t▫️{item.item.name} x{item.amount}\n' if item.amount != 1 else f'\t▫️{item.item.name}\n'
        buttons = []
        for category, label in Wasteland.inventory_types[1:]:
            buttons.append(InlineKeyboardButton(text=label, callback_data=f'show_inventory_{player.id}_{category}'))

        buttons = [buttons[x:min(x + 3, len(buttons))] for x in range(0, len(buttons), 3)]

        self.message_manager.send_message(
            chat_id=chat_id,
            text=formatted_report,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML',
        )

    @log
    @inner_update()
    @get_player
    def _show_player_inventory_inline(self, update: InnerUpdate, *args, **kwargs):
        if not update.player:
            return
        match = self._re_player_inventory.search(update.telegram_update.callback_query.data)
        player_id, category = match.group('player_id', 'category')
        player = Player.get_or_none(id=int(player_id))
        if not player:
            return update.telegram_update.callback_query.answer('Пользователя не существует')
        editable = player.id == update.player.id
        label = None
        buttons = []
        for c, l in Wasteland.inventory_types:
            if c == category:
                label = l
                continue
            buttons.append(InlineKeyboardButton(text=l, callback_data=f'show_inventory_{player.id}_{c}'))
        buttons = [buttons[x:min(x + 3, len(buttons))] for x in range(0, len(buttons), 3)]

        if label is None:
            return update.telegram_update.callback_query.answer('Такой категории не существует')

        formatted_report = '<b>🎒Инвентарь</b>' if not editable else f'<b>🎒Инвентарь</b> игрока {mention_html(player.telegram_user_id, player.nickname)}'
        formatted_report += f'\n\n▪️<b>{label}</b>\n'

        items = InventoryItem.select() \
            .join(Item, on=(InventoryItem.item_id == Item.id)) \
            .where((InventoryItem.owner == player) & (Item.type == category)) \
            .order_by(InventoryItem.amount.desc())
        if not items:
            formatted_report += '\t\t\t\t\t\t<code>ТУТ ПУСТА</code>'
            if update.telegram_update.callback_query.message.date - datetime.datetime.now() > datetime.timedelta(hours=12):
                return update.telegram_update.callback_query.message.reply_text(text=formatted_report, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
            return update.telegram_update.callback_query.edit_message_text(text=formatted_report, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

        for item in items:
            formatted_report += f'\t▫️{item.item.name} x{item.amount}\n' if item.amount != 1 else f'\t▫️{item.item.name}\n'

        if update.telegram_update.callback_query.message.date - datetime.datetime.now() > datetime.timedelta(hours=12):
            return update.telegram_update.callback_query.message.reply_text(text=formatted_report, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
        return update.telegram_update.callback_query.edit_message_text(text=formatted_report, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @permissions(is_developer)
    @command_handler(
        regexp=re.compile(r'\s*(?P<user_id>\d+)\s+(?P<amount>\d+).*'),
        argument_miss_msg='Пришли сообщение в формате "/inventory_add_item d+(ID предмета) @user1, @user2"'
    )
    @get_players(include_reply=True, break_if_no_players=True)
    def _inventory_add_item(self, update: InnerUpdate, match, players: list, *args, **kwargs):
        message = update.telegram_update.message
        chat_id = message.chat_id
        item_id = int(match.group('user_id'))
        amount = int(match.group('amount'))

        item = Item.get_or_none(Item.id == item_id)
        if not item:
            return self.message_manager.send_message(chat_id=message.chat_id, text=f'Предмета с ID={item_id} не существует.')

        pls = []
        users = []
        for player in players:
            in_inventory, created = InventoryItem.get_by_item(item=item, player=player)
            in_inventory.amount += amount
            in_inventory.last_update = update.date
            in_inventory.save()
            pls.append(player.nickname)
            users.append(player.telegram_user_id)
        for user in users:
            self.message_manager.send_message(chat_id=user, text=f'С небес на тебя упал ящик.....\nВнутри него ты обнаружил {item.name} x{amount}')
        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=f'Выдал "{item.name}" игрокам: {"; ".join(pls)}'
        )

    def _ww_inventory_handler(self, update: InnerUpdate):
        delta = datetime.datetime.now() - datetime.timedelta(seconds=10)
        if update.player.last_update < delta:
            return
        if update.date < delta:
            return
        if update.player.last_update + datetime.timedelta(seconds=10) < update.date:
            return

        for stock_item in update.stock:
            item = Item.get_or_none(name=stock_item.name)
            created = False if item else True

            if not item:
                item = Item.create(name=stock_item.name, type=stock_item.category)

            in_inventory, created = InventoryItem.get_by_item(item=item, player=update.player)
            if not created and in_inventory.last_update > update.date:
                continue
            in_inventory.amount = stock_item.amount
            in_inventory.last_update = update.date
            in_inventory.save()
        self.message_manager.send_message(chat_id=update.telegram_update.message.chat_id, text='Обновил твой 🎒Инвентарь.\nОткрыть: /inventory')
