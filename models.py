from database import Base
from sqlalchemy import (
    Boolean, Index, Column, Integer, String, Text, JSON, DateTime,
    ForeignKey, UniqueConstraint, Float, Table, Enum, ARRAY, CheckConstraint,
    BigInteger, Numeric, Date, LargeBinary
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
import enum
import re
from datetime import datetime, timedelta
import uuid
import secrets
class Language(str, enum.Enum):
    ENGLISH = "english"
    HINDI = "hindi"
    TAMIL = "tamil"
    TELUGU = "telugu"
    MARATHI = "marathi"
    BENGALI = "bengali"
    GUJARATI = "gujarati"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"
    PUNJABI = "punjabi"
    ORIYA = "oriya"
    ASSAMESE = "assamese"
    URDU = "urdu"
    OTHER = "other"
# ==================== ENHANCED ENUMS ==================== #
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
    TEACHING = "teaching"
    MBA = "mba"
    GOVERNMENT_JOB = "government_job"
    COMPUTER = "computer"

class QuestionType(enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANKS = "fill_blanks"
    MATCHING = "matching"
    SEQUENCE = "sequence"
    IMAGE_BASED = "image_based"
    AUDIO_BASED = "audio_based"
    VIDEO_BASED = "video_based"
    CODING = "coding"
    ESSAY = "essay"
    CASE_STUDY = "case_study"
    DATA_INTERPRETATION = "data_interpretation"
    REASONING = "reasoning"
    APTITUDE = "aptitude"

class DifficultyLevel(enum.Enum):
    BEGINNER = "beginner"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"
    MASTER = "master"
    EXAM_SPECIFIC = "exam_specific"  # For exam-specific difficulty

class BadgeType(enum.Enum):
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    SPECIAL = "special"
    LEGENDARY = "legendary"
    EXAM_SPECIALIST = "exam_specialist"  # For exam-specific achievements

class UserRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    CONTENT_CREATOR = "content_creator"
    PREMIUM_USER = "premium_user"
    USER = "user"
    GUEST = "guest"
    EXAM_EXPERT = "exam_expert"  # For subject matter experts

class ExamCategory(Base):
    __tablename__ = "exam_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    icon_url = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    # Exam-specific details
    exam_type = Column(Enum(ExamType), nullable=False)
    exam_pattern = Column(JSON)  # {"tier_1": {"time_limit": 60, "questions": 100}, "tier_2": {"time_limit": 120, "questions": 200}}
    syllabus = Column(JSON)  # {"section_1": "General Awareness", "section_2": "Quantitative Aptitude"}
    previous_years = Column(ARRAY(Integer))  # Array of previous year exam IDs
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Relationships
    quizzes = relationship("Quiz", back_populates="exam_category")

# ==================== CORE MODELS ==================== #
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
    location = Column(String(255), nullable=True)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(100), nullable=True)
    # Exam preferences
    exam_preferences = Column(ARRAY(Enum(ExamType)), nullable=True)
    # Progress & Stats
    xp = Column(BigInteger, default=0, index=True)
    level = Column(Integer, default=1, index=True)
    coins = Column(BigInteger, default=0)
    gems = Column(Integer, default=0)  # Premium currency
    streak = Column(Integer, default=0, index=True)
    max_streak = Column(Integer, default=0)
    daily_goal = Column(Integer, default=10)
    weekly_goal = Column(Integer, default=50)
    last_daily_reward = Column(Date, nullable=True)
    # Premium Features
    is_premium = Column(Boolean, default=False, index=True)
    premium_plan = Column(String(20), nullable=True)
    premium_expiry = Column(DateTime, nullable=True)
    premium_features = Column(JSON, default=lambda: {
        "ad_free": False,
        "unlimited_practice": False,
        "detailed_analytics": False,
        "priority_support": False,
        "exclusive_content": False,
        "offline_access": False,
        "exam_simulator": False
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Relationships
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
    category_preferences = relationship("Category", secondary="user_categories", back_populates="users")
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
    # Exam-specific
    exam_preferences = relationship("ExamPreference", back_populates="user")
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
            self.referral_code = secrets.token_urlsafe(8).upper()

class ExamPreference(Base):
    __tablename__ = "exam_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exam_category_id = Column(Integer, ForeignKey("exam_categories.id"))
    preference_level = Column(Integer, default=1)  # 1-5 scale
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="exam_preferences")
    exam_category = relationship("ExamCategory")

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
    users = relationship("User", secondary="user_categories", back_populates="category_preferences")
    children = relationship("Category", backref="parent")
    study_materials = relationship("StudyMaterial", back_populates="category")
    __table_args__ = (
        Index('ix_categories_exam_types', 'exam_types', postgresql_using='gin'),
    )

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text)
    color_code = Column(String(7), default="#3B82F6")  # Hex color
    icon = Column(String(50), nullable=True)
    # Categorization
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_system_tag = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Relationships
    quizzes = relationship("Quiz", secondary="quiz_tags", back_populates="tags")
    questions = relationship("QuestionTag", back_populates="tag")
    __table_args__ = (
        Index('ix_tags_category', 'category_id'),
    )

class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"))
    followed_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    followed = relationship("User", foreign_keys=[followed_id], back_populates="followers")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200))
    message = Column(Text)
    is_read = Column(Boolean, default=False)
    type = Column(String(50))
    data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="notifications")

class ReportedIssue(Base):
    __tablename__ = "reported_issues"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    issue_type = Column(String(50))
    description = Column(Text)
    status = Column(String(50), default="open")
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="reported_issues")
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=True)
    quiz = relationship("Quiz", back_populates="reports")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    jti = Column(String(36), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="refresh_tokens")

class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    points = Column(Integer, default=0)
    target_value = Column(Integer, nullable=True)
    icon_url = Column(String(500), nullable=True)
    exam_type = Column(Enum(ExamType), nullable=True)  # Exam-specific achievement
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    progress = Column(Float, default=0.0)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement")

class UserLearningProgress(Base):
    __tablename__ = "user_learning_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    level = Column(Integer, default=1)
    completed_quizzes = Column(Integer, default=0)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="learning_progress")
    category = relationship("Category")

class UserDailyChallenge(Base):
    __tablename__ = "user_daily_challenges"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    challenge_id = Column(Integer)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="daily_challenges")

class Referral(Base):
    __tablename__ = "referrals"
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"))
    referred_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_sent")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="referrals_received")

class StudyGroup(Base):
    __tablename__ = "study_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    creator_id = Column(Integer, ForeignKey("users.id"))
    member_count = Column(Integer, default=1)
    invite_code = Column(String(8), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    category = relationship("Category")
    creator = relationship("User", back_populates="created_study_groups")
    members = relationship("StudyGroupMember", back_populates="group")

class StudyGroupMember(Base):
    __tablename__ = "study_group_members"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String(50), default="member")
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    group = relationship("StudyGroup", back_populates="members")
    user = relationship("User", back_populates="study_groups")

class LearningPathStep(Base):
    __tablename__ = "learning_path_steps"
    id = Column(Integer, primary_key=True, index=True)
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    order = Column(Integer, default=0)
    learning_path = relationship("LearningPath", back_populates="steps")
    quiz = relationship("Quiz")

class LearningPath(Base):
    __tablename__ = "learning_paths"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    category = relationship("Category")
    creator = relationship("User")
    steps = relationship("LearningPathStep", back_populates="learning_path")

class Tournament(Base):
    __tablename__ = "tournaments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    category = relationship("Category")
    quiz = relationship("Quiz", back_populates="tournaments")
    participants = relationship("TournamentParticipant", back_populates="tournament")

class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Integer, default=0)
    rank = Column(Integer, default=0)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    tournament = relationship("Tournament", back_populates="participants")
    user = relationship("User", back_populates="tournament_participations")

# ==================== ASSOCIATION TABLES ==================== #
quiz_tags = Table(
    'quiz_tags', Base.metadata,
    Column('quiz_id', Integer, ForeignKey('quizzes.id', ondelete='CASCADE')),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE')),
    Index('ix_quiz_tags_quiz_id', 'quiz_id'),
    Index('ix_quiz_tags_tag_id', 'tag_id')
)

user_categories = Table(
    'user_categories', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('category_id', Integer, ForeignKey('categories.id', ondelete='CASCADE')),
    UniqueConstraint('user_id', 'category_id', name='uq_user_category'),
    Index('ix_user_categories_user_id', 'user_id'),
    Index('ix_user_categories_category_id', 'category_id')
)

quiz_exam_types = Table(
    'quiz_exam_types', Base.metadata,
    Column('quiz_id', Integer, ForeignKey('quizzes.id', ondelete='CASCADE')),
    Column('exam_type', Enum(ExamType)),
    Index('ix_quiz_exam_types_quiz_id', 'quiz_id')
)

# ==================== QUIZ & QUESTION MODELS ==================== #
class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text)
    short_description = Column(String(300))
    # Category & Type
    category_id = Column(Integer, ForeignKey("categories.id"))
    exam_category_id = Column(Integer, ForeignKey("exam_categories.id"))
    exam_types = Column(ARRAY(Enum(ExamType)))
    language = Column(Enum(Language), default=Language.ENGLISH)
    # Difficulty & Structure
    difficulty = Column(Enum(DifficultyLevel), index=True)
    time_limit = Column(Integer)  # seconds
    question_count = Column(Integer, default=10)
    estimated_completion_time = Column(Integer)  # minutes
    # Exam-specific features
    is_exam_simulator = Column(Boolean, default=False)
    exam_pattern = Column(JSON)  # {"tier_1": {"time_limit": 60, "questions": 100}, "tier_2": {"time_limit": 120, "questions": 200}}
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
    exam_category = relationship("ExamCategory", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    creator = relationship("User", back_populates="created_quizzes")
    tags = relationship("Tag", secondary=quiz_tags, back_populates="quizzes")
    likes = relationship("QuizLike", back_populates="quiz")
    reports = relationship("ReportedIssue", back_populates="quiz")
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
    # Exam-specific
    exam_pattern = Column(JSON)  # {"tier_1": {"time_limit": 60, "questions": 100}, "tier_2": {"time_limit": 120, "questions": 200}}
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

class QuestionTag(Base):
    __tablename__ = "question_tags"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"))
    relevance_score = Column(Float, default=1.0)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    question = relationship("Question", back_populates="question_tags")
    tag = relationship("Tag", back_populates="questions")
    __table_args__ = (
        UniqueConstraint('question_id', 'tag_id', name='uq_question_tag'),
        Index('ix_question_tags_question_id', 'question_id'),
        Index('ix_question_tags_tag_id', 'tag_id'),
    )

# ==================== ENHANCED FEATURES MODELS ==================== #
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
    category = relationship("Category", back_populates="study_materials")
    quiz = relationship("Quiz", back_populates="study_materials")

# ==================== ADDITIONAL ENHANCED MODELS ==================== #
class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String)  # in_progress, completed, abandoned
    score = Column(Float, default=0)
    accuracy = Column(Float, default=0)
    time_taken = Column(Integer, default=0)
    # Exam-specific
    exam_tier = Column(String(50), nullable=True)  # For multi-tier exams like UPSC

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String)
    event_data = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)

class UserScore(Base):
    __tablename__ = "user_scores"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"))
    score = Column(Integer, default=0)
    total_questions = Column(Integer)
    correct_answers = Column(Integer)
    accuracy = Column(Float)
    time_taken = Column(Integer)
    rank = Column(Integer)
    percentile = Column(Float)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="scores")
    quiz = relationship("Quiz")
    __table_args__ = (
        Index('ix_user_scores_user_quiz', 'user_id', 'quiz_id'),
        Index('ix_user_scores_completed_at', 'completed_at'),
    )

class QuizLike(Base):
    __tablename__ = "quiz_likes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="liked_quizzes")
    quiz = relationship("Quiz", back_populates="likes")
    __table_args__ = (
        UniqueConstraint('user_id', 'quiz_id', name='uq_user_quiz_like'),
    )

class UserBadge(Base):
    __tablename__ = "user_badges"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    badge_type = Column(Enum(BadgeType))
    title = Column(String(100))
    description = Column(Text)
    icon_url = Column(String(500))
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="badges")
    __table_args__ = (
        Index('ix_user_badges_user_id', 'user_id'),
    )

class QuestionDifficultyHistory(Base):
    __tablename__ = "question_difficulty_history"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    old_difficulty = Column(Enum(DifficultyLevel))
    new_difficulty = Column(Enum(DifficultyLevel))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    question = relationship("Question", back_populates="difficulty_history")

# ==================== FINAL OPTIMIZATIONS ==================== #
# Add indexes for better performance
Index('ix_users_email', User.email)
Index('ix_users_username', User.username)
Index('ix_quizzes_category_id', Quiz.category_id)
Index('ix_questions_quiz_id', Question.quiz_id)
Index('ix_options_question_id', Option.question_id)
Index('ix_quiz_reattempts_user_id', QuizReattempt.user_id)
Index('ix_user_scores_user_id', UserScore.user_id)
Index('ix_exam_categories_exam_type', ExamCategory.exam_type)
