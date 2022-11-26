import functools
import re
import datetime

from telegram import ParseMode
from telegram.ext import Dispatcher

from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, Update

from modules import BasicModule
from models import Quest
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from decorators.users import get_players
from utils.functions import CustomInnerFilters, get_link

class QuestModule(BasicModule): #TODO: Сделать :)

    module_name = 'quest'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter('rank_ls'), self._rank_ls,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        super().__init__(event_manager, message_manager, dispatcher)

    def _update_quests(self, update: Update):
        player_quests = None # Get names handlers of active quests player (update.player)
        for quest_data in player_quests:
            handler = getattr(self, quest_data.handler, None)
            if not handler:
                self.logger.warning(f'{quest_data.handler} handler not found!')
                continue

            handler(update, quest_data)

    def _quest1_handler(self, update: Update, quest: ActiveQuest):
        quest.progress = self._calculate_progress(update.player.hp / 150)
        quest.save()

        if quest.progress < 100:
            text = (
                    f'Квест: {quest.quest.name}'
                    f'Прогресс: {self._progress_bar(quest.progress)}'
                    )
            print(text)
    
    def _quest_get(self, update: Update):
        player = update.player

        c = player.quests_active.join(Quest, on=(Quest.id == ActiveQuest.quest_id)).filter(Quest.type == 1).count()
        if c >= 4:
            return update.telegram_update.message.reply_text(f'Работодатель сомневается в тебе. У тебя итак {c} задания на плечах.')

        quest = Quest.select().where(Quest.id != player.player_quests.c.quest_id).filter(Quest.type == 1)\
                        .order_by(peewee.fn.RANDOM()).limit(1)
        if not quest.exists():
            return update.telegram_update.message.reply_text('К сожалению у Работодателя нет для тебя заданий.')

        quest = quest.get()
        self._quest_add_player(quest, player)
        return update.telegram_update.message.reply_text(f'Задание: {quest.name} получено.')


    def _quest_add_player(self, quest, player: Player):
        ActiveQuest.create(
                quest=quest,
                player=player,
                progress=0
            )

    def _calculate_progress(self, value: float):
        return int(math.ceil((value) * 100))

    def _progress_bar(self, value: int = 0):
        if value < 0:
            value = 0
        if value > 100:
            value = 100

        return ((value // 10) * '▓') + ((10 - (value // 10)) * '░')

# Quest
# - name -> str
# - description -> str
# - group_type -> int (
#         0 - Основной,
#         1 - Побочный
#     )
# - handler [ function name ]

# ActiveQuest
# - quest -> Quest
# - player -> Player
# - progress -> int