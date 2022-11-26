import re
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CallbackQueryHandler
from config import settings
from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, Update
from models import Player, Boss
from modules import BasicModule
from utils.functions import CustomInnerFilters
from decorators.update import inner_update
from decorators.users import get_player

class BossModule(BasicModule):
    """
    message sending
    """
    module_name = 'boss'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('boss_spawn'), self._boss_spawned, []))
        self.add_inner_handler(InnerHandler(CommandFilter('bosses'), self._bosse_ls,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))

        self._re_boss_event = re.compile(r'^boss_(?P<event>(subscribe|unsubscribe))_(?P<boss_id>\d+)_(?P<group_type>\d+)$')
        self.add_handler(CallbackQueryHandler(self._boss_inline_event, pattern=self._re_boss_event))

        super().__init__(event_manager, message_manager, dispatcher)

    @inner_update()
    @get_player
    def _boss_inline_event(self, update: Update):
        boss_event = self._re_boss_event.search(update.telegram_update.callback_query.data)
        boss = Boss.get_or_none(id=int(boss_event.group('boss_id')))
        if not boss:
            return update.telegram_update.callback_query.answer('Такого Босса не существует!')
        subscribe = boss_event.group('event') == 'subscribe'

        subscribed = boss in update.player.boss_subscribes
        update_type = int(boss_event.group('group_type'))
        if subscribed == subscribe:
            return update.telegram_update.callback_query.answer(f'Ты уже {"подписан" if subscribe else "отписан"} от этого Босса!')

        if subscribe:
            update.player.boss_subscribes.add(boss)
        else:
            update.player.boss_subscribes.remove(boss)

        if update_type == 0:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                                                                    text=f'Отписаться' if subscribe else 'Подписаться',
                                                                    callback_data=f'boss_{"un" if subscribe else ""}subscribe_{boss.id}_0')]])
        elif update_type == 1:
            subscribers_id = [x.id for x in update.player.boss_subscribes]
            buttons = []
            for boss in Boss.select().order_by(Boss.hp.desc()):
                icon = '➕' if boss.id in subscribers_id else ' '
                km_range = f'[{boss.start_km:02}км..{boss.last_km:02}км]'
                event = 'unsubscribe' if boss.id in subscribers_id else 'subscribe'

                buttons.append([InlineKeyboardButton(text=f'{icon}{boss.name}{km_range}', callback_data=f'boss_{event}_{boss.id}_1')])
            markup = InlineKeyboardMarkup(buttons)
        else:
            markup = None
        update.telegram_update.callback_query.edit_message_reply_markup(reply_markup=markup)
        update.telegram_update.callback_query.answer('Готово!')

    def _bosse_ls(self, update: Update):
        text = 'Тут ты можешь подписаться на автооповещение о спавне нужного тебе Босса!\nПопробуй, это очень удобно.'
        buttons = []

        subscribers_id = [x.id for x in update.player.boss_subscribes]
        for boss in Boss.select().order_by(Boss.hp.desc()):
            icon = '➕' if boss.id in subscribers_id else ' '
            km_range = f'[{boss.start_km:02}км..{boss.last_km:02}км]'
            event = 'unsubscribe' if boss.id in subscribers_id else 'subscribe'

            buttons.append([InlineKeyboardButton(text=f'{icon}{boss.name}{km_range}', callback_data=f'boss_{event}_{boss.id}_1')])
        markup = InlineKeyboardMarkup(buttons)
        update.telegram_update.message.reply_text(text=text, reply_markup=markup)

    def _boss_spawned(self, update: Update):
        boss_name = update.boss_spawn.boss_name
        boss = Boss.get_or_none(name=boss_name)
        if not boss:
            return self.message_manager.send_message(chat_id=settings.ADMIN_CHAT_ID, text=f'Босса "{boss_name}" нет в базе!!!')
        text = (
                f'Босс <b>{boss.name}</b> появился в Пустоши.\n'
                f'<b>❤️Здоровье:</b> <code>{boss.hp}</code>\n'
                f'\n<code>Искать в диапазоне от 👣{boss.start_km:02}км до 👣{boss.last_km:02}км</code>'
            )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=f'Отписаться', callback_data=f'boss_unsubscribe_{boss.id}_0')]])
        for player in boss.subscribers:
            self.message_manager.send_message(
                    chat_id=player.telegram_user_id,
                    text=text,
                    reply_markup=markup,
                    parse_mode='HTML'
                )