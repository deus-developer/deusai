import re
from typing import Optional, List

from telegram import Message

from wasteland_wars.schemas import GangPanel, GangMember

goat_panel_regex = re.compile(
    r'^🤘\s+(?P<gang_name>.+)\s+🏅(?P<ears>\d+)\n'
    r'Панель банды\.\n\n'

    r'Главарь\n'
    r'⚜️\s+(?P<leader_nickname>.+)\n\n'

    r'Козёл\n'
    r'🐐\s+(?P<goat_name>.+)\s+/goat\n\n'

    r'Участники\s+\((?P<members_count>\d+)/(?P<available_members_count>\d+)\)'
)
gang_member_regex = re.compile(
    r'(.{1,2})\s+'
    r'(?P<nickname>.+)'
    r'👂(?P<ears>\d+)\s+'
    r'(?P<state>.)(?P<kilometr>\d+)km'
)


def parse_gang_panel(message: Message) -> Optional[GangPanel]:
    if not (match := goat_panel_regex.search(message.text)):
        return

    gang_name, leader_nickname, goat_name, gang_ears, members_count, available_members_count = match.group(
        'gang_name',
        'leader_nickname',
        'goat_name',
        'ears',
        'members_count',
        'available_members_count'
    )

    startpos = match.end()

    members: List[GangMember] = []
    for match in gang_member_regex.finditer(message.text, startpos + 1):
        nickname, state, ears, kilometr = match.group(
            'nickname',
            'state',
            'ears',
            'kilometr'
        )

        members.append(GangMember(
            nickname=nickname,
            ears=ears,
            kilometr=kilometr,
            status=state
        ))

    gang_panel = GangPanel(
        name=gang_name,
        ears=gang_ears,
        leader_nickname=leader_nickname,
        goat_name=goat_name,
        members=members
    )
    return gang_panel
