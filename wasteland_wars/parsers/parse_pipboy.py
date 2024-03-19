import re
from typing import Optional, Match

from telegram import Message

from wasteland_wars.schemas import Profile, PipboyStats
from wasteland_wars.utils import get_fraction_by_name

re_profile = re.compile(
    r'\n(?P<nic>[^\n]*),\s*(?P<fraction>[^\n]*)\s+'
    r'(🤟Банда:\s+(?P<crew>[^\n]*)\s+)?'
    r'❤️Здоровье:\s+(?P<hp_now>\d+)/(?P<hp>\d+)\s+'
    r'☠️Голод:\s+(?P<hunger>\d+)%\s*/myfood\s+'
    r'⚔️Урон:\s+(?P<attack>\d+)(\s*\([^)]*\))?\s*'
    r'🛡Броня:\s+(?P<armor>\d+)(\s*\([^)]*\))?\s*'
    r'💪Сила:\s+(?P<power>\d+)(\s*\([^)]*\))?\s*'
    r'🎯Меткость:\s+(?P<accuracy>\d+)(\s*\([^)]*\))?\s*'
    r'🗣Харизма:\s+(?P<oratory>\d+)(\s*\([^)]*\))?\s*'
    r'🤸🏽‍♂️Ловкость:\s+(?P<agility>\d+)(\s*\([^)]*\))?[\s\S]+'
    r'🔋Выносливость:\s+(?P<stamina_now>\d+)/(?P<stamina>\d+)\s*/ref\s+'
    r'📍(?P<location>[^\n]*),\s*👣\s*(?P<distance>\d+)км\.\s*(?P<on_raid>👊)?'
)

re_profile_short = re.compile(
    r'👤(?P<nic>[^\n]*?)(?:(?P<dzen>[🏵\d+|🏵+]*))?\n'
    r'├🤟 (?P<crew>[^\n]*)\n'
    r'├(?P<fraction>[^\n]*)\n'
    r'├❤️(?P<hp_now>[\d]+)/(?P<hp>[\d]+)[^\d]+(?P<hunger>[\d]+)[^\d]+'
    r'(?P<attack>[\d]+)[^\d]+[^\d]*(?P<armor>[\d]+)[^\d]+'
    r'(?P<power>[\d]+)[^\d]+[^\d]*(?P<accuracy>[\d]+)[^\d]+'
    r'(?P<oratory>[\d]+)[^\d]+(?P<agility>[\d]+)[^\d]+'
    r'(?P<stamina_now>[\d]+)/(?P<stamina>[\d]+)[^\d]+'
    r'👣(?P<distance>[\d]+)\n├🔥(?P<location>[^\n]+)'
)

telegram_user_id_regex = re.compile(r'ID(?P<user_id>\d+)')
dzen_regex = re.compile(r'(🏵(\d+)|🏵+)')
dzen_bars_regex = re.compile(r'[▓░]')


def get_dzen_from_match(
    match: Match,
    dzen_match: Match,
    dzen_bars_match: Match
) -> int:
    dzen = 0
    try:
        dzen = match.group('dzen') or 0  # Короткий профиль
    except IndexError:
        if dzen_match:
            dzen = dzen_match.group(0) or 0

    if isinstance(dzen, str):
        if dzen.endswith('🏵'):  # 1-3
            dzen = len(dzen)
        else:
            dzen = int(dzen.strip('🏵'))

    if dzen_bars_match:
        dzen -= 1

    return dzen


def parse_pipboy(message: Message) -> Optional[Profile]:
    match = re_profile.search(message.text) or re_profile_short.search(message.text)
    if not match:
        return

    startpos = match.end()

    if user_id_match := telegram_user_id_regex.search(message.text, startpos):
        telegram_user_id = user_id_match.group('user_id')
    else:
        telegram_user_id = None

    dzen_match = dzen_regex.search(message.text, startpos)
    dzen_bars_match = dzen_bars_regex.search(message.text, startpos)

    nickname, crew, location = match.group('nic', 'crew', 'location')
    fraction = get_fraction_by_name(match.group('fraction'))

    attack, armor, power, accuracy, oratory, agility, stamina = match.group(
        'attack',
        'armor',
        'power',
        'accuracy',
        'oratory',
        'agility',
        'stamina'
    )
    hp, hp_now, hunger, stamina_now, distance = match.group(
        'hp',
        'hp_now',
        'hunger',
        'stamina_now',
        'distance'
     )

    dzen = get_dzen_from_match(match, dzen_match, dzen_bars_match)
    stats = PipboyStats(
        hp=hp,
        stamina=stamina,
        agility=agility,
        oratory=oratory,
        accuracy=accuracy,
        power=power,
        attack=attack,
        defence=armor,
        dzen=dzen,
        time=message.forward_date
    )

    stand_on_raid = False
    try:
        if match.group('on_raid'):
            stand_on_raid = True
    except IndexError:
        pass

    pipboy = Profile(
        nickname=nickname,
        fraction=fraction,
        gang_name=crew,
        stats=stats,

        hp_now=hp_now,
        stamina_now=stamina_now,
        hunger=hunger,
        distance=distance,
        location=location,

        telegram_user_id=telegram_user_id,
        stand_on_raid=stand_on_raid
    )
    return pipboy
