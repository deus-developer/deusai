import re
import datetime
import json

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from config import settings
from core import EventManager, MessageManager, Handler as InnerHandler, CommandFilter, CommandNameFilter, UpdateFilter, Update

from ww6StatBotWorld import Wasteland
from modules import BasicModule
from models import Group, Taking, TakingStatus, Player
from utils.functions import CustomInnerFilters, get_link

from decorators import command_handler, permissions
from decorators.permissions import is_admin, is_lider, or_
from decorators.users import get_player
from decorators.update import inner_update
from decorators.log import log

class TakingModule(BasicModule): #TODO: Доработать
	module_name = 'taking'

	def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
		self.add_inner_handler(InnerHandler(CommandFilter('taking'), self._taking_create, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
		self.add_inner_handler(InnerHandler(CommandNameFilter('untaking'), self._taking_remove, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))

		self.add_inner_handler(InnerHandler(UpdateFilter('taking'), self._taking_handler))
		self.add_inner_handler(InnerHandler(UpdateFilter('taking_fail'), self._taking_fail))
		self.add_inner_handler(InnerHandler(UpdateFilter('taking_success'), self._taking_success))

		self.add_handler(CallbackQueryHandler(callback=self._taking_accept, pattern=re.compile(r'taking_accept')))
		self.add_handler(CallbackQueryHandler(callback=self._taking_refuse, pattern=re.compile(r'taking_refuse')))
		super().__init__(event_manager, message_manager, dispatcher)
		self.event_manager.scheduler.add_job(self._update_takings, 'interval', minutes=1)

		# Таймер на 1 минуту, чтобы проверять по радару км всех игроков на активных км

	def _taking_handler(self, update: Update):
		taking_data = update.taking
		group = Group.get_by_name(taking_data.gang, 'gang')
		if not group:
			return
		taking = Taking.select().where((Taking.reported == False) & (Taking.group == group) & (Taking.km == taking_data.km)).limit(1)

		if taking.count() == 0:
			return
		taking = taking.get()
		if update.date < taking.last_update:
			return

		for status in taking.statuses.filter(TakingStatus.status_id == 2):
			status.delete_instance()

		for player_ in taking_data.players:
			pl = Player.get_by_nickname(player_.nickname)
			if not pl:
				continue
			status = TakingStatus.create(taking=taking, player=pl, status_id=2)

		taking.last_update = update.date
		taking.save()
		self._update_takings()

	def _taking_success(self, update: Update):
		taking_data = update.taking_success
		group = Group.get_by_name(taking_data.gang_name, 'gang')	
		if not group:
			return

		km = Wasteland.take_locations_km_by_shortname.get(taking_data.location_name, None)
		if not km:
			return

		taking = Taking.select().where((Taking.reported == False) & (Taking.group == group) & (Taking.km == km)).limit(1)
		
		if taking.count() == 0:
			return
		taking = taking.get()

		taking.reported = True

		self.message_manager.send_message(	chat_id=taking.chat_id,
											text=f'Поздравим ударную групппу <b>{taking.group.name}</b> с захватом <i>{Wasteland.take_locations_by_km.get(km, ["[подземелье]"])[0]}</i>',
											parse_mode='HTML'
										)
		taking.last_update = update.date
		taking.save()
		kwargs = {'chat_id': taking.chat_id, 'message_id': taking.message_id}
		if not kwargs['message_id']:
			return
		self.message_manager.bot.delete_message(**kwargs)

	def _taking_fail(self, taking: Update):
		pass

	@log
	@inner_update()
	@get_player
	def _taking_accept(self, update: Update):
		message = update.telegram_update.callback_query.message
		taking = Taking.select().where((Taking.chat_id == message.chat_id) & (Taking.message_id == message.message_id)).limit(1)
		if taking.count() == 0:
			return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id, show_alert=False, text='Это не захват')
		taking = taking.get()
		if update.player not in taking.group.members:
			return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id, show_alert=False, text='Ты не состоишь в этой ударной группе')
		
		status = TakingStatus.select().where((TakingStatus.taking == taking) & (TakingStatus.player == update.player)).limit(1)
		if status.count() == 1:
			status = status.get()
		else:
			status = TakingStatus.create(taking=taking, player=update.player, status_id=1)
		status.status_id = 1
		status.save()
		self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id, show_alert=False, text='Молодец, ты участвуешь в захвате.')
		self._update_takings()

	@log
	@inner_update()
	@get_player
	def _taking_refuse(self, update: Update):
		message = update.telegram_update.callback_query.message
		taking = Taking.select().where((Taking.chat_id == message.chat_id) & (Taking.message_id == message.message_id)).limit(1)
		if taking.count() == 0:
			return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id, show_alert=False, text='Это не захват')
		taking = taking.get()
		if update.player not in taking.group.members:
			return self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id, show_alert=False, text='Ты не состоишь в этой ударной группе')
		
		status = TakingStatus.select().where((TakingStatus.taking == taking) & (TakingStatus.player == update.player)).limit(1)
		if status.count() == 1:
			status = status.get()
		else:
			status = TakingStatus.create(taking=taking, player=update.player, status_id=0)
		status.status_id = 0
		status.save()
		self.message_manager.bot.answer_callback_query(callback_query_id=update.telegram_update.callback_query.id, show_alert=False, text='Молодец, ты участвуешь в захвате.')
		self._update_takings()

	def _taking_remove(self, update: Update):
		message = update.telegram_update.message
		if not (update.player.takings_invoke.filter(Taking.reported == False).count() > 0 or update.invoker.is_admin):
			return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа.')
		reply = message.reply_to_message.message_id if message.reply_to_message else None
		subcommand = int(update.command.subcommand) if (update.command.subcommand and update.command.subcommand.isdigit()) else None

		taking = None
		if reply:
			taking = Taking.select().where((Taking.chat_id == message.chat_id) & (Taking.message_id == reply)).limit(1)

		if subcommand:
			taking = Taking.select().where(Taking.id == subcommand).limit(1)

		if not taking:
			return self.message_manager.send_message(chat_id=message.chat_id, text='Такого захвата не существует.')

		taking = taking.get()
		if not (taking.invoker == update.invoker or update.invoker.is_admin):
			return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа.')

		if taking.reported:
			return

		taking.reported = True
		taking.save()
		kwargs = {'chat_id': taking.chat_id, 'message_id': taking.message_id}
		if not kwargs['message_id']:
			return
		self.message_manager.bot.delete_message(**kwargs)

	@command_handler(	regexp=re.compile(r'(?P<group>.+)\s+(?P<km>\d+)'),
						argument_miss_msg='Пришлите сообщение в формате "/taking группа-банды(string) км(int)"')
	def _taking_create(self, update: Update, match, *args, **kwargs):
		message = update.telegram_update.message
		group_name = match.group('group')
		km = int(match.group('km'))
		if update.player.liders.count() == 0:
			return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа.')
		group = Group.get_by_name(group_name, 'gang')
		if not group:
			return self.message_manager.send_message(chat_id=message.chat_id, text='Такой банды не существует.')
		if not (update.invoker.is_admin or group in update.player.liders):
			return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа.')

		if km not in Wasteland.take_kms:
			return self.message_manager.send_message(chat_id=message.chat_id, text=f'{km}км не является подземельем.')

		taking = Taking.select().where((Taking.group == group) & (Taking.km == km) & (Taking.reported == False)).limit(1)
		if taking.count() > 0:
			taking = taking.get()
			return self.message_manager.send_message(chat_id=message.chat_id, text=f'Захват "{Wasteland.take_locations_by_km.get(km, ["[подземелье]"])[0]}" уже начат группой "{group.name}".\n'
																					f'Отменить захват: /untaking_{taking.id}')

		taking = Taking.create(group=group, km=km, chat_id=message.chat_id, invoker=update.player)
		self._update_takings()

	def _update_takings(self):
		takings = Taking.select().where(Taking.reported == False)
		delta = datetime.datetime.now() - datetime.timedelta(hours=10)
		for taking in takings.filter(Taking.created_date > delta):
			text = self._taking_text(taking)
			kwargs = {'chat_id': taking.chat_id, 'message_id': taking.message_id}
			markup = InlineKeyboardMarkup([
											[InlineKeyboardButton(text='Принимаю!', callback_data=f'taking_accept')],
											[InlineKeyboardButton(text='Отказываюсь!', callback_data=f'taking_refuse')]
										])
			if kwargs['message_id']:
				self.message_manager.update_msg(**kwargs, reply_markup=markup, text=text, parse_mode='HTML')
			else:
				message = self.message_manager.send_message(**kwargs, reply_markup=markup, text=text, parse_mode='HTML', is_queued=False)
				taking.message_id = message.message_id
				taking.save()
		for taking in takings.filter(Taking.created_date < delta):
			taking.reported = True
			taking.save()
			kwargs = {'chat_id': taking.chat_id, 'message_id': taking.message_id}
			if not kwargs['message_id']:
				continue
			self.message_manager.bot.delete_message(**kwargs)

	def _taking_text(self, taking: Taking):
		location = Wasteland.take_locations_by_km.get(taking.km, ["[подземелье]", 0])
		players = taking.statuses
	
		confirmed = players.filter(TakingStatus.status_id == 2)
		en_route = players.filter(TakingStatus.status_id == 1)
		refused = players.filter(TakingStatus.status_id == 0)
		
		text = (
				f'<b>Захват</b> <u>{location[0]}</u>\n'
				f'<i>Ударная группа:</i> <b>{taking.group.name}</b>\n'
			)

		if confirmed:
			text += (
					f'<i>Подтвердили участие {confirmed.count()} из {location[1]} требуемых:</i> {"; ".join([x.player.nickname for x in confirmed])}\n'
				)
		else:
			text += (
					f'<i>Подтвердили участие:</i> Нет таких\n'
				)

		def en_route_formatter(player):
			return f'{player.nickname}[{player.km}км]'
		if en_route:
			text += (
					f'<i>В пути {en_route.count()}ч:</i> {"; ".join([en_route_formatter(x.player) for x in en_route])}\n'
				)
		else:
			text += (
					f'<i>В пути:</i> Нет таких\n'
				)

		if refused:
			text += (
					f'<i>Отказались {refused.count()}ч:</i> {"; ".join([x.player.nickname for x in refused])}\n'
				)
		else:
			text += (
					f'<i>Отказались:</i> Нет таких\n'
				)
		return text

# TakingStatus -> status:
# 	0. Отказались
# 	1. В пути
# 	2. Подтвердили