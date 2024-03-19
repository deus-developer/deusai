import re
from typing import Optional

from telegram import Message

from src.wasteland_wars.schemas import ShowData

showdata_regex = re.compile(r"Доступ\s+к\s+данным\s+(?P<status>.+)")


def parse_showdata(message: Message) -> Optional[ShowData]:
    if not (match := showdata_regex.search(message.text)):
        return

    showdata_enabled = match.group("status") == "✅"
    showdata = ShowData(enabled=showdata_enabled)
    return showdata
