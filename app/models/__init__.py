"""Database models for EduMosaic Backend"""

# Import only the models that actually exist in the file
from .models import (
    Base,
    # Enums
    ExamType,
    QuestionType, 
    DifficultyLevel,
    BadgeType,
    UserRole,
    Language,
    # Core Models from actual file
    ExamCategory,
    User,
    ExamPreference,
    Category,
    Tag,
    Follow,
    Notification,
    ReportedIssue,
    RefreshToken,
    Achievement,
    UserAchievement,
    UserLearningProgress,
    UserDailyChallenge,
    Referral,
    StudyGroup,
    StudyGroupMember,
    LearningPathStep,
    LearningPath,
    Tournament,
    TournamentParticipant,
    Quiz,
    Question,
    Option,
    QuestionTag,
    QuizReattempt,
    StudyMaterial,
    QuizSession,
    AnalyticsEvent,
    UserScore,
    QuizLike,
    UserBadge,
    QuestionDifficultyHistory,
)

# Provide aliases for models expected by endpoints
LeaderboardEntry = UserScore  # Alias
UserQuizAttempt = QuizSession  # Alias
UserAnswer = QuizSession  # Temporary alias
Badge = Achievement  # Alias
UserProgress = UserLearningProgress  # Alias
DailyChallenge = UserDailyChallenge  # Alias
UserStats = UserScore  # Alias
Subject = Category  # Alias
Topic = Tag  # Alias

# These models don't exist, create placeholder classes
class UserFavorite:
    pass

class UserBookmark:
    pass

class ReportedContent:
    pass

class Feedback:
    pass

class SystemSettings:
    pass

class AuditLog:
    pass

class EmailVerification:
    pass

class PasswordReset:
    pass

class LoginHistory:
    pass

class UserSession:
    pass

class APIKey:
    pass

class RateLimitOverride:
    pass

class FeatureFlag:
    pass

class UserFeatureFlag:
    pass

class UserStreak:
    pass

class Announcement:
    pass

class UserAnnouncementRead:
    pass

class QuizReport:
    pass

class UserQuizReport:
    pass

__all__ = [
    "Base",
    # Enums
    "ExamType",
    "QuestionType",
    "DifficultyLevel",
    "BadgeType",
    "UserRole",
    "Language",
    # Actual Models
    "ExamCategory",
    "User",
    "ExamPreference",
    "Category",
    "Tag",
    "Follow",
    "Notification",
    "ReportedIssue",
    "RefreshToken",
    "Achievement",
    "UserAchievement",
    "UserLearningProgress",
    "UserDailyChallenge",
    "Referral",
    "StudyGroup",
    "StudyGroupMember",
    "LearningPathStep",
    "LearningPath",
    "Tournament",
    "TournamentParticipant",
    "Quiz",
    "Question",
    "Option",
    "QuestionTag",
    "QuizReattempt",
    "StudyMaterial",
    "QuizSession",
    "AnalyticsEvent",
    "UserScore",
    "QuizLike",
    "UserBadge",
    "QuestionDifficultyHistory",
    # Aliases and placeholders
    "LeaderboardEntry",
    "UserQuizAttempt",
    "UserAnswer",
    "Badge",
    "UserProgress",
    "DailyChallenge",
    "UserStats",
    "Subject",
    "Topic",
    "UserFavorite",
    "UserBookmark",
    "ReportedContent",
    "Feedback",
    "SystemSettings",
    "AuditLog",
    "EmailVerification",
    "PasswordReset",
    "LoginHistory",
    "UserSession",
    "APIKey",
    "RateLimitOverride",
    "FeatureFlag",
    "UserFeatureFlag",
    "UserStreak",
    "Announcement",
    "UserAnnouncementRead",
    "QuizReport",
    "UserQuizReport",
]