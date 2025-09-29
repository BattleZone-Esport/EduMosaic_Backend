"""
Quiz models for EduMosaic
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import enum

class DifficultyLevel(enum.Enum):
    """Quiz difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

class QuizCategory(enum.Enum):
    """Quiz categories"""
    MATHEMATICS = "mathematics"
    SCIENCE = "science"
    HISTORY = "history"
    GEOGRAPHY = "geography"
    LITERATURE = "literature"
    TECHNOLOGY = "technology"
    SPORTS = "sports"
    GENERAL_KNOWLEDGE = "general_knowledge"
    CURRENT_AFFAIRS = "current_affairs"
    ENTERTAINMENT = "entertainment"

class Language(enum.Enum):
    """Supported languages"""
    ENGLISH = "english"
    HINDI = "hindi"
    BENGALI = "bengali"
    TAMIL = "tamil"
    TELUGU = "telugu"
    MARATHI = "marathi"
    GUJARATI = "gujarati"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"
    PUNJABI = "punjabi"

class Quiz(Base):
    """Quiz model"""
    __tablename__ = "quizzes"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(Enum(QuizCategory), nullable=False, index=True)
    difficulty = Column(Enum(DifficultyLevel), default=DifficultyLevel.MEDIUM)
    language = Column(Enum(Language), default=Language.ENGLISH)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    
    total_questions = Column(Integer, default=0)
    time_limit = Column(Integer, nullable=True)  # in seconds
    passing_score = Column(Float, default=60.0)  # percentage
    
    thumbnail_url = Column(String, nullable=True)
    tags = Column(JSON, default=list)
    
    times_taken = Column(Integer, default=0)
    average_score = Column(Float, default=0.0)
    rating = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="quiz")

class Question(Base):
    """Question model"""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    
    question_text = Column(Text, nullable=False)
    question_type = Column(String, default="multiple_choice")  # multiple_choice, true_false, fill_blank
    
    option_a = Column(String, nullable=True)
    option_b = Column(String, nullable=True)
    option_c = Column(String, nullable=True)
    option_d = Column(String, nullable=True)
    
    correct_answer = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    
    points = Column(Integer, default=10)
    time_limit = Column(Integer, nullable=True)  # seconds
    
    image_url = Column(String, nullable=True)
    hint = Column(Text, nullable=True)
    
    order_number = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions")

class QuizAttempt(Base):
    """Quiz attempt tracking"""
    __tablename__ = "quiz_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    
    score = Column(Float, nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    time_taken = Column(Integer, nullable=False)  # seconds
    
    answers = Column(JSON, nullable=True)  # Store user answers
    
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")
