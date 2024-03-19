import datetime

from pydantic import BaseModel


class RaidReward(BaseModel):
    time: datetime.datetime
