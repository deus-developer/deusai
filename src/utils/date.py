import datetime


def from_utc_date(date: datetime.datetime) -> datetime.datetime:
    return date.astimezone()
