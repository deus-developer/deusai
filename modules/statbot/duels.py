from telegram import ParseMode
from telegram.ext import Dispatcher
import telegram
from core import EventManager, MessageManager, Handler as InnerHandler, CommandFilter, Update
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from modules import BasicModule
from models import Feedback
from config import settings
from utils.functions import CustomInnerFilters, get_link
from random import randint
class DuelModule(BasicModule):

    module_name = 'duels'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
    	self.add_inner_handler(InnerHandler(CommandFilter('duel'), self._duel,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self._script = [
                            {'group_type': 'attack', 'title': 'атаковал первым', 'attack_factor': 1.1, 'defence_factor': 0.9,
                                'next': [1, 3, 5, 6] },
                            {'group_type': 'attack', 'title': 'ударил в корпус', 'attack_factor': 0.9, 'defence_factor': 1,
                                'next': [2, 3, 4, 5, 6, 7, 8, 10] },
                            {'group_type': 'attack', 'title': 'оглушил', 'attack_factor': 2, 'defence_factor': 1,
                                'next': [1, 5, 9] },
                            {'group_type': 'attack', 'title': 'использовал технику', 'attack_factor': 1.5, 'defence_factor': 1,
                                'next': [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 13] },
                            {'group_type': 'attack', 'title': 'пробил броню', 'attack_factor': 1, 'defence_factor': 0.7,
                                'next': [10, 12, 13, 1, 3, 5] },
                            {'group_type': 'attack', 'title': 'наступил на палец', 'attack_factor': 0.5, 'defence_factor': 0,
                                'next': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] },
                            {'group_type': 'attack', 'title': 'использовал навык', 'attack_factor': 1.5, 'defence_factor': 1,
                                'next': [1, 2, 5, 7, 8, 9, 10, 11, 12, 13] },
                            {'group_type': 'attack', 'title': 'зашёл с тыла', 'attack_factor': 1.1, 'defence_factor': 0,
                                'next': [1, 3, 5] },
                            {'group_type': 'defence', 'title': 'парировал удар', 'attack_factor': 0, 'defence_factor': 0,
                                'next': [1, 2, 3, 4, 5, 6, 7] },
                            {'group_type': 'defence', 'title': 'увернулся', 'attack_factor': 0, 'defence_factor': 0,
                                'next': [1, 2, 3, 4, 5, 6] },
                            {'group_type': 'defence', 'title': 'контратаковал', 'attack_factor': 0.95, 'defence_factor': 1.5,
                                'next': [1, 2, 3, 4, 5, 6, 7] },
                            {'group_type': 'defence', 'title': 'отскочил от каната', 'attack_factor': 2, 'defence_factor': 2,
                                'next': [1, 3, 5] },
                            {'group_type': 'defence', 'title': 'пробил SMASHHHH', 'attack_factor': 3, 'defence_factor': 1,
                                'next': [1] },
                            {'group_type': 'defence', 'title': 'задонатил разрабу', 'attack_factor': 2, 'defence_factor': 1.5,
                                'next': [1] },
                        ]
        super().__init__(event_manager, message_manager, dispatcher)

    @command_handler()
    @get_players(include_reply=True, break_if_no_players=False)
    def _duel(self, update: Update, players, *args, **kwargs):
        message = update.telegram_update.message
    	pl1 = update.player
        for pl2 in players:
            if pl1 == pl2:
                self.message_manager.send_message(chat_id=message.chat_id,
                                                    text='Ты не можешь устроить дуэль с самим собой!')
                continue
            pls = [(pl1, 0), (pl2, 0)]
            lines = [   f'На ринг выш{"ла" if pl1.sex == 1 else "ел"} {pl1.nickname} и о{"на баба" if pl1.sex == 1 else "н мужик"}',
                        f'На ринг выш{"ла" if pl2.sex == 1 else "ел"} {pl2.nickname} и о{"на баба" if pl2.sex == 1 else "н мужик"}',
                         '!!!!Бой начинается!!!!']
            first = randint(0, 1)
            if first == 0:
                pl = pls[0]
                pl_ = pls[1]
            else:
                pl = pls[1]
                pl_ = pls[0]
            last_attack = 0

            while pl[0].hp > 0 and pl_[0].hp > 0:
                action = self._script[pl[1]]
                if action.get('group_type', 'attack') == 'attack':
                    next_id = randint(0, len(action.get('next')-1))
                    next_action = action.get('next')[next_id]
                    if next_action.get('group_type', 'attack') == 'defence':
                        if next_action.get('attack_factor', 0) > 0:
                            pl, pl_ = pl_, pl
                        action = next_action
                    
                    attack = pl[0].attack*action.get('attack_factor', 1)/(pl_[0].defence*action.get('defence_factor', 1))*100
                    pl_[0].hp -= attack
                    lines.append(f'({pl[0].hp}) {pl[0].nickname} {action.get("title", "атаковал")} {pl_[0].nickname} [-{attack}]')
                attack = pl[0].attack*