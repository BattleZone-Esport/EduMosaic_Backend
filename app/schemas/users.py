"""User schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class UserFilter(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
