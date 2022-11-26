from telegram.ext import Dispatcher
from telegram import ParseMode
import datetime
import re
import math
from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, Update
from decorators import command_handler, permissions
from decorators.permissions import is_admin, is_rank, or_
from decorators.users import get_players
from models import Radar, Player, Group
from modules import BasicModule
from modules.statbot.parser import GroupParseResult, PlayerParseResult
from utils.functions import CustomInnerFilters
from ww6StatBotWorld import Wasteland

STATUS_LIST = { '📍': 0, '👟': 1, '👊': 2 }
STATUS_LIST_by_id = { 0: '📍', 1: '👟', 2: '👊'}

class RadarModule(BasicModule):
    module_name = 'radar'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('gang'), self._update_from_gang))
        self.add_inner_handler(InnerHandler(UpdateFilter('profile'), self._update_km_from_profile))
        self.add_inner_handler(InnerHandler(CommandFilter('search'), self._search,
                                            [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        super().__init__(event_manager, message_manager, dispatcher)

        self._none_delta = datetime.timedelta(seconds=1)
        self._minutes_delta = datetime.timedelta(minutes=3)
        self._hour_delta = datetime.timedelta(hours=1)
        self._day_delta = datetime.timedelta(days=1)
        self._fday_delta = datetime.timedelta(days=5)
        self._re_groups = re.compile(r'[\s\S]*(\"|\')(?P<group>.+)(\"|\')[\s\S]*')

    @permissions(is_admin)
    @command_handler()
    def _search(self, update: Update, *args, **kwargs):
        names = update.command.argument.split()
        groups = [f.group('group') for f in self._re_groups.finditer(update.command.argument)]
        kms = []
        for i in names:
            if i.isdigit():
                kms.append(int(i))
        
        if groups:
            names.extend(groups)
        enemys = Player.select().where((Player.nickname << names))
        groups = Group.select().where((Group.name << names) | (Group.alias << names))
        players = []
        for enemy in enemys:
            if enemy not in players:
                players.append(enemy)
        for group in groups:
            for member in group.members:
                if member not in players:
                    players.append(member)
        self._output_view(update=update, players=players)

    def _view_handler(self, update: PlayerParseResult):
        message = update.telegram_update.message
        view = update.view
        nicknames = [pl.nickname.strip() for pl in view.players]
        codes = []
        players = []
        if not nicknames:
            return

        for idx, nickname in enumerate(nicknames):
            player = Player.get_by_nickname(nickname=nickname)
            if player and player.last_update > update.date:
                continue

            if not player:
                player = Player.create(nickname=nickname, last_update=update.date)

            g = player.goat
            if g and g.is_active:
                continue
            g = player.gang
            if g and g.is_active:
                continue

            radar = player.radars.order_by(Radar.time.desc()).limit(1)
            if not radar or radar[0].time < update.date:
                Radar.create(player=player, time=update.date, km=view.km, status=0)
            players.append(player)
            codes.append(view.players[idx].u_command)

        self._output_view(update=update, players=players, codes=codes)

    def _output_view(self, update: PlayerParseResult, players, codes=None):
        message = update.telegram_update.message
        now = datetime.datetime.now()
        info_ = {}
        missed = []

        for idx, player in enumerate(players):        
            if not player.gang:
                missed.append((player, codes[idx] if codes else None))
                continue
            goat = player.goat.name if player.goat else '[Без козла]'
            gang = player.gang.name if player.gang else '[Без банды]'
            goat_ = info_.get(goat, {})
            gang_ = goat_.get(gang, [])
            if not gang_:
                gang_ = []
            gang_.append(player)
            goat_.update({gang: gang_})
            info_.update({goat: goat_})

        output_ = []
        for goat, gangs in info_.items():
            output_.append(f'🐐<b>{goat}</b>')
            for gang, players in gangs.items():
                output_.append(f'  <i>{gang}</i>')
                sorted_players = sorted(players, key=lambda x: x.km, reverse=True)
                output_players = []
                for player in sorted_players:
                    output_players.append(self._prepare_output(player, self._delta(now-player.last_update)))
                output_.extend(output_players)
        if output_:
            self.message_manager.send_split(chat_id = message.chat_id, msg='\n'.join(output_), n=63)
        
        if not missed:
            return

        output_ = ['⚠<b>Пришли мне аватары этих игроков</b>⚠:']  
        for player, command in missed:
            output_.append(self._prepare_output(player, self._delta(now-player.last_update), command=f'/u_{command}'))
        self.message_manager.send_split(chat_id = message.chat_id, msg='\n'.join(output_), n=63)
        
    @staticmethod
    def _update_from_gang(update: GroupParseResult):
        goat = (Group.get_by_name(update.gang.goat.name, group_type='goat') or Group.create(name=update.gang.goat.name, type='goat')) if update.gang.goat else None
        gang = Group.get_by_name(update.gang.name, group_type='gang') or Group.create(name=update.gang.name, type='gang')
        
        for gangster in update.gang.players:
            player, created = Player.get_or_create(nickname=gangster.nickname)

            if not created and player.last_update > update.date:
                continue
            
            if goat:
                player.goat = goat
            else:
                player.goat.remove(player)
            player.gang = gang
            player.last_update = update.date
            player.save()
            radar = player.radars.order_by(Radar.time.desc()).limit(1)
            if not radar or radar[0].time < update.date:
                status = STATUS_LIST.get(gangster.status, 0)
                Radar.create(player=player, time=update.date, km=gangster.distance, status = status)

    @staticmethod
    def _update_km_from_profile(update: PlayerParseResult):
        player = update.player
        if not player or player.last_update > update.date:
            return
        message = update.telegram_update.message
        status = 2 if update.profile.on_raid else 0
        radar = player.radars.order_by(Radar.time.desc()).limit(1)
        if not radar or radar[0].time < update.date:
            Radar.create(player=player, time=update.date, km=update.profile.distance, status = status)

    def _delta(self, delta):
        if delta <= self._hour_delta:
            delta_ = f'{delta.seconds//60} мин.'
        elif delta <= self._day_delta:
            delta_ = f'{delta.seconds//3600} час.'
        else:
            delta_ = f'{delta.days} дн.'
        return delta_

    def _prepare_output(self, player, delta, command=None):
        sum_stats = player.sum_stat
        regen_l = player.regeneration_l
        if sum_stats != 0 and regen_l != 0:
            t_line = f'    ├📯БМ: {sum_stats} ❣️{regen_l} ур. \n'
        elif sum_stats != 0:
            t_line = f'    ├📯БМ: {sum_stats}\n'
        elif regen_l != 0:
            t_line = f'    ├❣️{regen_l} ур. \n'
        else:
            t_line = ''
        hp = player.hp
        attack = player.attack or self._attack_from_power(player.power)
        if hp != 0 and attack != 0:
            e_line = f'    └❤️{hp} 💥{attack} ⏱{delta}'
        elif hp != 0:
            e_line = f'    └❤️{hp} ⏱{delta}'
        elif attack != 0:
            e_line = f'    └💥{attack} ⏱{delta}'
        else:
            e_line = f'    └⏱{delta}'
        nickname = f'<a href="tg://share/url?text={command}">{player.nickname}</a>' if command else player.nickname
        return  f'    ┌<b>{nickname}[{player.km} км]</b>\n'\
                f'{t_line}'\
                f'{e_line}'
                
    def _attack_from_power(self, power: int = 0):
        if power < 250:
            return 0
        if power < 2100:
            return int(math.ceil(((1.14+(power//50-5)*0.2)*416)*0.75))

        return int(math.ceil(((1.81+((power-2100)//100)*0.7)*507)*0.75))