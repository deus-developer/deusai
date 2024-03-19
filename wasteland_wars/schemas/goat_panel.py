from typing import List, Optional

from pydantic import BaseModel


class GoatGangMember(BaseModel):
    gang_name: str
    combat_power: int
    gang_id: Optional[int]


class GoatPanel(BaseModel):
    name: str
    league_name: str
    rating: int

    leader_nickname: str

    gangs_count: int
    gangs_available_count: int

    gangs: List[GoatGangMember]

    raid_combat_power: int
    combat_power: int
