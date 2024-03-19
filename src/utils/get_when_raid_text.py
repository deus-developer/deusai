import datetime
import math
from typing import Optional

from src.utils import get_next_raid_date


def get_when_raid_text(date: Optional[datetime.datetime] = None) -> str:
    next_raid_time = get_next_raid_date(date)
    seconds = math.ceil((next_raid_time - datetime.datetime.now()).total_seconds())

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds %= 60

    text = (
        f"Скоро рейд в <b>{next_raid_time.hour}:00</b> мск\n"
        f"Т.е. через <b>{hours:.0f}</b> ч <b>{minutes:.0f}</b> мин <b>{seconds:.0f}</b> сек"
    )

    return text
