from pydantic import BaseModel


class ShowData(BaseModel):
    enabled: bool
