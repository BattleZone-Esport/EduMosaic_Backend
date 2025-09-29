"""
User model for EduMosaic
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, Enum
from sqlalchemy.sql import func
from app.db.database import Base
import enum

class UserRole(enum.Enum):
    """User roles"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"
    MODERATOR = "moderator"

class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    role = Column(Enum(UserRole), default=UserRole.STUDENT)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    phone_number = Column(String, nullable=True)
    
    total_score = Column(Integer, default=0)
    quizzes_taken = Column(Integer, default=0)
    average_score = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
