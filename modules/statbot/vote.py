import datetime
import re
from typing import List

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    CallbackQueryHandler,
    Dispatcher
)

from config import settings
from core import (
    CommandFilter,
    CommandNameFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import command_handler
from decorators.log import log
from decorators.update import inner_update
from decorators.users import get_player
from models import (
    Group,
    Player,
    Vote,
    VoteAnswer
)
from modules import BasicModule
from utils.functions import CustomInnerFilters


class VoteModule(BasicModule):  # TODO: Переработать

    module_name = 'vote'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self._re_vote_answer = re.compile(r'vote_answer_(?P<vote_id>\d+)_(?P<answer_id>\d+)$')
        self.add_handler(CallbackQueryHandler(self._vote_answer_handler, pattern=self._re_vote_answer))

        self.add_inner_handler(InnerHandler(CommandFilter('vote_create'), self._vote_create, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandFilter('vote_ls'), self._vote_ls, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandNameFilter('vremove'), self._vote_remove, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(CommandNameFilter('vstop'), self._vote_stop, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))

        super().__init__(event_manager, message_manager, dispatcher)
        self.event_manager.scheduler.add_job(self._vote_autoresults, 'interval', minutes=5)

    @log
    @inner_update()
    @get_player
    def _vote_answer_handler(self, update: Update):
        callback_query = update.telegram_update.callback_query
        message = callback_query.message

        m = self._re_vote_answer.search(callback_query.data)
        if not (m and update.player):
            return

        vote_id, answer_id = [int(x) for x in m.group('vote_id', 'answer_id')]

        vote = Vote.get_or_none(Vote.id == vote_id)
        if not vote:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False,
                text='Это не опрос'
            )
        if vote.complete:
            return self.message_manager.bot.answer_callback_query(
                callback_query_id=callback_query.id,
                show_alert=False,
                text='Опрос завершён'
            )
        vote_group = Group.get_by_name(f'Vote_{vote_id}', 'vote')
        if not vote_group:
            vote_group = Group.create(name=f'Vote_{vote_id}', type='vote', is_active=True)
        if update.player not in vote_group.members:
            vote_group.members.add(update.player)
        for answer in update.player.votes.filter(VoteAnswer.vote == vote):
            answer.voted.remove(update.player)
            group_name = f'Vote_{vote_id}_{answer.id}'
            group = Group.get_by_name(group_name, 'vote')
            if not group:
                continue

            if update.player in group.members:
                group.members.remove(update.player)

        answer = VoteAnswer.select().where((VoteAnswer.vote == vote) & (VoteAnswer.id == answer_id)).limit(1)
        if not (answer and answer.count() > 0):
            return
        answer = answer.get()
        answer.voted.add(update.player)

        group_name = f'Vote_{vote_id}_{answer.id}'
        group = Group.get_by_name(group_name, 'vote')
        if not group:
            group = Group.create(name=group_name, type='vote', is_active=True)
        group.members.add(update.player)
        group.parent = vote_group
        group.save()

        return self.message_manager.bot.answer_callback_query(
            callback_query_id=callback_query.id,
            show_alert=False,
            text='Ты проголосовал в опросе'
        )

    @command_handler(
        regexp=re.compile(
            r'(?P<group_aliase>\w+)\s+(?P<subject>.+)\s*'
            r'(?P<answers>[\s\S]+)\s*'
            r'(?P<date>\d{2}\.\d{2}\.\d{4}-\d{2}:\d{2})'
        ),
        argument_miss_msg='Пришли сообщение в формате "/vote_create Алиас Тема\n Вариант 1\nВариант 2 и т.д.\n01.01.2020-00:00"'
    )
    def _vote_create(self, update: Update, match):
        message = update.telegram_update.message
        if not update.player.liders:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')
        group_name = match.group('group_aliase')
        group = Group.get_by_name(group_name)
        if not group:
            return self.message_manager.send_message(chat_id=message.chat_id, text=f'Группы "{group_name}" не существует')
        if group not in update.player.liders:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')

        date_text = match.group('date')
        try:
            enddate = datetime.datetime.strptime(date_text, '%d.%m.%Y-%H:%M')
        except (Exception, ):
            return self.message_manager.send_message(chat_id=message.chat_id, text=f'{date_text}: Неверный формат даты. Формат: 01.01.2020-00:00')
        answers = match.group('answers').strip().split('\n')
        if not answers:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Поле для вариантов ответов пустое')
        vote = Vote.create(subject=match.group('subject').replace('\n', '\n'), invoker=update.player, enddate=enddate)
        answers_list = []
        for answer in answers:
            if not answer:
                continue
            answers_list.append(VoteAnswer.create(vote=vote, title=answer))

        self.message_manager.send_message(
            chat_id=message.chat_id, text=f'<b>Опрос #{vote.id} создан</b>\n'
                                          f'<b>Опрос завершится: {enddate}</b>\n'
                                          f'<b>Вариантов ответа:</b> {len(answers_list)} шт.\n'
                                          f'<b>Варианты:</b> {"; ".join([x.title for x in answers_list])}',
            parse_mode='HTML'
        )
        text, markup = self.get_vote_kwargs(vote, answers_list)
        for member in group.members.filter(Player.is_active):
            tg_chat = member.telegram_user.chat_id if member.telegram_user else None
            if not tg_chat:
                continue
            self.message_manager.send_message(chat_id=tg_chat, text=text, reply_markup=markup, parse_mode='HTML')

    def _vote_remove(self, update: Update):
        message = update.telegram_update.message
        vote_id = update.command.subcommand
        if not vote_id:
            return
        if not update.player.votes_invoked:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')
        if not vote_id.isdigit():
            return self.message_manager.send_message(chat_id=message.chat_id, text='ID должен быть числом')
        vote_id = int(vote_id)

        vote = Vote.get_or_none(Vote.id == vote_id)
        if not vote:
            return self.message_manager.send_message(chat_id=message.chat_id, text=f'Опроса с user_id={vote_id} не существует')
        for answer in vote.answers:
            answer.voted.clear()
            group_name = f'Vote_{vote_id}_{answer.id}'
            group = Group.get_by_name(group_name)
            if group:
                group.members.clear()
                group.liders.clear()
                group.delete_instance()
            answer.delete_instance()
        group = Group.get_by_name(f'Vote_{vote_id}', 'vote')
        if group:
            group.members.clear()
            group.liders.clear()
            group.delete_instance()
        vote.delete_instance()
        self.message_manager.send_message(chat_id=message.chat_id, text=f'Опрос с ID={vote_id} и все группы его результатов удалены.')

    def _vote_stop(self, update: Update):
        message = update.telegram_update.message
        vote_id = update.command.subcommand
        if not vote_id:
            return
        if not update.player.votes_invoked:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')
        if not vote_id.isdigit():
            return self.message_manager.send_message(chat_id=message.chat_id, text='ID должен быть числом')
        vote_id = int(vote_id)

        vote = Vote.get_or_none(Vote.id == vote_id)
        if not vote:
            return self.message_manager.send_message(chat_id=message.chat_id, text=f'Опроса с user_id={vote_id} не существует')
        vote.enddate = datetime.datetime.now()
        vote.complete = True
        vote.save()

        self.message_manager.send_message(chat_id=message.chat_id, text=f'Опрос с ID={vote_id} остановлен. Группы будут удалены, через 8 часов.')

    def _vote_ls(self, update: Update):
        message = update.telegram_update.message
        if not update.player.votes_invoked:
            return self.message_manager.send_message(chat_id=message.chat_id, text='Нет доступа')
        output = ['Список опросов:']
        for idx, vote in enumerate(update.player.votes_invoked.filter(Vote.complete == False), 1):
            output.append(f'\t\t{idx}. <b>{vote.subject}</b>')
        self.message_manager.send_message(chat_id=message.chat_id, text='\n'.join(output), parse_mode='HTML')

    def _vote_autoresults(self):
        now = datetime.datetime.now()
        stop_query = Vote.select().where((Vote.complete == False) & (Vote.enddate < now))

        for vote in stop_query:
            vote.complete = True
            vote.save()
            player = vote.invoker
            if not player:
                continue
            chat_id = player.telegram_user.chat_id if player.telegram_user else None
            if not chat_id:
                continue
            results = []
            for idx, answer in enumerate(vote.answers, 1):
                results.append(f'\t\t{idx}. <code>{answer.title}</code>\n\t\t\t- Vote_{vote.id}_{answer.id}')
            results = '\n'.join(results)
            chat_id = chat_id if vote.type == 0 else settings.GOAT_ADMIN_CHAT_ID
            self.message_manager.send_message(
                chat_id=chat_id,
                text=f'<b>Опрос #{vote.id}</b> завершился.\n'
                     f'Его тема: <b>{vote.subject}</b>\n'
                     f'\nРезультаты в группах:\n{results}\n'
                     'Группы удалятся, через 8 часов.',
                parse_mode='HTML'
            )
        remove_group_query = Vote.select().where((Vote.complete == True) & (Vote.enddate < now - datetime.timedelta(hours=8)))

        for vote in remove_group_query:
            for answer in vote.answers:
                group = Group.get_by_name(f'Vote_{vote.id}_{answer.id}', 'vote')
                if not group:
                    continue
                group.members.clear()
                group.liders.clear()
                group.delete_instance()
            group = Group.get_by_name(f'Vote_{vote.id}', 'vote')
            if not group:
                continue
            group.members.clear()
            group.liders.clear()
            group.delete_instance()

    @staticmethod
    def get_vote_kwargs(vote: Vote, answers_list: List[VoteAnswer]):
        text = f'<b>{vote.subject}</b>\n'
        markup = InlineKeyboardMarkup(
            [
                *[[InlineKeyboardButton(text=answer.title, callback_data=f'vote_answer_{vote.id}_{answer.id}')] for answer in answers_list]
            ]
        )
        return text, markup
