import datetime
import re
from typing import List

import telegram
from telegram.ext import (
    Dispatcher,
    MessageHandler
)
from telegram.ext.filters import Filters

from config import settings
from core import (
    EventManager,
    MessageManager,
    Update as InnerUpdate
)
from decorators.update import inner_update
from decorators.users import get_player
from modules import BasicModule
from utils.functions import (
    CustomFilters,
    clearEmoji
)
from ww6StatBotWorld import Wasteland


# TODO: Провести тесты всего этого добра

class PlayerStat:
    def __init__(self):
        self.hp = None
        self.stamina = None
        self.agility = None
        self.oratory = None
        self.accuracy = None
        self.power = None
        self.attack = None
        self.defence = None
        self.dzen = None


class Notebook:
    def __init__(self):
        self.attrs = []


class Profile:
    def __init__(self, match=None, id_match=None, dzen_match=None, dzen_bars_match=None):
        self.nickname = None
        self.fraction = None
        self.crew = None
        self.stats = None
        self.hp_now = None
        self.stamina_now = None
        self.hunger = None
        self.distance = None
        self.location = None
        self.uid = int(id_match.group(1)) if id_match else None
        self.on_raid = None
        self.raid = None
        if match:
            self.nickname, self.crew, self.location = match.group('nic', 'crew', 'location')
            self.fraction = Wasteland.fractions_by_name.get(match.group('fraction')) or match.group('fraction')
            self.nickname = self.nickname.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            self.nickname = clearEmoji(self.nickname)
            hp, hp_now, hunger, attack, armor, power, accuracy, oratory, agility, stamina, stamina_now, distance = \
                [int(x) for x in
                 match.group(
                     'hp', 'hp_now', 'hunger', 'attack', 'armor', 'power', 'accuracy', 'oratory',
                     'agility', 'stamina', 'stamina_now', 'distance'
                 )]
            self.hp_now, self.stamina_now, self.hunger, self.distance = hp_now, stamina_now, hunger, distance
            self.stats = PlayerStat()
            (self.stats.hp, self.stats.stamina, self.stats.agility, self.stats.oratory, self.stats.accuracy,
             self.stats.power, self.stats.attack, self.stats.defence) = (hp, stamina, agility, oratory, accuracy, power,
                                                                         attack, armor)
            dzen = 0
            try:
                dzen = match.group('dzen') or 0  # Короткий профиль
            except IndexError:
                if dzen_match:
                    dzen = dzen_match.group(0) or 0
            if type(dzen) == str:
                if dzen.endswith('🏵'):  # 1-3
                    dzen = len(dzen)
                else:
                    dzen = int(dzen.strip('🏵'))
            if dzen_bars_match:
                dzen -= 1
            self.stats.dzen = dzen

            try:
                if match.group('on_raid'):
                    self.on_raid = True
            except IndexError:
                pass


class Raid:
    def __init__(self, fdate: datetime.datetime, raid_match):
        self.time = None
        self.text = None
        self.km = None
        self.cups = None
        self.boxes = None
        if raid_match:
            hour, day, month = raid_match.group('hour', 'day', 'month')
            if hour is None:
                h = (((int(fdate.hour) % 24) - 1) // 6) * 6 + 1
                d = 0
                if h < 0:
                    h = 19
                    d = -1
                date = datetime.datetime(
                    year=fdate.year, month=fdate.month, day=fdate.day,
                    hour=h
                ) + datetime.timedelta(days=d)
            elif day is None:
                date = datetime.datetime(
                    year=fdate.year, month=fdate.month, day=fdate.day,
                    hour=int(hour) % 24
                )
                if fdate - date < -datetime.timedelta(seconds=1):
                    date = date - datetime.timedelta(days=1)
            else:
                date = datetime.datetime(
                    year=fdate.year, month=int(month), day=int(day),
                    hour=int(hour) % 24
                )
                if fdate - date < datetime.timedelta(seconds=-1):
                    date = datetime.datetime(date.year - 1, date.month, date.day, date.hour)

            self.text = raid_match.group('msg')
            self.time = date


class InfoLine:
    def __init__(self, match=None):
        self.hp_now = None
        self.stamina_now = None
        self.hunger = None
        self.distance = None
        if match:
            self.hp_now, self.stamina_now, self.hunger, self.distance = \
                [int(x) for x in match.group('hp_now', 'stamina_now', 'hunger', 'distance')]


class PVPDrone:
    name: str
    damage: int | None
    defence: int | None

    def __init__(self):
        self.name = '/ДРОН/'
        self.damage = self.defence = None


class PVPLine:
    def __init__(self, player: str, health: int, damage: int, regeneration: int, drone: PVPDrone | None):
        self.player = player
        self.health = health
        self.damage = damage
        self.regeneration = regeneration
        self.drone = drone


class PVP:
    def __init__(self, winner: str, looser: str, pvp_lines: List[PVPLine], loose_text: str):
        self.winner = winner
        self.looser = looser
        self.pvp_lines = pvp_lines
        self.loose_text = loose_text

    def __str__(self):
        text = (
            f'ПВП Между {self.winner} и {self.looser}\n'
            f'Колличество действий: {len(self.pvp_lines)}\n'
        )
        for line in self.pvp_lines:
            if not line.drone:
                text += f'[{line.health}]{line.player} атакует сопперника ({line.damage})\n'
                if line.regeneration:
                    text += f'[{line.health + line.regeneration}]{line.player} регенерирует {line.regeneration}\n'
            else:
                if line.drone.damage:
                    text += f'{line.player} ( {line.drone.name} ) атакует на {line.damage}\n'
                else:
                    text += f'{line.player} ( {line.drone.name} ) блокирует на {line.drone.defence}\n'
        return text


class PVE:
    def __init__(self):
        self.damage_dealt = []
        self.damage_taken = []
        self.win = None
        self.mob_nic = None
        self.dunge = None


class Meeting:
    def __init__(self):
        self.fraction = None
        self.nic = None
        self.goat = None
        self.gang = None
        self.code = None

    def __str__(self):
        return f'[{self.fraction}]{self.nic} ({self.goat}; {self.gang}) #{self.code}'


class GettoPlayer:
    def __init__(self, match=None):
        if not match:
            self.fraction = None
            self.nickname = None
            self.telegram_id = None
        else:
            self.fraction = Wasteland.fractions_by_name.get(match.group('fraction')) or match.group('fraction')
            self.nickname = match.group('nickname')
            self.telegram_id = int(match.group('tguser_id'))

    def __str__(self):
        return f'[{self.fraction}]{self.nickname} - {self.telegram_id}'


class ViewPlayer:
    def __init__(self, match=None):
        if not match:
            self.nickname = None
            self.fraction = None
            self.u_command = None
        else:
            self.nickname, self.u_command = \
                match.group('nickname', 'u_command')
            self.nickname = clearEmoji(self.nickname)
            self.fraction = Wasteland.fractions_by_icon.get(match.group('fraction'), 'ww')

    def __str__(self):
        return f'[{self.fraction}] {self.nickname} ({self.u_command})'


class View:
    km: int
    players: List[ViewPlayer]

    def __init__(self, match):
        if not match:
            self.km = 0
        else:
            self.km = int(match.group('km'))
        self.players = []

    def __str__(self):
        players = '\n'.join([str(x) for x in self.players])
        return f'View {self.km}км:\n{players}'


class PlayerDistance:
    nickname: str
    km: int

    def __init__(self, nickname=None, km=None):
        self.nickname, self.km = clearEmoji(nickname), km

    def __str__(self):
        return f'{self.nickname}({self.km}км)'


class SumStatPlayer:
    nickname: str
    fraction: str
    sum_stat: int

    def __init__(self, m=None):
        if not m:
            self.nickname = '_?'
            self.fraction = 'ww'
            self.sum_stat = 0
        else:
            self.nickname = clearEmoji(m.group('nickname'))
            self.sum_stat = int(m.group('sum_stat'))
            self.fraction = Wasteland.fractions_by_icon.get(m.group('fraction'), 'ww')

    def __str__(self):
        return f'[{self.fraction}]{self.nickname} - {self.sum_stat}'


class SumStatTop:
    players: List[SumStatPlayer]

    def __init__(self):
        self.players = []

    def __str__(self):
        return (
            f'Топ игроков по БМ ( {len(self.players)}ч. )\n'
            '\n'.join([
                f'{idx}. [{x.fraction}]{x.nickname} - {x.sum_stat}'
                for idx, x in enumerate(self.players, 1)
            ])
        )


class TakingDunge:
    km: int
    gang: str
    players: List[PlayerDistance]

    def __init__(self, gang=None, km=0):
        self.gang, self.km = gang, km
        self.players = []

    def __str__(self):
        return (
            f'Захват {self.km} группой {self.gang}\n'
            f'Игроки: {"; ".join([str(x) for x in self.players])}'
        )


class TakingSuccess:
    gang_name: str
    location_name: str

    def __init__(self, match=None):
        if not match:
            self.gang_name, self.location_name = '[отсутствует]', '[подземелье]'
        else:
            self.gang_name, self.location_name = match.group('gang_name', 'location_name')

    def __str__(self):
        return f'Захват {self.location_name} группой {self.gang_name} удался'


class PokemobDead:
    mob_name: str
    dead_text: str
    nickname: str

    def __init__(self, mob_name: str, dead_text: str, nickname: str):
        self.mob_name, self.dead_text, self.nickname = mob_name, dead_text, nickname


class DomePlayer:
    nickname: str
    fraction: str
    code: str
    gang: str

    def __init__(self, match=None):
        if not match:
            self.nickname = self.fraction = self.code = self.gang = None
        else:
            self.nickname, self.gang = match.group('nickname', 'gang')
            self.fraction = Wasteland.fractions_by_icon.get(match.group('fraction')) or match.group('fraction')

    def __str__(self):
        return f'({self.fraction}) {self.nickname} из {self.gang if self.gang else "(Без банды)"}'


class Dome:
    players: List[DomePlayer]

    def __init__(self):
        self.players = []

    def __str__(self):
        players = '\n'.join([str(x) for x in self.players])
        return f'Купол грома:\n{players}'


class StockItem:
    name: str
    amount: int
    category: str

    def __init__(self, name: str = '', amount: int = 0, category: str = ''):
        self.name, self.amount, self.category = name, amount, category


class Boss:
    name: str
    hp: int
    attacks: List[int]

    def __init__(self, name: str = None, hp: int = 0, attacks=None):
        if attacks is None:
            attacks = []
        self.name, self.hp, self.attacks = name, hp, attacks

    def __bool__(self):
        return self.name is not None

    def __str__(self):
        return (
            f'Босс: {self.name}\n'
            f'❤️Здоровье: {self.hp}\n'
            f'⚔️Атаки: {"; ".join([str(x) for x in self.attacks])}'
            f'⚔️Суммарный урон: {sum(self.attacks)}'
        )


class BossFightPlayer:
    nickname: str
    hp: int
    attacks: List[int]
    loose_attacks: List[int]

    def __init__(self, nickname: str = None):
        self.nickname = nickname
        self.hp = 0
        self.attacks = []
        self.loose_attacks = []

    def __str__(self):
        return (
            f'Игрок: {self.nickname}\n'
            f'❤️Здоровье: {self.hp}\n'
            f'⚔️Атаки: {"; ".join([str(x) for x in self.attacks])}\n'
            f'⚔️Пропущенные атаки: {"; ".join([str(x) for x in self.loose_attacks])}\n'
            f'⚔️Суммарный урон: {sum(self.attacks)}\n'
            f'⚔️Суммарный пропущенный урон: {sum(self.loose_attacks)}'
        )


class BossFight:
    boss: Boss
    players: List[BossFightPlayer]

    def __init__(self, boss: Boss, players: list[BossFightPlayer]):
        self.boss = boss
        self.players = players

    def __str__(self):
        return f'{self.boss}\n\n' + '\n\n'.join([str(x) for x in self.players])


class Scuffle:
    winner: str
    winner_fraction: str

    dead_text: str

    looser: str
    looser_fraction: str

    def __init__(self, match=None):
        if not match:
            self.winner = self.winner_fraction = self.dead_text = self.looser = self.looser_fraction = None
        else:
            self.winner = match.group('winner_spases') + match.group('winner_text')
            self.looser = match.group('looser_spases') + match.group('looser_text')

            self.winner_fraction = Wasteland.fractions_by_icon.get(match.group('winner_fraction'), 'ww')
            self.looser_fraction = Wasteland.fractions_by_icon.get(match.group('looser_fraction'), 'ww')

            self.dead_text = match.group('dead_text')


class PlayerParseResult(InnerUpdate):
    def __init__(self, update: telegram.Update):
        super().__init__(update)
        self.view = None
        self.sum_stat_top = None
        self.raid = None
        self.profile = None
        self.info_line = None
        self.loot = None
        self.loss = None
        self.pvp = None
        self.pve = None
        self.meeting = None
        self.getto = None
        self.distance = None

        self.stock = None  # List[StockItem]
        self.dome = None


class Gangster:
    fraction: str
    nickname: str
    ears: int
    distance: int
    status: str

    def __init__(self, match):
        if match:
            self.nickname = clearEmoji(match.group('nickname'))
            self.ears = int(match.group('ears'))
            self.status = match.group('status')
            self.distance = int(match.group('distance'))


class Group:
    name: str
    commander: str

    def __init__(self, match=None):
        if match:
            self.name = match.group('name')
            self.commander = match.group('commander')
        else:
            self.name = None
            self.commander = None


class Gang(Group):
    goat: 'Goat'
    players: List[Gangster]

    def __init__(self, match):
        super(Gang, self).__init__(match)
        if match:
            self.goat = Goat()
            self.goat.name = match.group('goat')
            if self.goat.name == 'Нет':
                self.goat = None
        else:
            self.goat = None
        self.players = []


class Goat(Group):
    gangs: List[str]
    league: str

    def __init__(self, match=None):
        super(Goat, self).__init__(match)
        self.gangs = []
        self.league = (match.group('league') or '🥉Детская лига') if match else None


class GroupParseResult(InnerUpdate):

    def __init__(self, update: telegram.Update):
        super(GroupParseResult, self).__init__(update)
        self.gang = None
        self.goat = None


class ParserModule(BasicModule):
    """
    responds to forwards in group 1 (not default 10 and not activity 0)
    as a result make EventManager trigger WWHandlers in other modules
    """
    module_name = 'parser'
    group = 1

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_handler(MessageHandler(CustomFilters.ww_forwarded & Filters.text, self._text))
        self.add_handler(MessageHandler(Filters.photo, self._photo))
        self.add_handler(MessageHandler(CustomFilters.tolyly_forwarded & Filters.text, self._text))
        super().__init__(event_manager, message_manager, dispatcher)

        self.raid_format = re.compile(
            r'(Рейд\s+(?P<msg>в\s+((?P<hour>\d+)|(-+)):\d+\s*((?P<day>\d+)\.(?P<month>\d+))?'
            r'.*\n.*\n.*))'
        )

        self.re_profile = re.compile(
            r'\n(?P<nic>[^\n]*),\s*(?P<fraction>[^\n]*)\s+'
            r'(🤟Банда:\s+(?P<crew>[^\n]*)\s+)?'
            r'❤️Здоровье:\s+(?P<hp_now>\d+)/(?P<hp>\d+)\s+'
            r'☠️Голод:\s+(?P<hunger>\d+)%\s*/myfood\s+'
            r'⚔️Урон:\s+(?P<attack>\d+)(\s*\([^)]*\))?\s*'
            r'🛡Броня:\s+(?P<armor>\d+)(\s*\([^)]*\))?\s*'
            r'💪Сила:\s+(?P<power>\d+)(\s*\([^)]*\))?\s*'
            r'🎯Меткость:\s+(?P<accuracy>\d+)(\s*\([^)]*\))?\s*'
            r'🗣Харизма:\s+(?P<oratory>\d+)(\s*\([^)]*\))?\s*'
            r'🤸🏽‍♂️Ловкость:\s+(?P<agility>\d+)(\s*\([^)]*\))?\s*'
            r'(?:💡Умения /perks\s+)?'
            r'(?:⭐️Испытания.+\s+)?'
            r'🔋Выносливость:\s+(?P<stamina_now>\d+)/(?P<stamina>\d+)\s*/ref\s+'
            r'📍(?P<location>[^\n]*),\s*👣\s*(?P<distance>\d+)км\.\s*(?P<on_raid>👊)?'
        )

        self.re_profile_short = re.compile(
            r'👤(?P<nic>[^\n]*?)(?:(?P<dzen>[🏵\d+|🏵]*))?\n'
            r'├🤟 (?P<crew>[^\n]*)\n'
            r'├(?P<fraction>[^\n]*)\n'
            r'├❤️(?P<hp_now>\d+)/(?P<hp>\d+)\D+(?P<hunger>\d+)\D+'
            r'(?P<attack>\d+)\D+\D*(?P<armor>\d+)\D+'
            r'(?P<power>\d+)\D+\D*(?P<accuracy>\d+)\D+'
            r'(?P<oratory>\d+)\D+(?P<agility>\d+)\D+'
            r'(?P<stamina_now>\d+)/(?P<stamina>\d+)\D+'
            r'👣(?P<distance>\d+)\n├🔥(?P<location>[^\n]+)'
        )

        self.re_id = re.compile(r'ID(\d+)')
        self.re_dzen = re.compile(r'(🏵(\d+)|🏵+)')
        self.re_dzen_bars = re.compile(r'[▓░]')
        self.re_info_line = re.compile(
            r'❤️(?P<hp_now>-?\d+)\\(?P<hp>\d+)\s*🍗(?P<hunger>\d+)%\s*'
            r'🔋(?P<stamina_now>\d+)\\(?P<stamina>\d+)\s*👣(?P<distance>\d+)км'
        )

        self.re_pve = re.compile(r'Сражение с\s*(?P<mob>.*)')
        self.re_pve_win = re.compile('Ты одержал победу!')
        self.re_pve_dt = re.compile(r'💔(-?\d+)')
        self.re_pve_dd = re.compile(r'💥(-?\d+)')

        self.re_loot_caps = re.compile(r'\n\s*(Ты заработал:|Получено крышек:|Найдено крышек:)\s*🕳(\d+)')
        self.re_loot_mats = re.compile(r'\n\s*(Получено материалов:|Получено:|Собрано материалов:)\s*📦(\d+)')
        self.re_loot_other = re.compile(r'\n\s*Получено:\s*([^📦].*)')
        self.re_loot_mult = re.compile(r'\s*х?(\d+)\s*$')
        self.re_loot_pvp = re.compile(r'Получено:\s+🕳(?P<caps>\d+)\s+и\s+📦(?P<mats>\d+)')

        self.re_loss_caps = re.compile(r'(\n\s*Потеряно крышек:|Ты потерял:)\s*🕳(\d+)')
        self.re_loss_mats = re.compile(r'(\n\s*Потеряно материалов:|Проебано:)\s*📦(\d+)')
        self.re_loss_dead = re.compile(r'\n\s*Потеряно:\s*🕳(\d+)\s*и\s*📦(\d+)')

        fractions = '|'.join(Wasteland.fractions_by_name.keys())
        self.re_friend = re.compile(r'знакомый:\s+👤(?P<nickname>.+)\s+из\s+(?P<fraction>{})!'.format(fractions))
        self.re_maniak = re.compile(r'\nЭто (?P<nic>.*) из (?P<fraction>' + fractions + ')')
        self.re_player_in_brackets = re.compile(r'(?P<nic>.*)\((?P<fraction>' + fractions + r')\)')
        self.re_duel = re.compile(
            r'👤(?P<nickname>.+)\s+из\s+(?P<fraction>' + fractions + r')\s*'
                                                                    r'(🤘(?P<gang>.+)\s+)?'
            )

        self.re_getto = re.compile(r'Игроки в белом гетто')

        self.re_raid_locs = [(re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*📦'), 5),
                             (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🕳'), 9),
                             (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🔹'), 20),
                             (re.compile(r"🕳\s*\+\d+\s*📦\s*\+\d+\s*((❤️|❤)\s*\+\s*\d+,\s*)?Эффедрин"), 24),
                             (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*💡'), 28),
                             (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*💾'), 32),
                             (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🔩'), 38),
                             (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🔗'), 46)
                             ]
        self.re_raid_msg_default = re.compile(r'🕳\s*\+(\d+)\s*📦\s*\+(\d+)\s*(.*)')

        self.re_goat = re.compile(
            r'🐐\s*(?P<name>.+)[\s\S]*'
            r'🏅\s*Уровень:\s*(?P<goat_level>\d+)\s*'
            r'🚩Лига:\s*(?P<league>.+)\s*'
            r'🏆\s*Рейтинг:\s*(?P<goat_rate>\d+)\s*'
            r'Лидер\s*⚜️\s*(?P<commander>.+)\s*'
            r'Банды-участники \(\d/\d\)\s*'
            r'(?P<gangs>[\s\S]+)\s*'
            r'🐐\s+👊\s+\d+\s+/\s+\d+\s*'
            r'Штаб козла[\s\S]+'
        )
        _frac_icons = '|'.join(f'({i})' for i in Wasteland.fractions_by_icon)
        self.re_dome = re.compile(r'\((?P<fraction>{})\)\s(?P<nickname>.+)\s+(🤘(?P<gang>.+)|\(Без банды\))'.format(_frac_icons))

        self.re_player_in_gang = re.compile(
            r'(?P<idx>(🥇)|(🥈)|(🥉)|(\d+\.))\s(?P<nickname>.+)\s*'
            r'👂(?P<ears>\d+)\s+(?P<status>[📍👟👊])(?P<distance>\d+)km'.format(_frac_icons)
        )
        self.re_gang = re.compile(
            r'🤘\s*(?P<name>.+)\s+🏅\d+[\s\S]*'
            r'Панель банды\.\s+'
            r'Главарь\s*⚜️\s*(?P<commander>.+)\s*'
            r'Козёл\s*'
            r'🐐\s*(?P<goat>.+) /goat\s*'
        )
        self.re_gang_in_goat = re.compile(r'(?P<idx>(🥇)|(🥈)|(🥉)|(\d+\.))\s*🤘(?P<gang>.+)\s+💥(?P<power>\d+)\s+(🔐|/gcr_\d+)')
        self.re_view = re.compile(r'[🚷👣]\s*(?P<km>\d+)\s+км.')
        self.re_view_line = re.compile(r'((?P<fraction>{})(?P<nickname>.*)\s+\|\s+👤/u_(?P<u_command>.*));'.format(_frac_icons))
        self.re_meeting_photo_line_drone = re.compile(
            r'(?P<fraction>{})\s*(?P<nic>.+)\s+(и\s+его\s+(?P<drone>.+).)\s*'
            r'(🐐(?P<goat>.+)\s+)?🤘(?P<gang>.+)\s*(⚔️\s+/p_(?P<code>.+))?'.format(_frac_icons)
        )
        self.re_meeting_photo_line = re.compile(
            r'(?P<fraction>{})\s*(?P<nic>.+)\s*'
            r'(🐐(?P<goat>.+)\s+)?🤘(?P<gang>.+)\s*(⚔️\s+/p_(?P<code>.+))?'.format(_frac_icons)
        )

        self.re_taking = re.compile(
            r'\s*✊️Захват\s+(?P<location_name>.+)\s*'
            r'\s*🤘(?P<gang>.*)'
        )
        self.re_taking_gansters_final = re.compile(r'👊(?P<nickname>.+)\s(❤️|☠️)\d+/(?P<hp>\d+)')
        self.re_taking_gansters = re.compile(r'👊(?P<nickname>.+)')
        self.re_taking_fail = re.compile(r'[\s\S]+Захват\s+провален\.[\s\S]+')
        self.re_taking_success = re.compile(r'(?P<location_name>.+)\s+теперь\s+под\s+контролем\s+🤘(?P<gang_name>.+)!')

        self.re_sum_stat_top = re.compile(r'[\s\S]*🏆ТОП\s*ИГРОКОВ:[\s\S]*')
        self.re_sum_stat_top_players = re.compile(
            r'(?P<position>\d+).\s+(?P<nickname>.+)\s+\[(?P<fraction>{})]\s*'
            r'Счет:\s*(?P<sum_stat>\d+)\s*'.format(_frac_icons)
        )

        self.re_notebook = re.compile(r'[\s\S]*ДНЕВНИК ВЫЖИВАНИЯ[\s\S]*')
        self.re_notebook_line = re.compile(r'(?P<name>.+)\s+(?P<value>\d+)(?P<name2>.*);')

        self.food = {'Луковица', 'Помидор', 'Конфета', 'Булочка', 'Морковь', 'Человечина', 'Эдыгейский сыр',
                     'Мясо белки', 'Собачатина', r'Абрик\*с', 'Сухари', 'Чипсы', 'Голубь', 'Сырое мясо', 'Мясо утки',
                     'Хомячок', 'Красная слизь', 'Луковица', 'Сухофрукты', 'Молоко брамина', 'Вяленое мясо',
                     'Тесто в мясе', 'Сахарные бомбы', 'Консервы', 'Радсмурф', 'Мутафрукт', 'Что-то тухлое',
                     'Гнилой апельсин', 'Гнилое мясо', 'Не красная слизь'}
        self.drugs = {'Холодное пиво', 'Виски', 'Бурбон', 'Абсент', 'Глюконавт', 'Психонавт', 'Ментаты', 'Психо',
                      'Винт', 'Ультравинт', 'Скума'}

        self._n_re_pvp = (
            r'<b>.+</b> из <b>(?P<fraction1>.+)</b>\n'
            r'<code>VS\.</code>\n'
            r'<b>.+</b>\s+из <b>(?P<fraction2>.+)</b>\n'
            r'<code>FIGHT!</code>\n\n'
            r'(?P<pvp_lines>[\s\S]+)\n\n'
            r'(?P<winner>(?P<winner_spases>\s*)<b>(?P<winner_text>.+)</b>)\s+(?P<dead_text>.+)\s(?P<looser>(?P<looser_spases>\s*)<b>(?P<looser_text>.+)</b>)'
        )

        self._n_re_pvp_drone_defence = re.compile(
            r'🛰<b>(?P<drone_name>.+)</b>\s+принял\s+на\s+себя\s+удар\s+от\s(?P<nickname>(?P<nickname_spases>\s*)<b>(?P<nickname_text>.+)</b>)\s+🛡<code>-(?P<defence>\d+)</code>'
        )
        self._n_re_pvp_drone_attack = re.compile(
            r'🛰<b>(?P<drone_name>.+)</b>\s+атаковал\s(?P<nickname>(?P<nickname_spases>\s*)<b>(?P<nickname_text>.+)</b>)\s+<code>💥(?P<damage>\d+)</code>'
        )
        self._n_re_pvp_base_attack = re.compile(
            r'❤️<code>(?P<hp>\d+)\s+</code>(?P<nickname>(?P<nickname_spases>\s*)<b>(?P<nickname_text>.+)</b>)\s+(?P<text>.+)\s+<code>\(💥(?P<damage>\d+)\)</code>(⚡️)?(\s+❣️(?P<regen>\d+))?'
        )
        self._n_re_pvp_loose_line = re.compile(
            r'❤️<code>(?P<hp>\d+)\s+</code>(?P<nickname>(?P<nickname_spases>\s*)<b>(?P<nickname_text>.+)</b>)\s+(?P<text>.+)\s+<code>\(💔(?P<damage>\d+)\)</code>'
        )
        self._n_re_pvp_insight = re.compile(r'❤️<code>(?P<hp>\d+)\s+</code>(?P<nickname>(?P<nickname_spases>\s*)<b>(?P<nickname_text>.+)</b>)\s+увернулся\s+🌀')

        self._re_player_in_getto = re.compile(
            r'👤(?P<nickname>.+)\s+\((?P<fraction>.+)\)\s+'
            r'🤘\(Без банды\)\s+'
            r'/inv_(?P<tguser_id>\d+)'
        )
        self._re_raid_voevat_answer = re.compile(
            r'Ты занял позицию для 👊Рейда и приготовился к групповому сражению козлов\.'
            r'Рейд начнётся через ⏱(?P<last_time>.+)\.'
        )
        self._re_raid_voevat_answer_time = re.compile(r'((?P<hours>\d+)ч\.)?\s*((?P<minutes>\d+)\s*мин)?((?P<seconds>\d+)\s*сек)?')

        self._re_stock_item = re.compile(r'▫️\s+(?P<name>.+)\s+(\((?P<amount>\d+)\))?\s+/(?P<command>.+)')
        self._re_food_item = re.compile(r'▪️\s+(?P<name>.+)\s+(\((?P<amount>\d+)\))?\s+/(?P<command>.+)')
        self._re_resource_item = re.compile(r'▫️\s+(?P<name>.+)\s+(\((?P<amount>\d+)\))?\s+')

        self._re_stuff_items = re.compile(r'Хлам\s+(?P<stuff>[\s\S]+)🗃Припасы\s+/myfood')
        self._re_stuff_item = re.compile(r'(?P<name>[^,()]+)(\((?P<amount>\d+)\))?')

        self._re_boss_part = re.compile(
            r'(?P<boss_name>.+)\s❤️(?P<boss_hp>-?\d+)\n'
            r'(?P<fight>[\s\S]+)'
        )
        self._re_boss_player_attack = re.compile(r'(?P<nickname>.+)\s💥(?P<damage>-?\d+)')
        self._re_boss_attack = re.compile(r'(?P<nickname>.+)\s💔-(?P<boss_damage>\d+)')
        self._re_boss_player_dead = re.compile(r'(?P<nickname>.+)\s☠️')
        self._re_pokemob_dead = re.compile(
            r'(?P<fraction>{})\s(?P<nickname>(?P<nickname_spases>\s*)<b>(?P<nickname_text>.+)</b>)\s+(?P<dead_text>.+)\s<i>(?P<mob_name>.+)</i>'.format(_frac_icons)
        )
        self._re_scuffle = re.compile(
            r'(?P<winner_fraction>{})\s(?P<winner>(?P<winner_spases>\s*)<b>(?P<winner_text>.+)</b>)\s+(?P<dead_text>.+)\s(?P<looser_fraction>{})(?P<looser>(?P<looser_spases>\s*)<b>(?P<looser_text>.+)</b>)'.format(
                _frac_icons,
                _frac_icons
            )
        )
        self._re_lynch = re.compile(r'(?P<fraction>' + _frac_icons + r')\s(?P<nickname>.+)\s{2}👥(?P<recorded>\d)/(?P<total>\d)\s+/gomaniac_(?P<user_id>\d+)')

    def _parse_boss_fight(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if not text.startswith('ХОД БИТВЫ:'):
            return

        parts = text.split('\n\n')
        parts.pop(0)
        boss = Boss()
        players = {

        }
        for part in parts:
            m = self._re_boss_part.search(part)
            if not m:
                continue
            boss_name, boss_hp = m.group('boss_name'), int(m.group('boss_hp'))
            boss.name = boss_name
            boss.hp = boss_hp if boss.hp == 0 else boss.hp

            for line in m.group('fight').split('\n'):
                player_attack = self._re_boss_player_attack.search(line)
                boss_attack = self._re_boss_attack.search(line)
                player_dead = self._re_boss_player_dead.search(line)

                if player_attack:
                    nickname = player_attack.group('nickname')
                elif boss_attack:
                    nickname = boss_attack.group('nickname')
                elif player_dead:
                    nickname = player_dead.group('nickname')
                else:
                    continue

                if not (player := players.get(nickname, None)):
                    player = BossFightPlayer(nickname=nickname)

                if player_attack:
                    player.attacks.append(int(player_attack.group('damage')))
                elif boss_attack:
                    boss_damage = int(boss_attack.group('boss_damage'))
                    player.loose_attacks.append(boss_damage)
                    boss.attacks.append(boss_damage)
                    player.hp += boss_damage
                elif player_dead:
                    player.hp -= player.loose_attacks[len(player.loose_attacks) - 1] - 1
                else:
                    continue
                players.update(
                    {
                        nickname: player
                    }
                )
        if not boss:
            return
        pr.boss_fight = BossFight(boss=boss, players=list(players.values()))

    def _parse_info_line(self, message: telegram.Message, pr: PlayerParseResult):
        match = self.re_info_line.search(message.text or '')
        if match:
            pr.info_line = InfoLine(match)

    def _parse_getto(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if not self.re_getto.match(text):
            return
        pr.getto = []
        for m in self._re_player_in_getto.finditer(text):
            pr.getto.append(GettoPlayer(m))

    def _parse_dome(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if '📊ТОП Купола /tdtop' not in text:
            return

        dome = Dome()
        for player in self.re_dome.finditer(text):
            dome.players.append(DomePlayer(player))
        if dome.players:
            pr.dome = dome

    def _parse_friend_maniak_meeting(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if pr.pvp is not None:
            return
        match = self.re_friend.search(text) or self.re_maniak.search(text)
        if not match:
            return

        pr.meeting = Meeting()
        pr.meeting.nic = match.group('nickname')
        pr.meeting.fraction = Wasteland.fractions_by_name(match.group('fraction'))
        pr.meeting.type = 1

    def _parse_glove_meeting(self, message: telegram.Message, pr: PlayerParseResult):
        if pr.meeting is not None:
            return
        if pr.pvp is not None:
            return
        text = message.text or ''
        match = self.re_duel.search(text)
        if not match:
            return
        pr.meeting = Meeting()
        pr.meeting.nic = match.group('nickname')
        pr.meeting.fraction = Wasteland.fractions_by_name.get(match.group('fraction'), 'ww')
        pr.meeting.gang = match.group('gang')
        pr.meeting.type = 2

    def _parse_pokemob(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text_html or ''
        if 'Неподалеку ты заметил другого выжившего.' not in text:
            return
        match = self._re_pokemob_dead.search(text)
        if not match:
            return
        nickname = match.group('nickname_spases') + match.group('nickname_text')
        mob_name, dead_text = match.group('mob_name', 'dead_text')
        pr.pokemob_dead = PokemobDead(mob_name=mob_name, dead_text=dead_text, nickname=nickname)

    def _parse_scuffle(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text_html or ''
        if 'Неподалеку ты заметил какую-то потасовку.' not in text:
            return
        match = self._re_scuffle.search(text)
        if not match:
            return
        pr.scuffle = Scuffle(match)

    def _parse_pve(self, message: telegram.Message, pr: PlayerParseResult):
        """
        should be called only after _parse_info_line
        """
        text = message.text or ''
        if pr.info_line is None:
            return
        match = self.re_pve.search(text)
        if match:
            pr.pve = PVE()
            pr.pve.mob_nic = match.group('mob')
            pr.pve.mob_nic = pr.pve.mob_nic.strip()
            pr.pve.win = self.re_pve_win.search(text) is not None
            pr.pve.damage_dealt = [int(m.group(1)) for m in self.re_pve_dd.finditer(text)]
            pr.pve.damage_taken = [-int(m.group(1)) for m in self.re_pve_dt.finditer(text)]

    def _parse_loot(self, message: telegram.Message, pr: PlayerParseResult):
        pr.loot = {}
        pr.loss = {}
        text = message.text or ''
        caps = sum([int(m.group(2)) for m in self.re_loot_caps.finditer(text)])
        mats = sum([int(m.group(2)) for m in self.re_loot_mats.finditer(text)])

        caps += sum([int(x.group('caps')) for x in self.re_loot_pvp.finditer(text)])
        mats += sum([int(x.group('mats')) for x in self.re_loot_pvp.finditer(text)])

        caps_loss = sum([int(m.group(2)) for m in self.re_loss_caps.finditer(text)])
        mats_loss = sum([int(m.group(2)) for m in self.re_loss_mats.finditer(text)])
        dead_match = self.re_loss_dead.search(text)
        if dead_match:
            caps_loss += int(dead_match.group(1))
            mats_loss += int(dead_match.group(2))

        if caps:
            pr.loot['🕳'] = caps
        if mats:
            pr.loot['📦'] = mats
        if caps_loss:
            pr.loss['🕳'] = caps_loss
        if mats_loss:
            pr.loss['📦'] = mats_loss

        for m in self.re_loot_other.finditer(text):
            loot = m.group(1)
            m_x = self.re_loot_mult.search(loot)
            k = 1
            if m_x:
                loot = loot[:m_x.start()]
                k = int(m_x.group(1))
            loot = loot.strip()
            if loot in pr.loot.keys():
                pr.loot[loot] += k
            else:
                pr.loot[loot] = k

    def _parse_pvp(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text_html or ''  # TODO: работать с HTML текстом ( message.text_html )

        re_ = self._n_re_pvp
        if 'ушел победителем из этой схватки.' in text:
            re_ += r'\n\s*👤<code>.+</code>\s+из\s+<b>.+</b>\s+ушел\s+победителем\s+из\s+этой\s+схватки\.'
        re_ = re.compile(re_)

        match = re_.search(text)

        if not match:
            return

        # nics = list(match.group('winner', 'looser'))
        nics = [''.join(match.group(f'{prefix}_spases', f'{prefix}_text')) for prefix in ['winner', 'looser']]
        pvp_lines_text = match.group('pvp_lines')

        pvp_lines = []
        for idx, line in enumerate(pvp_lines_text.split('\n')):
            pvp_attack = self._n_re_pvp_base_attack.search(line)
            loose_line = self._n_re_pvp_loose_line.search(line)
            pvp_insight = self._n_re_pvp_insight.search(line)

            drone_attack = self._n_re_pvp_drone_attack.search(line)
            drone_defence = self._n_re_pvp_drone_defence.search(line)

            hp = attack = regen = drone = nickname = None
            if drone_defence:
                drone_name, defence = drone_defence.group('drone_name', 'defence')
                nickname = drone_defence.group('nickname_spases') + drone_defence.group('nickname_text')
                nickname = nics[0 if nics.index(nickname) == 1 else 1]
                drone = PVPDrone()
                drone.name = drone_name
                drone.defence = int(defence)

            elif drone_attack:
                drone_name, attack = drone_attack.group('drone_name', 'damage')
                nickname = drone_attack.group('nickname_spases') + drone_attack.group('nickname_text')
                attack = int(attack)
                nickname = nics[0 if nics.index(nickname) == 1 else 1]
                drone = PVPDrone()
                drone.name = drone_name
                drone.damage = attack

            elif pvp_attack:
                hp, attack, regen = [int(x) if x else 0 for x in pvp_attack.group('hp', 'damage', 'regen')]
                text = pvp_attack.group('text')
                nickname = pvp_attack.group('nickname_spases') + pvp_attack.group('nickname_text')

            elif loose_line:
                hp, attack = [int(x) if x else 0 for x in loose_line.group('hp', 'damage')]
                text = loose_line.group('text')
                nickname = loose_line.group('nickname_spases') + loose_line.group('nickname_text')
                hp += attack
                attack = None
            else:
                continue

            pvp_lines.append(PVPLine(
                player=nickname,
                health=hp,
                damage=attack,
                regeneration=regen,
                drone=drone
            ))

        winner, looser = (''.join(match.group(f'{prefix}_spases', f'{prefix}_text')) for prefix in ['winner', 'looser'])
        pr.pvp = PVP(
            winner=winner,
            looser=looser,
            pvp_lines=pvp_lines,
            loose_text=match.group('dead_text')
        )

    def _parse_forward(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        match = self.re_profile.search(text) or self.re_profile_short.search(text)
        if not match:
            return

        tail = message.text[match.end():]
        id_match = self.re_id.search(tail)
        dzen_match = self.re_dzen.search(tail)
        dzen_bars_match = self.re_dzen_bars.search(tail)
        pr.profile = Profile(match, id_match, dzen_match, dzen_bars_match)
        pr.profile.stats.time = message.forward_date
        self._parse_raid(message, pr)
        if getattr(pr, 'raid', False):
            pr.profile.raid = pr.raid
        return False

    def _parse_raid_msg(self, msg: str):
        rkm = -1
        cups = 0
        boxes = 0
        loc = -1
        for re_l, km in self.re_raid_locs:
            if re_l.search(msg):
                rkm = km
                m = self.re_raid_msg_default.search(msg)
                if m:
                    cups = int(m.group(1))
                    boxes = int(m.group(2))
                break
        if rkm < 0:  # Special cases 12, 16
            m = self.re_raid_msg_default.search(msg)
            if m:
                rest = m.group(3)
                if any([re.match(val, rest) for val in self.food]):
                    rkm = 16
                elif any([re.match(val, rest) for val in self.drugs]):
                    rkm = 12
                loc = rkm if rkm > 0 else -1
                cups = int(m.group(1))
                boxes = int(m.group(2))
        else:
            loc = rkm
        return loc, cups, boxes

    def _parse_raid(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        m = self.raid_format.search(text)
        if m:
            pr.raid = Raid(message.forward_date, m)
            pr.raid.km, pr.raid.cups, pr.raid.boxes = self._parse_raid_msg(pr.raid.text)

    def _parse_gang(self, msg: telegram.Message, pres: GroupParseResult):
        match = self.re_gang.match(msg.text)
        if not match:
            return
        gang = Gang(match)

        for m in self.re_player_in_gang.finditer(msg.text):
            gang.players.append(Gangster(m))

        pres.gang = gang

    def _parse_goat(self, msg: telegram.Message, pres: GroupParseResult):
        match = self.re_goat.match(msg.text)
        if not match:
            return
        goat = Goat(match)
        for gang in self.re_gang_in_goat.finditer(msg.text):
            goat.gangs.append(gang.group('gang'))

        pres.goat = goat

    def _parse_view(self, msg: telegram.Message, pr: PlayerParseResult):
        match = self.re_view.search(msg.text)
        if not match:
            return
        view = View(match)
        for player in self.re_view_line.finditer(msg.text):
            view.players.append(ViewPlayer(player))
        pr.view = view

    def _parse_taking(self, msg: telegram.Message, pr: PlayerParseResult):
        match = self.re_taking.search(msg.text)
        if not match:
            return
        gang, location_name = match.group('gang', 'location_name')
        km = Wasteland.take_locations.get(location_name, 0)
        taking = TakingDunge(gang=gang, km=km)
        for gangster in self.re_taking_gansters.finditer(msg.text):
            taking.players.append(PlayerDistance(gangster.group('nickname'), km))

        pr.taking = taking

    def _parse_taking_fail(self, msg: telegram.Message, pr: PlayerParseResult):
        match = self.re_taking_fail.search(msg.text)
        if not match:
            return
        taking = TakingDunge()
        for gangster in self.re_taking_gansters_final.finditer(msg.text):
            taking.players.append(PlayerDistance(gangster.group('nickname'), None))
        pr.taking_fail = taking

    def _taking_success(self, msg: telegram.Message, pr: PlayerParseResult):
        text = msg.text or ''
        match = self.re_taking_success.search(text)
        if not match:
            return
        pr.taking_success = TakingSuccess(match=match)

    def _parse_sum_stat_top(self, msg: telegram.Message, pr: PlayerParseResult):
        match = self.re_sum_stat_top.match(msg.text)
        if not match:
            return
        top = SumStatTop()
        for m in self.re_sum_stat_top_players.finditer(msg.text):
            top.players.append(SumStatPlayer(m))
        pr.sum_stat_top = top

    def _parse_notebook(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        match = self.re_notebook.match(text)
        if not match:
            return

        notebook = Notebook()
        for line in self.re_notebook_line.finditer(text):
            name, name2 = line.group('name', 'name2')
            value = int(line.group('value'))
            notebook.attrs.append((name, value, name2))
        pr.notebook = notebook

    def _parse_stock(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if '🎒СОДЕРЖИМОЕ РЮКЗАКА' not in text:
            return

        pr.stock = [] if not pr.stock else pr.stock

        for stock_item in self._re_stock_item.finditer(text):
            name = stock_item.group('name')
            amount = stock_item.group('amount') or 1
            amount = int(amount)

            pr.stock.append(StockItem(name=name, amount=amount, category='WW_OTHER'))

    def _parse_food(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if '🗃ПРИПАСЫ В РЮКЗАКЕ' not in text:
            return
        pr.stock = [] if not pr.stock else pr.stock

        for stock_item in self._re_food_item.finditer(text):
            name = stock_item.group('name')
            amount = stock_item.group('amount') or 1
            amount = int(amount)

            pr.stock.append(StockItem(name=name, amount=amount, category='WW_FOOD'))

    def _parse_stuff(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if '🔧РЕСУРСЫ И ХЛАМ' not in text:
            return
        pr.stock = [] if not pr.stock else pr.stock

        for stock_item in self._re_resource_item.finditer(text):
            name = stock_item.group('name')
            amount = stock_item.group('amount') or 1
            amount = int(amount)
            pr.stock.append(StockItem(name=name, amount=amount, category='WW_RESOURCE'))
        stuff_items = self._re_stuff_items.search(text)
        if not stuff_items:
            return
        for stuff_item in self._re_stuff_item.finditer(stuff_items.group('stuff')):
            name = stuff_item.group('name').strip()
            if not name:
                continue
            amount = stuff_item.group('amount') or 1
            amount = int(amount)
            pr.stock.append(StockItem(name=name, amount=amount, category='WW_STUFF'))

    def _parse_lynch(self, message: telegram.Message, pr: PlayerParseResult):
        text = message.text or ''
        if '🔥Суд Линча ...групповое избиение негодяя не делает тебя самого негодяем, так ведь?' not in text:
            return
        players = []
        for player in self._re_lynch.finditer(text):
            meet = Meeting()
            meet.nickname = player.group('nickname')
            meet.fraction = Wasteland.fractions_by_icon.get(player.group('fraction'))
            players.append(meet)
        if players:
            pr.lynch = players

    def _photo_meeting(self, msg: telegram.Message, pr: PlayerParseResult):
        if not msg.caption:
            return
        m = self.re_meeting_photo_line_drone.search(msg.caption) or self.re_meeting_photo_line.search(msg.caption)
        if not m:
            return
        pr.meeting = Meeting()
        pr.meeting.nic = clearEmoji(m.group('nic'))
        pr.meeting.fraction = Wasteland.fractions_by_icon.get(m.group('fraction'), 'ww')
        pr.meeting.goat = m.group('goat') or None
        pr.meeting.gang = m.group('gang') or None
        pr.meeting.code = m.group('code')
        pr.meeting.type = 3

    def _photo_forward(self, msg: telegram.Message, pr: PlayerParseResult):
        self.message_manager.bot.forward_message(
            chat_id=settings.UNKOWN_CHAT_ID, message_id=pr.telegram_update.message.message_id,
            from_chat_id=pr.telegram_update.message.chat_id
        )

    @inner_update(PlayerParseResult)
    @get_player
    def _text(self, update: PlayerParseResult, *args, **kwargs):
        player_info_parsed = update
        group_info_parsed = GroupParseResult(update.telegram_update)
        group_info_parsed.invoker = player_info_parsed.invoker
        group_info_parsed.player = player_info_parsed.player
        msg = update.telegram_update.message

        self._parse_info_line(msg, player_info_parsed)
        self._parse_forward(msg, player_info_parsed)

        self._parse_raid(msg, player_info_parsed)
        self._parse_pve(msg, player_info_parsed)
        self._parse_loot(msg, player_info_parsed)
        self._parse_pvp(msg, player_info_parsed)
        self._parse_friend_maniak_meeting(msg, player_info_parsed)
        self._parse_glove_meeting(msg, player_info_parsed)
        self._parse_getto(msg, player_info_parsed)
        self._parse_view(msg, player_info_parsed)
        self._parse_taking(msg, player_info_parsed)
        self._parse_taking_fail(msg, player_info_parsed)
        self._taking_success(msg, player_info_parsed)
        self._parse_sum_stat_top(msg, player_info_parsed)
        self._parse_notebook(msg, player_info_parsed)
        self._parse_dome(msg, player_info_parsed)
        self._parse_stock(msg, player_info_parsed)
        self._parse_food(msg, player_info_parsed)
        self._parse_stuff(msg, player_info_parsed)
        self._parse_boss_fight(msg, player_info_parsed)
        self._parse_pokemob(msg, player_info_parsed)
        self._parse_scuffle(msg, player_info_parsed)
        self._parse_lynch(msg, player_info_parsed)
        self.event_manager.invoke_handler_update(player_info_parsed)

        self._parse_gang(msg, group_info_parsed)
        self._parse_goat(msg, group_info_parsed)
        self.event_manager.invoke_handler_update(group_info_parsed)

    @inner_update(PlayerParseResult)
    @get_player
    def _photo(self, update: PlayerParseResult, *args, **kwargs):
        player_info_parsed = update
        msg = update.telegram_update.message

        self._photo_meeting(msg, player_info_parsed)
        self.event_manager.invoke_handler_update(player_info_parsed)
