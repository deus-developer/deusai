import functools
import re
import datetime
import peewee

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CallbackQueryHandler
from config import settings
from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, CommandNameFilter, Update
from modules.statbot.karma import Karma
from modules import BasicModule
from models import ShopItem, ShopPurchase, PlayerStatHistory, Auction, AuctionMember
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_player
from utils.functions import CustomInnerFilters
from decorators.update import inner_update
from decorators.log import log
from telegram.utils.helpers import mention_html
from ww6StatBotWorld import Wasteland

class ShopModuleUpdate(BasicModule): #TODO: Ввести механизм скидок

    module_name = 'shop_update'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('shop1'), self._shop_open,
                                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(CommandNameFilter('auctionp'), self._shop_auction_buy,
                                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))

        self._re_category_slug = re.compile(r'^shop_open_(?P<slug>\w+)$')

        self._re_item_info = re.compile(r'^shop_info_(?P<user_id>\d+)$')
        self._re_auction_info = re.compile(r'^shop_auction_info_(?P<user_id>\d+)$')
        self._re_item_auctions = re.compile(r'^shop_auctions_(?P<user_id>\d+)$')
        self._re_item_buy = re.compile(r'^shop_buy_(?P<user_id>\d+)$')
        self._re_auction_exit = re.compile(r'^shop_auction_exit_(?P<user_id>\d+)$')
        
        self._re_crm_accept = re.compile(r'^crm_accept_(?P<user_id>\d+)$')
        self._re_crm_refuse = re.compile(r'^crm_refuse_(?P<user_id>\d+)$')
        self._re_crm_confirm = re.compile(r'^crm_confirm_(?P<user_id>\d+)$')
        self._re_crm_return = re.compile(r'^crm_return_(?P<user_id>\d+)$')


        self.add_handler(CallbackQueryHandler(self._shop_open_category_inline, pattern=self._re_category_slug))
        self.add_handler(CallbackQueryHandler(self._shop_info_inline, pattern=self._re_item_info))
        self.add_handler(CallbackQueryHandler(self._shop_auctions_inline, pattern=self._re_item_auctions))
        self.add_handler(CallbackQueryHandler(self._shop_buy_inline, pattern=self._re_item_buy))
        self.add_handler(CallbackQueryHandler(self._shop_auction_info_inline, pattern=self._re_auction_info))

        self.add_handler(CallbackQueryHandler(self._crm_accept, pattern=self._re_crm_accept))
        self.add_handler(CallbackQueryHandler(self._crm_refuse, pattern=self._re_crm_refuse))
        self.add_handler(CallbackQueryHandler(self._crm_confirm, pattern=self._re_crm_confirm))
        self.add_handler(CallbackQueryHandler(self._crm_return, pattern=self._re_crm_return))

        self.add_handler(CallbackQueryHandler(self._shop_open_inline, pattern=re.compile(r'^shop_openmain$')))

        super().__init__(event_manager, message_manager, dispatcher)
        self.event_manager.scheduler.add_job(self._crm_update_msgs, 'interval', minutes=5)

    @permissions(is_admin)
    def _shop_open(self, update: Update):
        text = (
                f'Привет, {mention_html(update.invoker.user_id, update.player.nickname.capitalize())}!\n'
                'Это магазин альянса Deus Ex Machina\n'
                'Выбери нужную тебе категорию товаров с помощью кнопок под сообщением.\n\n'
                'Категории:\n'
            )
        buttons = []
        for category, description, slug in Wasteland.shop_category:
            text += f'◽️<b>{category}</b>: <code>{description}</code>\n'
            buttons.append([InlineKeyboardButton(text=category, callback_data=f'shop_open_{slug}')])
        return update.telegram_update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _shop_open_inline(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')
        text = (
                f'Привет, {mention_html(update.invoker.user_id, update.player.nickname.capitalize())}!\n'
                'Это магазин альянса Deus Ex Machina\n'
                'Выбери нужную тебе категорию товаров с помощью кнопок под сообщением.\n\n'
                'Категории:\n'
            )
        buttons = []
        for category, description, slug in Wasteland.shop_category:
            text += f'◽️<b>{category}</b>: <code>{description}</code>\n'
            buttons.append([InlineKeyboardButton(text=category, callback_data=f'shop_open_{slug}')])
        if update.telegram_update.callback_query.message.date - datetime.datetime.now() > datetime.timedelta(hours=12):
            return update.telegram_update.callback_query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
        return update.telegram_update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _shop_open_category_inline(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')
        category_slug = self._re_category_slug.search(update.telegram_update.callback_query.data).group('slug')
        category_info = Wasteland.shop_category_by_slug.get(category_slug, None)
        if not category_info:
            return update.telegram_update.callback_query.answer('Такой категории товаров не существует!')

        text = (
                f'<b>ᗒ {category_info[0]} ᗕ</b>\n'
                f'<code>{category_info[1]}</code>\n\n'
            )
        items = ShopItem.select()\
                        .where(ShopItem.category == category_slug)\
                        .order_by(ShopItem.price.desc(), ShopItem.limit.desc())

        buttons = [[InlineKeyboardButton(text='🔙Список категорий', callback_data='shop_openmain')]]
        for item in items:
            text += f'◽️ {item.name} [ {item.limit if item.limit != -1 else "♾"} шт. ]\n'
            buttons.append([InlineKeyboardButton(text=item.name, callback_data=f'shop_info_{item.id}')])

        if update.telegram_update.callback_query.message.date - datetime.datetime.now() > datetime.timedelta(hours=12):
            return update.telegram_update.callback_query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
        return update.telegram_update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _shop_info_inline(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')
        item_id = int(self._re_item_info.search(update.telegram_update.callback_query.data).group('user_id'))
        item = ShopItem.get_or_none(id=item_id)

        if not item:
            return update.telegram_update.callback_query.answer('Такого товара не существует!')
        category_info = Wasteland.shop_category_by_slug.get(item.category, None)
        if not category_info:
            return update.telegram_update.callback_query.answer('Произошла ошибка.')

        text = (
                f'<b>Название:</b> {item.name}\n'
                f'<b>Стоимость:</b> <code>{item.price if item.price > 0 else "<i>ДАРОМ</i>"}☯️</code>\n'
                f'<b>Описание:</b> {item.description}'
            )
        buttons = [[InlineKeyboardButton(text=f'🔙{category_info[0]}', callback_data=f'shop_open_{item.category}')]]
        if item.is_auction:
            text += f'\n\n<code>Данный товар продаётся, через аукцион. Список открытых аукционов можно просмотреть нажав кнопку "Аукционы"</code>'
            buttons.append([InlineKeyboardButton(text='🏛Аукционы', callback_data=f'shop_auctions_{item.id}')])
        else:
            buttons.append([InlineKeyboardButton(text='🛒Купить', callback_data=f'shop_buy_{item.id}')])
        if update.telegram_update.callback_query.message.date - datetime.datetime.now() > datetime.timedelta(hours=12):
            return update.telegram_update.callback_query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
        return update.telegram_update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _shop_auctions_inline(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')
        item_id = int(self._re_item_auctions.search(update.telegram_update.callback_query.data).group('user_id'))
        item = ShopItem.get_or_none(id=item_id)

        if not item:
            return update.telegram_update.callback_query.answer('Такого товара не существует!')
        category_info = Wasteland.shop_category_by_slug.get(item.category, None)
        if not category_info:
            return update.telegram_update.callback_query.answer('Произошла ошибка.')

        if not item.is_auction:
            return update.telegram_update.callback_query.answer('Этот товар не покупается через аукцион')

        if item.limit <= 0:
            return update.telegram_update.callback_query.answer('Лимит на покупки этого товара исчерпан. Дождись следующей рейдовой недели.')

        buttons = [[InlineKeyboardButton(text=f'🔙Информация "{item.name}"', callback_data=f'shop_info_{item_id}')]]
        auctions = item.auctions.filter(Auction.status == 0)

        text = (
                f'<b>Аукционы для товара "{item.name}"</b>\n'
                f'<b>Стартовая цена:</b> <code>{item.price if item.price > 0 else "Нет цены братишка, скок хочешь предлагай"}☯️</code>\n\n'
                f'<b>Доступные лоты:</b>\n'
            )
        for auction in auctions:
            auction_data = AuctionMember.select(peewee.fn.COUNT(AuctionMember.player), peewee.fn.MAX(AuctionMember.price))\
                                        .where(AuctionMember.auction_id == auction.id)\
                                        .group_by(AuctionMember.auction_id)\
                                        .limit(1)\
                                        .tuples()
            if not auction_data:
                members = 0
                price = item.price
            else:
                members = auction_data[0][0]
                price = auction_data[0][1]

            text += (
                        f'\t\t<b>Лот #{auction.id}</b>\n'
                        f'\t\t\t◽️<b>Участников:</b> {members}\n'
                        f'\t\t\t◽️<b>Текущая цена:</b> {price}☯️\n\n'
                    )
            buttons.append([InlineKeyboardButton(text=f'Лот #{auction.id}', callback_data=f'shop_auction_info_{auction.id}')])
        update.telegram_update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _shop_auction_info_inline(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')
        auction_id = int(self._re_auction_info.search(update.telegram_update.callback_query.data).group('user_id'))
        auction = Auction.get_or_none(id=auction_id)

        if not auction:
            return update.telegram_update.callback_query.answer('Такого аукциона не существует!')
        item = auction.item
        if auction.status == 1:
            return update.telegram_update.callback_query.answer('Этот аукцион уже окончился!')

        text = (
                f'<b>Лот #{auction.id}</b> на "{item.name}"\n'
                f'<b>Участники:</b>\n'
            )
        auction_data = AuctionMember.select()\
                                    .where(AuctionMember.auction_id == auction.id)\
                                    .order_by(AuctionMember.price.desc())
        for member in auction_data:
            player = member.player
            delta = int(member.price / item.price * 100) - 100

            text += f'◽️{mention_html(player.telegram_user_id, player.nickname.capitalize())}: {member.price}☯️ ( {"+" if delta >= 0 else ""}{delta}% )\n'
        text += (
                '\n<code>Чтобы установить новую ставку или изменить прошлую используйте команду ниже</code>\n'
                f'<b>/auctionp_{auction.id} Тут ваша ставка</b>'
            )
        buttons = [[InlineKeyboardButton(text=f'🏛Все Аукционы', callback_data=f'shop_auctions_{item.id}')]]
        return update.telegram_update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

    @permissions(is_admin)
    def _shop_auction_buy(self, update: Update):
        auction_id = update.command.subcommand
        if not auction_id:
            return

        if not auction_id.isdigit():
            return update.telegram_update.message.reply_text('ID должен быть числом!')
        auction_id = int(auction_id)
        auction = Auction.get_or_none(id=auction_id)
        if not auction:
            return update.telegram_update.message.reply_text(f'Аукциона с ID={auction_id} не существует!')

        if not update.command.argument.isdigit():
            return update.telegram_update.message.reply_text('Ставка на лот должна быть числом!')
        item = auction.item

        price = int(update.command.argument)
        if price < item.price:
            return update.telegram_update.message.reply_text('Ставка на лот должна быть не меньше стартовой цены лота!')
        max_price = AuctionMember.select(peewee.fn.MAX(AuctionMember.price)).where(AuctionMember.auction_id == auction.id).limit(1).scalar()
        max_price = max_price if max_price else 0

        curret_price = int(max_price * 1.05)
        if price < curret_price:
            return update.telegram_update.message.reply_text('Ставка на лот должна быть не мешьне максимальной ставки на лот * 1.05!')

        member = auction.members.filter(AuctionMember.player_id == update.player.id).limit(1)
        member = member.get() if member.exists() else AuctionMember(auction=auction, player=player, price=0, last_update=update.date)
        karma_delta = price - member.price
        member.price = price
        member.save()
        notify_text = (
                        f'<b>Оповещение по лоту #{auction.id}</b>\n'
                        f'<i>Товар: "{item.name}"</i>\n'
                        f'<b>{mention_html(update.invoker.chat_id, update.player.nickname.capitalize())} изменил свою ставку\n'
                        f'<b>Новая ставка:</b> <code>{price}</code>☯️\n'
                    )
        markup = InlineKeyboardMarkup([
                                        [InlineKeyboardButton(text=f'ℹ️Информация по "{item.name}"', callback_data=f'shop_info_{item.id}')],
                                        [InlineKeyboardButton(text='ℹ️Информация по 🏛Аукциону', callback_data=f'shop_auction_info_{auction.id}')],
                                        [InlineKeyboardButton(text='❌Выйти из 🏛Аукциона', callback_data=f'shop_auction_exit_{auction.id}')]
                                    ])
        u = Update()
        u.karma_ = Karma(
                            module_name='shop', recivier=update.player,
                            sender=update.player, amount=-karma_delta,
                            description=f'Снятие за обновление ставки в аукционе {auction.id}')
        self.event_manager.invoke_handler_update(u)
        for member in auction.members.filter(AuctionMember.player_id != update.player.id):
            text = notify_text
            text += f'<b>Твоя ставка:</b> <code>{member.price}</code>☯️'
            self.message_manager.send_message(chat_id=member.player.telegram_user_id, text=text, reply_markup=markup, parse_mode='HTML')
        return update.telegram_update.message.reply_text(
                                                            text=f'Я обновил твою ставку по лоту #{auction.id}\n'
                                                                 f'С тебя снял {karma_delta}☯️',
                                                            reply_markup=markup)

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _shop_buy_inline(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')
        item_id = int(self._re_item_buy.search(update.telegram_update.callback_query.data).group('user_id'))
        item = ShopItem.get_or_none(id=item_id)

        if not item:
            return update.telegram_update.callback_query.answer('Такого товара не существует!')
        category_info = Wasteland.shop_category_by_slug.get(item.category, None)
        if not category_info:
            return update.telegram_update.callback_query.answer('Произошла ошибка.')

        if item.is_auction:
            return update.telegram_update.callback_query.answer('Этот товар покупается только через аукцион!')

        if item.limit <= 0:
            return update.telegram_update.callback_query.answer('Лимит на покупки этого товара исчерпан. Дождись следующей рейдовой недели.')

        if item.price > update.player.karma:
            return update.telegram_update.callback_query.answer(f'Тебе не хватает {item.price - update.player.karma} кармы')

        message = self.message_manager.bot.send_message(chat_id=settings.CRM_SHOP_CHAT_ID, text='Покупка товара.', is_queued=False)
        purchare = ShopPurchase.create(
                                        item=item,
                                        player=update.player,
                                        executor=None,
                                        status=0,
                                        price=item.price,
                                        message_id=message.message_id,
                                        chat_id=message.chat_id
                                    )
        self._crm_task_edit(purchare)
        item.limit -= 1
        item.save()
        u = Update()
        u.karma_ = Karma(
                            module_name='shop', recivier=update.player,
                            sender=update.player, amount=-item.price,
                            description=f'Снятие за покупку товара {item.name}')
        self.event_manager.invoke_handler_update(u)
        return update.telegram_update.callback_query.answer(f'Занёс твою покупку в список.')
    
    def _crm_status_text(self, status_id: int) -> str:
        if status_id == 0:
            return 'Ожидает'
        elif status_id == 1:
            return 'Принято'
        elif status_id == 2:
            return 'Выполнено'
        elif status_id == 3:
            return 'Отказано'
        
        return 'Неизвестно'

    def _crm_update_msgs(self):
        posts = []
        to_delete_message_ids = []
        to_update_posts = []

        purchares = ShopPurchase.select()\
                                .where(ShopPurchase.status.not_in([2, 3]))\
                                .filter(ShopPurchase.last_update < datetime.datetime.now() - datetime.timedelta(hours=12))

        for purchare in purchares:
            player = purchare.player
            executor = purchare.executor
            item = purchare.item
            stats = player.history_stats.filter(PlayerStatHistory.time < purchare.created_date).order_by(PlayerStatHistory.time.desc()).limit(1)
            stats = stats.get() if stats.exists() else None
            if not stats:
                continue

            text = (
                    f'{mention_html(player.telegram_user_id, player.nickname.capitalize())} хочет купить "{item.name}"\n'
                    f'<b>Рейдовые баллы:</b> <code>{stats.raid_points}</code>\n'
                    f'<b>Карма:</b> <code>{stats.karma}</code>\n\n'
                    f'<b>Статус:</b> <b>#{self._crm_status_text(purchare.status)}</b>\n'
                    f'<b>Исполнитель:</b> {mention_html(executor.telegram_user_id, executor.nickname.capitalize()) if purchare.executor else "Не назначен"}\n\n'
                    f'<b>Дата:</b> <code>{purchare.created_date}</code>\n'
                    f'#заявка #user_id{purchare.id}'
                )

            if purchare.status == 0:
                markup = InlineKeyboardMarkup([
                                                [InlineKeyboardButton(text='Принять', callback_data=f'crm_accept_{purchare.id}')],
                                                [InlineKeyboardButton(text='Отказать', callback_data=f'crm_refuse_{purchare.id}')]
                                            ])
            elif purchare.status == 1:
                markup = InlineKeyboardMarkup([
                                                [InlineKeyboardButton(text='Подтвердить', callback_data=f'crm_confirm_{purchare.id}')],
                                                [InlineKeyboardButton(text='Вернуть', callback_data=f'crm_return_{purchare.id}')]
                                            ])
            else:
                markup = None
            posts.append((purchare.id, purchare.chat_id, text, markup, item))
            to_delete_message_ids.append((purchare.message_id, purchare.chat_id))

        for message_id, chat_id in to_delete_message_ids:
            try:
                self.message_manager.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                self.logger.error(e)

        now = datetime.datetime.now()
        for purchare_id, chat_id, text, markup, item in posts:
            message = self.message_manager.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode='HTML', is_queued=False)
            to_update_posts.append(
                                    {
                                        ShopPurchase.id: purchare_id,
                                        ShopPurchase.item_id: item.id,
                                        ShopPurchase.message_id: message.message_id,
                                        ShopPurchase.chat_id: message.chat_id,
                                        ShopPurchase.last_update: now
                                    }
                                )
        ShopPurchase.insert(to_update_posts).on_conflict(
                                                            conflict_target=[ShopPurchase.id],
                                                            update={
                                                                    ShopPurchase.id: peewee.EXCLUDED.id,
                                                                    ShopPurchase.message_id: peewee.EXCLUDED.message_id,
                                                                    ShopPurchase.item_id: peewee.EXCLUDED.item_id,
                                                                    ShopPurchase.chat_id: peewee.EXCLUDED.chat_id,
                                                                    ShopPurchase.last_update: peewee.EXCLUDED.last_update
                                                            }
                                                        ).execute()

    def _crm_task_edit(self, purchare: ShopPurchase):
        player = purchare.player
        executor = purchare.executor
        stats = player.history_stats.filter(PlayerStatHistory.time < purchare.created_date).order_by(PlayerStatHistory.time.desc()).limit(1)
        stats = stats.get() if stats.exists() else None
        if not stats:
            return

        text = (
                    f'{mention_html(player.telegram_user_id, player.nickname.capitalize())} хочет купить "{purchare.item.name}"\n'
                    f'<b>Рейдовые баллы:</b> <code>{stats.raid_points}</code>\n'
                    f'<b>Карма:</b> <code>{stats.karma}</code>\n\n'
                    f'<b>Статус:</b> <b>#{self._crm_status_text(purchare.status)}</b>\n'
                    f'<b>Исполнитель:</b> {mention_html(executor.telegram_user_id, executor.nickname.capitalize()) if purchare.executor else "Не назначен"}\n\n'
                    f'<b>Дата:</b> <code>{purchare.created_date}</code>\n'
                    f'#заявка #user_id{purchare.id}'
                )

        if purchare.status == 0:
            markup = InlineKeyboardMarkup([
                                            [InlineKeyboardButton(text='Принять', callback_data=f'crm_accept_{purchare.id}')],
                                            [InlineKeyboardButton(text='Отказать', callback_data=f'crm_refuse_{purchare.id}')]
                                        ])
        elif purchare.status == 1:
            markup = InlineKeyboardMarkup([
                                            [InlineKeyboardButton(text='Подтвердить', callback_data=f'crm_confirm_{purchare.id}')],
                                            [InlineKeyboardButton(text='Вернуть', callback_data=f'crm_return_{purchare.id}')]
                                        ])
        else:
            markup = None
        now = datetime.datetime.now()
        if purchare.last_update < now - datetime.timedelta(hours=12):
            try:
                self.message_manager.bot.delete_message(chat_id=purchare.chat_id, message_id=purchare.message_id)
            except Exception as e:
                pass
            message = self.message_manager.send_message(chat_id=purchare.chat_id, reply_markup=markup,
                                                        text=text, parse_mode='HTML', is_queued=False)
            purchare.message_id = message.message_id
            purchare.last_update = now
            purchare.save()
        else:
            self.message_manager.update_msg(chat_id=purchare.chat_id, message_id=purchare.message_id,
                                            text=text, reply_markup=markup, parse_mode='HTML')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _crm_accept(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')

        purchare_id = self._re_crm_accept.search(update.telegram_update.callback_query.data)
        purchare_id = int(purchare_id.group('user_id'))
        purchare = ShopPurchase.get_or_none(id=purchare_id)
        if not purchare:
            return update.telegram_update.callback_query.answer('Такой заявки не существует!')
        purchare.status = 1
        purchare.executor = update.player
        purchare.save()
        self._crm_task_edit(purchare)
        return update.telegram_update.callback_query.answer('Ты принял заявку, удачи тебе.')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _crm_refuse(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')

        purchare_id = self._re_crm_refuse.search(update.telegram_update.callback_query.data)
        purchare_id = int(purchare_id.group('user_id'))
        purchare = ShopPurchase.get_or_none(id=purchare_id)
        if not purchare:
            return update.telegram_update.callback_query.answer('Такой заявки не существует!')

        purchare.status = 3
        purchare.executor = update.player
        purchare.save()
        self._crm_task_edit(purchare)
        item = purchare.item
        item.limit += 1
        item.save()
        update.telegram_update.callback_query.answer('Отклонил заявку.')
        u = Update()
        u.karma_ = Karma(module_name='shop', recivier=purchare.player, sender=purchare.player,
                            amount=item.price, description=f'Возврат за покупку товара {item.name}')
        self.event_manager.invoke_handler_update(u)
        return self.message_manager.send_message(
                                                    chat_id=purchare.player.telegram_user_id,
                                                    text=f'Заявка на покупку "{item.name}" отклонена.\n'
                                                         f'Возврат: {purchare.price}☯️\n'
                                                        f'<i>©{mention_html(update.invoker.user_id, update.player.nickname.capitalize())}</i>',
                                                    parse_mode='HTML'
                                                )

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _crm_confirm(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')

        purchare_id = self._re_crm_confirm.search(update.telegram_update.callback_query.data)
        purchare_id = int(purchare_id.group('user_id'))
        purchare = ShopPurchase.get_or_none(id=purchare_id)
        if not purchare:
            return update.telegram_update.callback_query.answer('Такой заявки не существует!')
        if purchare.executor != update.player:
            return update.telegram_update.callback_query.answer('Это не твоя заявка!')
        purchare.status = 2
        purchare.save()
        self._crm_task_edit(purchare)
        return update.telegram_update.callback_query.answer('Красавчик)')

    @log
    @inner_update()
    @get_player
    @permissions(is_admin)
    def _crm_return(self, update: Update):
        if not update.player:
            return update.telegram_update.callback_query.answer('Ты не зарегистрирован в DeusAI!')

        purchare_id = self._re_crm_return.search(update.telegram_update.callback_query.data)
        purchare_id = int(purchare_id.group('user_id'))
        purchare = ShopPurchase.get_or_none(id=purchare_id)
        if not purchare:
            return update.telegram_update.callback_query.answer('Такой заявки не существует!')
        if purchare.executor != update.player:
            return update.telegram_update.callback_query.answer('Это не твоя заявка!')
        purchare.status = 0
        purchare.executor = None
        purchare.save()
        self._crm_task_edit(purchare)
        return update.telegram_update.callback_query.answer('Вернул заявку, ты лохъ.')