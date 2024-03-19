import datetime
import re
from typing import Optional

from telegram import Message

from src.wasteland_wars.schemas import RaidReward

raid_reward_regex = re.compile(
    r"(Рейд\s+(?P<msg>в\s+((?P<hour>\d+)|(-+)):\d+\s*((?P<day>\d+)\.(?P<month>\d+))?" r".*\n.*\n.*))"
)


def parse_raid_reward(message: Message) -> Optional[RaidReward]:
    if not (match := raid_reward_regex.search(message.text)):
        return

    hour, day, month = match.group("hour", "day", "month")
    forward_date = message.forward_date

    if hour is None:
        h = (((int(forward_date.hour) % 24) - 1) // 6) * 6 + 1
        d = 0
        if h < 0:
            h = 19
            d = -1

        date = datetime.datetime(
            year=forward_date.year,
            month=forward_date.month,
            day=forward_date.day,
            hour=h,
        ) + datetime.timedelta(days=d)
    elif day is None:
        date = datetime.datetime(
            year=forward_date.year,
            month=forward_date.month,
            day=forward_date.day,
            hour=int(hour) % 24,
        )
        if forward_date - date < -datetime.timedelta(seconds=1):
            date -= datetime.timedelta(days=1)
    else:
        date = datetime.datetime(year=forward_date.year, month=int(month), day=int(day), hour=int(hour) % 24)
        if forward_date - date < datetime.timedelta(seconds=-1):
            date = datetime.datetime(date.year - 1, date.month, date.day, date.hour)

    return RaidReward(time=date)
