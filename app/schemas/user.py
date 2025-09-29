"""
User schemas for EduMosaic
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.models.user import UserRole

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)

class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    """User update schema"""
    full_name: Optional[str] = None
    bio: Optional[str] = None
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None

class UserResponse(UserBase):
    """User response schema"""
    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str]
    bio: Optional[str]
    total_score: int
    quizzes_taken: int
    average_score: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    """User login schema"""
    username: str
    password: str

class Token(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Token data schema"""
    username: Optional[str] = None
    user_id: Optional[int] = None
