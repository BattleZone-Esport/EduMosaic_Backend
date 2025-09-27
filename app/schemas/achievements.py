"""Achievement schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AchievementResponse(BaseModel):
    id: int
    name: str
    description: str
    icon_url: Optional[str]
    points: int
    unlocked_at: Optional[datetime]

    class Config:
        from_attributes = True


class BadgeResponse(BaseModel):
    id: int
    name: str
    type: str
    icon_url: Optional[str]
    awarded_at: datetime

    class Config:
        from_attributes = True
