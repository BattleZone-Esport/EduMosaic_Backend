from sqlalchemy import (
    Boolean, Index, Column, Integer, String, Text, JSON, DateTime,
    ForeignKey, UniqueConstraint, Float, Table, Enum, ARRAY, CheckConstraint,
    BigInteger, Numeric, Date
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from database import Base
import enum
import re
from datetime import datetime, timedelta
import uuid

# ==================== ENHANCED ENUMS ==================== #

class DifficultyLevel(enum.Enum):
    BEGINNER = "beginner"      # School level
    EASY = "easy"              # High school
    MEDIUM = "medium"          # Undergraduate
    HARD = "hard"              # Graduate
    EXPERT = "expert"          # Professional
    MASTER = "master"          # Subject matter expert

class QuestionType(enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANKS = "fill_blanks"
    MATCHING = "matching"
    SEQUENCE = "sequence"
    IMAGE_BASED = "image_based"
    AUDIO_BASED = "audio_based"
    VIDEO_BASED = "video_based"
    CODING = "coding"           # For programming quizzes
    ESSAY = "essay"             # For descriptive answers

class BadgeType(enum.Enum):
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    SPECIAL = "special"
    LEGENDARY = "legendary"

class UserRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    CONTENT_CREATOR = "content_creator"
    PREMIUM_USER = "premium_user"
    USER = "user"
    GUEST = "guest"

class ExamType(enum.Enum):
    UPSC = "upsc"
    SSC = "ssc"
    BANKING = "banking"
    RAILWAYS = "railways"
    DEFENSE = "defense"
    STATE_PSC = "state_psc"
    ENGINEERING = "engineering"
    MEDICAL = "medical"
    LAW = "law"
    SCHOOL = "school"
    UNIVERSITY = "university"
    COMPETITIVE = "competitive"
    SKILL_DEVELOPMENT = "skill_development"

class Language(enum.Enum):
    ENGLISH = "en"
    HINDI = "hi"
    BENGALI = "bn"
    TELUGU = "te"
    MARATHI = "mr"
    TAMIL = "ta"
    URDU = "ur"
    GUJARATI = "gu"
    KANNADA = "kn"
    ODIA = "or"
    PUNJABI = "pa"
    MALAYALAM = "ml"
    ASSAMESE = "as"
    MAITHILI = "mai"
    SANTALI = "sat"
    KASHMIRI = "ks"
    NEPALI = "ne"
    SINDHI = "sd"
    KONKANI = "kok"
    MANIPURI = "mni"
    DOGRI = "doi"
    BODO = "brx"
    SANSKRIT = "sa"

# ==================== ASSOCIATION TABLES ==================== #

quiz_tags = Table(
    'quiz_tags', Base.metadata,
    Column('quiz_id', Integer, ForeignKey('quizzes.id', ondelete='CASCADE')),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'))
)

user_categories = Table(
    'user_categories', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('category_id', Integer, ForeignKey('categories.id', ondelete='CASCADE'))
)

quiz_exam_types = Table(
    'quiz_exam_types', Base.metadata,
    Column('quiz_id', Integer, ForeignKey('quizzes.id', ondelete='CASCADE')),
    Column('exam_type', Enum(ExamType))
)

# ==================== ENHANCED MODELS ==================== #

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    username = Column(String(50), unique=True, index=True, nullable=True)
    phone_number = Column(String(15), unique=True, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    avatar_public_id = Column(String(100), nullable=True)
    
    # Progress & Stats
    xp = Column(BigInteger, default=0, index=True)
    level = Column(Integer, default=1, index=True)
    coins = Column(BigInteger, default=0)
    gems = Column(Integer, default=0)  # Premium currency
    streak = Column(Integer, default=0, index=True)
    max_streak = Column(Integer, default=0)
    daily_goal = Column(Integer, default=10)
    weekly_goal = Column(Integer, default=50)
    
    # Premium Features
    is_premium = Column(Boolean, default=False, index=True)
    premium_plan = Column(String(20), nullable=True)
    premium_expiry = Column(DateTime, nullable=True)
    premium_features = Column(JSON, default=lambda: {
        "ad_free": False,
        "unlimited_practice": False,
        "detailed_analytics": False,
        "priority_support": False,
        "exclusive_content": False
    })
    
    # Referral System
    referral_code = Column(String(20), unique=True, nullable=True)
    referred_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    referral_count = Column(Integer, default=0)
    
    # Account Status
    role = Column(Enum(UserRole), default=UserRole.USER, index=True)
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    is_content_creator = Column(Boolean, default=False)
    
    # Timestamps
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    last_daily_reward = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Enhanced Relationships
    scores = relationship("UserScore", back_populates="user", cascade="all, delete-orphan")
    reattempts = relationship("QuizReattempt", back_populates="user", cascade="all, delete-orphan")
    badges = relationship("UserBadge", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    # Social Features
    followers = relationship("Follow", foreign_keys="Follow.followed_id", back_populates="followed")
    following = relationship("Follow", foreign_keys="Follow.follower_id", back_populates="follower")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    # Content
    created_quizzes = relationship("Quiz", back_populates="creator")
    liked_quizzes = relationship("QuizLike", back_populates="user")
    reported_issues = relationship("ReportedIssue", back_populates="user")
    category_preferences = relationship("Category", secondary=user_categories, back_populates="users")
    
    # Learning
    learning_progress = relationship("UserLearningProgress", back_populates="user", cascade="all, delete-orphan")
    daily_challenges = relationship("UserDailyChallenge", back_populates="user")
    tournament_participations = relationship("TournamentParticipant", back_populates="user")
    
    # Referrals
    referrals_sent = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    referrals_received = relationship("Referral", foreign_keys="Referral.referred_id", back_populates="referred")
    
    # Study Groups
    study_groups = relationship("StudyGroupMember", back_populates="user")
    created_study_groups = relationship("StudyGroup", back_populates="creator")

    __table_args__ = (
        CheckConstraint('xp >= 0', name='check_xp_positive'),
        CheckConstraint('coins >= 0', name='check_coins_positive'),
        CheckConstraint('gems >= 0', name='check_gems_positive'),
        CheckConstraint('streak >= 0', name='check_streak_positive'),
        Index('ix_users_xp_level', 'xp', 'level'),
    )

    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError('Invalid email format')
        return email

    @validates('phone_number')
    def validate_phone(self, key, phone_number):
        if phone_number and not re.match(r'^\+?[1-9]\d{1,14}$', phone_number):
            raise ValueError('Invalid phone number format')
        return phone_number

    def generate_referral_code(self):
        if not self.referral_code:
            self.referral_code = str(uuid.uuid4())[:8].upper()

class QuizReattempt(Base):
    __tablename__ = "quiz_reattempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"))
    session_id = Column(String(50), nullable=False)
    
    # Performance Metrics
    score = Column(Integer, default=0)
    total_questions = Column(Integer)
    correct_answers = Column(Integer)
    accuracy = Column(Float)
    time_taken = Column(Integer)  # in seconds
    question_wise_time = Column(JSON)  # {question_id: time_taken}
    
    # Detailed Analysis
    weak_areas = Column(JSON)  # {category: accuracy_percentage}
    time_management_score = Column(Float)
    accuracy_consistency = Column(Float)
    
    # Progress Tracking
    improvement_percentage = Column(Float)  # Compared to previous attempt
    rank_percentile = Column(Float)
    
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="reattempts")
    quiz = relationship("Quiz")

    __table_args__ = (
        UniqueConstraint("user_id", "quiz_id", "session_id", name="uq_user_quiz_session"),
        CheckConstraint('score >= 0', name='check_score_positive'),
        CheckConstraint('accuracy >= 0 AND accuracy <= 100', name='check_accuracy_range'),
        Index('ix_reattempts_user_quiz', 'user_id', 'quiz_id'),
    )

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    icon_url = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    
    # Hierarchy
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    level = Column(Integer, default=0)  # 0: Main, 1: Sub, 2: Topic
    
    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0)
    exam_types = Column(ARRAY(Enum(ExamType)))  # Which exams this category is relevant for
    difficulty_range = Column(JSON)  # {min: "beginner", max: "expert"}
    
    # Statistics
    total_quizzes = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    avg_difficulty = Column(Float, default=0.0)
    popularity_score = Column(Float, default=0.0)

    # Relationships
    quizzes = relationship("Quiz", back_populates="category", cascade="all, delete-orphan")
    users = relationship("User", secondary=user_categories, back_populates="category_preferences")
    children = relationship("Category", backref="parent")
    study_materials = relationship("StudyMaterial", back_populates="category")

    __table_args__ = (
        Index('ix_categories_exam_types', 'exam_types', postgresql_using='gin'),
    )

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text)
    short_description = Column(String(300))
    
    # Category & Type
    category_id = Column(Integer, ForeignKey("categories.id"))
    exam_types = Column(ARRAY(Enum(ExamType)))
    language = Column(Enum(Language), default=Language.ENGLISH)
    
    # Difficulty & Structure
    difficulty = Column(Enum(DifficultyLevel), index=True)
    time_limit = Column(Integer)  # seconds
    question_count = Column(Integer, default=10)
    estimated_completion_time = Column(Integer)  # minutes
    
    # Rewards
    xp_reward = Column(Integer, default=10)
    coin_reward = Column(Integer, default=5)
    gem_reward = Column(Integer, default=0)
    
    # Access Control
    is_active = Column(Boolean, default=True, index=True)
    is_premium = Column(Boolean, default=False, index=True)
    is_featured = Column(Boolean, default=False, index=True)
    is_verified = Column(Boolean, default=False)
    access_level = Column(Integer, default=0)  # 0: Public, 1: Subscribers, 2: Premium
    
    # Creator Info
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Media
    cover_image = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    promo_video_url = Column(String(500), nullable=True)
    
    # Statistics
    plays_count = Column(Integer, default=0, index=True)
    likes_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    avg_score = Column(Float, default=0.0)
    avg_completion_time = Column(Float, default=0.0)
    completion_rate = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Enhanced Relationships
    category = relationship("Category", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    creator = relationship("User", back_populates="created_quizzes")
    tags = relationship("Tag", secondary=quiz_tags, back_populates="quizzes")
    likes = relationship("QuizLike", back_populates="quiz")
    reports = relationship("ReportedIssue", back_populates="quiz")
    exam_type_associations = relationship("QuizExamType", back_populates="quiz")
    study_materials = relationship("StudyMaterial", back_populates="quiz")
    
    # Learning Path Integration
    learning_path_steps = relationship("LearningPathStep", back_populates="quiz")
    
    # Tournament Integration
    tournaments = relationship("Tournament", back_populates="quiz")

    __table_args__ = (
        CheckConstraint('question_count > 0', name='check_question_count_positive'),
        CheckConstraint('time_limit > 0', name='check_time_limit_positive'),
        Index('ix_quizzes_difficulty_category', 'difficulty', 'category_id'),
        Index('ix_quizzes_exam_types', 'exam_types', postgresql_using='gin'),
    )

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"))
    
    # Content
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), default=QuestionType.MULTIPLE_CHOICE)
    explanation = Column(Text)
    detailed_solution = Column(Text)
    
    # Media
    image_url = Column(String(500), nullable=True)
    audio_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    diagram_url = Column(String(500), nullable=True)
    
    # Difficulty & Scoring
    difficulty = Column(Enum(DifficultyLevel), default=DifficultyLevel.MEDIUM, index=True)
    points = Column(Integer, default=1)
    time_limit = Column(Integer, nullable=True)  # Individual question time limit
    sort_order = Column(Integer, default=0)
    
    # Learning Aids
    hint = Column(Text)
    learning_tips = Column(Text)
    common_mistakes = Column(Text)
    related_concepts = Column(ARRAY(String))
    
    # Advanced Features
    has_negative_marking = Column(Boolean, default=False)
    negative_mark_percentage = Column(Float, default=0.25)
    partial_scoring = Column(Boolean, default=False)
    adaptive_difficulty = Column(Boolean, default=False)
    
    # Statistics
    accuracy_rate = Column(Float, default=0.0)
    average_time = Column(Float, default=0.0)
    discrimination_index = Column(Float, default=0.0)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Enhanced Relationships
    quiz = relationship("Quiz", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")
    question_tags = relationship("QuestionTag", back_populates="question")
    difficulty_history = relationship("QuestionDifficultyHistory", back_populates="question")

    __table_args__ = (
        CheckConstraint('points >= 0', name='check_points_positive'),
        CheckConstraint('negative_mark_percentage >= 0 AND negative_mark_percentage <= 1', 
                       name='check_negative_mark_range'),
    )

class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, index=True)
    image_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0)
    
    # Advanced Features
    partial_score = Column(Float, default=0.0)  # For partial scoring
    explanation = Column(Text)  # Why this option is correct/incorrect
    common_choice = Column(Boolean, default=False)  # Frequently chosen incorrect option
    
    question = relationship("Question", back_populates="options")

    __table_args__ = (
        CheckConstraint('partial_score >= 0 AND partial_score <= 1', name='check_partial_score_range'),
    )

# ==================== NEW MODELS FOR ENHANCED FEATURES ==================== #

class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    material_type = Column(String(20))  # pdf, video, article, notes, formula_sheet
    file_url = Column(String(500))
    thumbnail_url = Column(String(500))
    duration = Column(Integer)  # in minutes for videos
    
    category_id = Column(Integer, ForeignKey("categories.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=True)
    
    # Metadata
    difficulty = Column(Enum(DifficultyLevel))
    language = Column(Enum(Language), default=Language.ENGLISH)
    is_free = Column(Boolean, default=True)
    download_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))