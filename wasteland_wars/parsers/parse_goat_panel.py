import re
from typing import Optional, List

from telegram import Message

from wasteland_wars.schemas import GoatPanel, GoatGangMember

gang_in_goat_regex = re.compile(r'🤘(?P<gang_name>.+)\s+💥(?P<combat_power>\d+) (/gcr_(?P<gang_id>\d+)|🔐)')

goat_panel_regex = re.compile(
    r'🐐\s+(?P<goat_name>.+)\n'
    r'Панель\s+козла\.\n\n'
    r'🏅\s+Уровень:\s\d+\s*\n'
    r'🚩Лига:\s(?P<league_name>.+)\n'
    r'🏆 Рейтинг:\s+(?P<rating>\d+)\n\n'
    r'Лидер\n'
    r'⚜️\s+(?P<leader_nickname>.+)\n\n'
    r'Банды-участники\s+\((?P<gangs_count>\d+)/(?P<gangs_available_count>\d+)\)\s*\n'
    r'(?P<gangs>[\s\S]+)\n'
    r'🐐\s+👊\s+(?P<goat_raid_combat_power>\d+)\s+/\s+(?P<goat_combat_power>\d+)'
)


def parse_goat_panel(message: Message) -> Optional[GoatPanel]:
    if not (match := goat_panel_regex.search(message.text)):
        return

    goat_name, league_name, leader_nickname, gangs = match.group(
        'goat_name',
        'league_name',
        'leader_nickname',
        'gangs'
    )
    gangs_count, gangs_available_count, rating, goat_raid_combat_power, goat_combat_power = match.group(
        'gangs_count',
        'gangs_available_count',
        'rating',
        'goat_raid_combat_power',
        'goat_combat_power'
    )

    gangs: List[GoatGangMember] = []
    for match in gang_in_goat_regex.finditer(message.text):
        gang_name, combat_power, gang_id = match.group(
            'gang_name',
            'combat_power',
            'gang_id'
        )
        gangs.append(GoatGangMember(
            gang_name=gang_name,
            combat_power=combat_power,
            gang_id=gang_id
        ))

    goat_panel = GoatPanel(
        name=goat_name,
        league_name=league_name,
        rating=rating,

        leader_nickname=leader_nickname,

        gangs_count=gangs_count,
        gangs_available_count=gangs_available_count,

        gangs=gangs,

        raid_combat_power=goat_raid_combat_power,
        combat_power=goat_combat_power
    )
    return goat_panel
