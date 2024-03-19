from typing import List, Optional

from pydantic import BaseModel


class GangMember(BaseModel):
    nickname: str
    ears: int
    kilometr: int
    status: str


class GangPanel(BaseModel):
    name: str
    ears: int
    leader_nickname: str
    goat_name: Optional[str]
    members: List[GangMember]
