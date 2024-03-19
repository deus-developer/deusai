import datetime
from typing import Optional

from pydantic import BaseModel

from src.wasteland_wars.enums import Fraction


class PipboyStats(BaseModel):
    hp: int
    stamina: int
    agility: int
    oratory: int
    accuracy: int
    power: int
    attack: int
    defence: int
    dzen: int

    time: datetime.datetime


class Profile(BaseModel):
    nickname: str
    fraction: Fraction
    gang_name: Optional[str]
    stats: PipboyStats

    hp_now: int
    stamina_now: int
    hunger: int
    distance: int
    location: str

    telegram_user_id: Optional[int]
    stand_on_raid: bool
