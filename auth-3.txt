# auth.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import uuid
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, text, case
import models
from database import get_db
import os
from dotenv import load_dotenv
from cloudinary_service import get_avatar_url as get_avatar_cloudinary_url
from cloudinary_service import upload_avatar as cloudinary_upload_avatar

load_dotenv()

# Configuration from environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
XP_PER_LEVEL = int(os.getenv("XP_PER_LEVEL", "1000"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# -----------------------
# Password helpers
# -----------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate hash for password"""
    return pwd_context.hash(password)

# -----------------------
# Authentication helpers
# -----------------------
def _now_utc() -> datetime:
    """Return current UTC time"""
    return datetime.utcnow()

def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """Authenticate user by email or username"""
    # Try email first
    user = db.query(models.User).filter(models.User.email == username).first()
    if not user:
        # Try username
        user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    # Update last login time
    user.last_login = _now_utc()
    db.commit()
    return user

# -----------------------
# Token creation helpers
# -----------------------
def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = _now_utc() + expires_delta
    else:
        expire = _now_utc() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": _now_utc()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> Tuple[str, str, datetime]:
    """Create refresh token with JTI"""
    jti = str(uuid.uuid4())
    to_encode = {"sub": subject, "type": "refresh", "jti": jti}
    if expires_delta:
        expire = _now_utc() + expires_delta
    else:
        expire = _now_utc() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": _now_utc()})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti, expire

# -----------------------
# Refresh token persistence
# -----------------------
def store_refresh_token(db: Session, user_id: int, jti: str, expires_at: datetime) -> models.RefreshToken:
    """Store refresh token in database"""
    rt = models.RefreshToken(
        user_id=user_id,
        jti=jti,
        expires_at=expires_at,
        revoked=False,
        created_at=_now_utc()
    )
    db.add(rt)
    db.commit()
    db.refresh(rt)
    return rt

def revoke_refresh_token(db: Session, jti: str) -> Optional[models.RefreshToken]:
    """Revoke refresh token"""
    rt = db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()
    if rt:
        rt.revoked = True
        rt.revoked_at = _now_utc()
        db.add(rt)
        db.commit()
    return rt

def revoke_user_refresh_tokens(db: Session, user_id: int) -> bool:
    """Revoke all refresh tokens for a user"""
    tokens = db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user_id,
        models.RefreshToken.revoked == False
    ).all()
    for rt in tokens:
        rt.revoked = True
        rt.revoked_at = _now_utc()
        db.add(rt)
    db.commit()
    return True

def _get_refresh_record(db: Session, jti: str) -> Optional[models.RefreshToken]:
    """Get refresh token record by JTI"""
    return db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()

# -----------------------
# Token exchange (refresh token to new tokens)
# -----------------------
def refresh_access_token(db: Session, refresh_token: str) -> Dict[str, Any]:
    """Exchange refresh token for new access and refresh tokens"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    if payload.get("type") != "refresh":
        raise credentials_exception
    
    subject = payload.get("sub")
    jti = payload.get("jti")
    if not subject or not jti:
        raise credentials_exception
    
    # Check DB for jti and revoked status & expiration
    rt = _get_refresh_record(db, jti)
    if not rt or rt.revoked:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")
    
    if rt.expires_at < _now_utc():
        # Token expired server-side (extra safety)
        rt.revoked = True
        db.add(rt)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")
    
    # Rotate: revoke old refresh token, issue new pair
    revoke_refresh_token(db, jti)
    
    new_access = create_access_token(
        {"sub": subject, "type": "access"}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    new_refresh_jwt, new_jti, new_expires = create_refresh_token(subject)
    
    # Store new refresh token record
    user = db.query(models.User).filter(models.User.email == subject).first()
    if not user:
        raise credentials_exception
    store_refresh_token(db, user_id=user.id, jti=new_jti, expires_at=new_expires)
    
    return {
        "access_token": new_access,
        "refresh_token": new_refresh_jwt,
        "token_type": "bearer"
    }

# -----------------------
# Token verification
# -----------------------
def verify_token(token: str) -> str:
    """Verify JWT token and return subject (email)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise credentials_exception

# -----------------------
# Current user dependency (for access tokens)
# -----------------------
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            raise credentials_exception
        # Update last active timestamp
        user.last_active = _now_utc()
        db.commit()
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError:
        raise credentials_exception

# -----------------------
# Avatar management
# -----------------------
def get_user_avatar_url(user: models.User) -> Optional[str]:
    """Get user avatar URL with Cloudinary transformations"""
    if not user.avatar_url:
        return None
    
    try:
        # Use Cloudinary service to get optimized avatar URL
        return get_avatar_cloudinary_url(user.avatar_url, size=200, crop="fill")
    except Exception as e:
        # Fallback to original URL if Cloudinary fails
        return user.avatar_url

def upload_user_avatar(user_id: int, file_content: bytes) -> Optional[Dict[str, Any]]:
    """Upload user avatar to Cloudinary with optimization"""
    try:
        # Use Cloudinary service for avatar upload
        result = cloudinary_upload_avatar(file_content, str(user_id))
        return result
    except Exception as e:
        return None

# -----------------------
# User Profile Functions
# -----------------------
def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
    """Get comprehensive user statistics"""
    # Basic stats
    total_quizzes = db.query(models.UserScore).filter(models.UserScore.user_id == user_id).count()
    
    # Total questions answered
    total_questions = db.query(func.coalesce(func.sum(models.UserScore.total_questions), 0)).filter(
        models.UserScore.user_id == user_id
    ).scalar()
    
    # Total correct answers
    total_correct = db.query(func.coalesce(func.sum(models.UserScore.correct_answers), 0)).filter(
        models.UserScore.user_id == user_id
    ).scalar()
    
    # Overall accuracy
    accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
    
    # Category-wise performance
    category_stats = db.query(
        models.ExamCategory.name,
        func.count(models.UserScore.id).label("quiz_count"),
        func.avg(models.UserScore.accuracy).label("avg_accuracy"),
        func.max(models.UserScore.score).label("best_score")
    ).join(models.Quiz, models.Quiz.id == models.UserScore.quiz_id
    ).join(models.ExamCategory, models.ExamCategory.id == models.Quiz.category_id
    ).filter(models.UserScore.user_id == user_id
    ).group_by(models.ExamCategory.id, models.ExamCategory.name).all()
    
    # Streak information
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    # Recent activity
    recent_quizzes = db.query(models.UserScore).filter(
        models.UserScore.user_id == user_id
    ).order_by(models.UserScore.completed_at.desc()).limit(5).all()
    
    # Achievement progress
    achievements = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user_id
    ).options(joinedload(models.UserAchievement.achievement)).all()
    
    # Social stats
    followers_count = db.query(models.Follow).filter(models.Follow.followed_id == user_id).count()
    following_count = db.query(models.Follow).filter(models.Follow.follower_id == user_id).count()
    
    return {
        "total_quizzes": total_quizzes,
        "total_questions": total_questions,
        "total_correct": total_correct,
        "overall_accuracy": round(accuracy, 2),
        "category_stats": [
            {
                "category": stat[0],
                "quiz_count": stat[1],
                "avg_accuracy": round(float(stat[2] or 0) * 100, 2),
                "best_score": stat[3] or 0
            } for stat in category_stats
        ],
        "current_streak": user.streak if user else 0,
        "max_streak": user.max_streak if user else 0,
        "recent_quizzes": [
            {
                "quiz_id": quiz.quiz_id,
                "score": quiz.score,
                "accuracy": round(quiz.accuracy * 100, 2) if quiz.accuracy else 0,
                "completed_at": quiz.completed_at
            } for quiz in recent_quizzes
        ],
        "achievements": [
            {
                "name": ua.achievement.title,
                "description": ua.achievement.description,
                "icon_url": ua.achievement.icon_url,
                "points": ua.achievement.points,
                "unlocked_at": ua.earned_at,
                "progress": ua.progress,
                "target": ua.achievement.target_value
            } for ua in achievements
        ],
        "social": {
            "followers_count": followers_count,
            "following_count": following_count,
            "rank": get_user_rank(db, user_id)
        },
        "xp": user.xp if user else 0,
        "level": user.level if user else 1,
        "coins": user.coins if user else 0,
        "gems": user.gems if user else 0
    }

def update_user_streak(db: Session, user_id: int) -> bool:
    """Update user's login streak and award streak-based rewards"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    
    today = datetime.utcnow().date()
    last_login = user.last_login.date() if user.last_login else None
    
    if last_login == today:
        return False  # Already logged in today
    
    # Update streak based on time since last login
    if last_login and (today - last_login).days == 1:
        # Consecutive login
        user.streak += 1
    elif last_login and (today - last_login).days > 1:
        # Broken streak
        user.streak = 1
    else:
        # First login or same day
        user.streak = user.streak or 1
    
    # Update max streak
    if user.streak > (user.max_streak or 0):
        user.max_streak = user.streak
    
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Award daily login bonus
    user.coins += 10
    user.xp += 5
    db.commit()
    
    # Check for streak achievements
    check_streak_achievements(db, user_id)
    
    # Award streak-based rewards for longer streaks
    if user.streak >= 7:
        user.coins += 25
        user.xp += 50
        award_achievement(db, user_id, "Weekly Streak Champion")
    
    if user.streak >= 30:
        user.coins += 100
        user.xp += 200
        award_achievement(db, user_id, "Monthly Streak Master")
    
    if user.streak >= 90:
        user.coins += 300
        user.xp += 600
        award_achievement(db, user_id, "Quarterly Streak Legend")
    
    if user.streak >= 365:
        user.coins += 1000
        user.xp += 2000
        award_achievement(db, user_id, "Annual Streak Legend")
    
    db.commit()
    return True

def check_streak_achievements(db: Session, user_id: int):
    """Check and award streak-based achievements"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return
    
    # Streak achievements
    streak_achievements = [
        (7, "7-Day Streak Champion", "Complete 7 consecutive days of logging in", 50),
        (14, "14-Day Streak Master", "Complete 14 consecutive days of logging in", 100),
        (30, "30-Day Streak Legend", "Complete 30 consecutive days of logging in", 250),
        (90, "90-Day Streak Expert", "Complete 90 consecutive days of logging in", 500),
        (180, "180-Day Streak Pro", "Complete 180 consecutive days of logging in", 1000),
        (365, "365-Day Streak Legend", "Complete 365 consecutive days of logging in", 2500)
    ]
    
    for days, name, description, points in streak_achievements:
        if user.streak >= days:
            award_achievement(db, user_id, name, description, points)
    
    # Special achievement for maintaining a streak for a long time
    if user.max_streak >= 100:
        award_achievement(db, user_id, "Streak Master", "Maintain a streak of 100+ days", 1000)

def award_achievement(db: Session, user_id: int, title: str, description: str = "", points: int = 0, 
                     target_value: Optional[int] = None, icon_url: Optional[str] = None) -> bool:
    """Award an achievement to a user"""
    # Check if achievement exists, create if not
    achievement = db.query(models.Achievement).filter(
        models.Achievement.title == title
    ).first()
    
    if not achievement:
        achievement = models.Achievement(
            title=title,
            description=description,
            points=points,
            target_value=target_value,
            icon_url=icon_url
        )
        db.add(achievement)
        db.commit()
        db.refresh(achievement)
    
    # Check if user already has this achievement
    existing = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user_id,
        models.UserAchievement.achievement_id == achievement.id
    ).first()
    
    if existing:
        # Update progress if needed
        if target_value and target_value > existing.progress:
            existing.progress = target_value
            db.commit()
        return True
    
    # Award new achievement
    user_achievement = models.UserAchievement(
        user_id=user_id,
        achievement_id=achievement.id,
        progress=target_value if target_value else 100,
        earned_at=datetime.utcnow()
    )
    db.add(user_achievement)
    db.commit()
    
    # Add XP reward
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and achievement.points > 0:
        user.xp += achievement.points
        db.commit()
    
    return True

def check_quiz_achievements(db: Session, user_id: int, quiz_score: Dict[str, Any]):
    """Check achievements based on quiz performance"""
    # Total quizzes achievement
    total_quizzes = db.query(models.UserScore).filter(models.UserScore.user_id == user_id).count()
    
    quiz_milestones = [
        (10, "Novice Quizzer", "Complete your first 10 quizzes", 50),
        (25, "Quiz Enthusiast", "Complete 25 quizzes", 100),
        (50, "Quiz Master", "Complete 50 quizzes", 200),
        (100, "Quiz Champion", "Complete 100 quizzes", 500),
        (250, "Quiz Legend", "Complete 250 quizzes", 1000),
        (500, "Quiz Grandmaster", "Complete 500 quizzes", 2500)
    ]
    
    for count, name, description, points in quiz_milestones:
        if total_quizzes >= count:
            award_achievement(db, user_id, name, description, points)
    
    # Accuracy achievements
    accuracy = quiz_score.get('accuracy', 0)
    if accuracy >= 0.9:  # 90% accuracy
        award_achievement(db, user_id, "Accuracy Master", "Achieve 90% accuracy in a quiz", 100)
    if accuracy >= 0.8:  # 80% accuracy
        award_achievement(db, user_id, "Accuracy Expert", "Achieve 80% accuracy in a quiz", 50)
    
    # Speed achievements
    time_per_question = quiz_score.get('time_per_question', 0)
    if time_per_question <= 30:  # 30 seconds per question
        award_achievement(db, user_id, "Speed Demon", "Answer questions at 30 seconds or less per question", 75)
    
    # Category-specific achievements
    category_id = quiz_score.get('category_id')
    if category_id:
        category = db.query(models.ExamCategory).filter(models.ExamCategory.id == category_id).first()
        if category:
            category_quizzes = db.query(models.UserScore).join(models.Quiz).filter(
                models.UserScore.user_id == user_id,
                models.Quiz.category_id == category_id
            ).count()
            
            category_milestones = [
                (5, f"{category.name} Specialist", f"Complete 5 quizzes in {category.name}", 50),
                (10, f"{category.name} Expert", f"Complete 10 quizzes in {category.name}", 100),
                (25, f"{category.name} Master", f"Complete 25 quizzes in {category.name}", 250)
            ]
            
            for count, name, description, points in category_milestones:
                if category_quizzes >= count:
                    award_achievement(db, user_id, name, description, points)
    
    # Perfect score achievement
    if quiz_score.get('score', 0) == quiz_score.get('max_score', 0):
        award_achievement(db, user_id, "Perfect Score", "Achieve a perfect score in a quiz", 200)

def get_global_leaderboard(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """Get global leaderboard with rankings"""
    top_users = db.query(models.User).order_by(desc(models.User.xp)).limit(limit).all()
    leaderboard = []
    
    for rank, user in enumerate(top_users, 1):
        total_quizzes = db.query(models.UserScore).filter(models.UserScore.user_id == user.id).count()
        leaderboard.append({
            "rank": rank,
            "user_id": user.id,
            "name": user.full_name,
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
            "max_streak": user.max_streak,
            "total_quizzes": total_quizzes,
            "avatar_url": get_user_avatar_url(user),
            "coins": user.coins,
            "gems": user.gems
        })
    
    return leaderboard

def get_category_leaderboard(db: Session, category_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get leaderboard for specific category"""
    category_scores = db.query(
        models.User.id,
        models.User.full_name,
        models.User.avatar_url,
        func.coalesce(func.max(models.UserScore.score), 0).label("best_score"),
        func.coalesce(func.avg(models.UserScore.accuracy), 0).label("avg_accuracy"),
        func.count(models.UserScore.id).label("quiz_count")
    ).join(models.UserScore, models.UserScore.user_id == models.User.id
    ).join(models.Quiz, models.Quiz.id == models.UserScore.quiz_id
    ).filter(models.Quiz.category_id == category_id
    ).group_by(models.User.id, models.User.full_name, models.User.avatar_url
    ).order_by(desc("best_score")).limit(limit).all()
    
    return [
        {
            "user_id": score[0],
            "name": score[1],
            "avatar_url": get_user_avatar_url(score[0]),
            "best_score": float(score[2]),
            "avg_accuracy": round(float(score[3]) * 100, 2),
            "quiz_count": score[4]
        } for score in category_scores
    ]

def get_user_rank(db: Session, user_id: int) -> Optional[int]:
    """Get user's global rank"""
    # This is a simplified implementation
    # In production, you'd use window functions for proper ranking
    users = db.query(models.User.id, models.User.xp).order_by(desc(models.User.xp)).all()
    for rank, (uid, _) in enumerate(users, 1):
        if uid == user_id:
            return rank
    return None

def get_user_rankings(db: Session, user_id: int) -> Dict[str, Any]:
    """Get user's rankings across different categories"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {}
    
    # Global rank
    global_rank = get_user_rank(db, user_id)
    
    # Category ranks
    categories = db.query(models.ExamCategory).all()
    category_ranks = {}
    
    for category in categories:
        # Get category leaderboard
        category_leaderboard = get_category_leaderboard(db, category.id, limit=100)
        for rank, user_data in enumerate(category_leaderboard, 1):
            if user_data["user_id"] == user_id:
                category_ranks[category.name] = {
                    "rank": rank,
                    "total_players": len(category_leaderboard),
                    "best_score": user_data["best_score"],
                    "avg_accuracy": user_data["avg_accuracy"]
                }
                break
    
    return {
        "global_rank": global_rank,
        "total_players": db.query(models.User).count(),
        "category_ranks": category_ranks
    }

# -----------------------
# Social Features
# -----------------------
def follow_user(db: Session, follower_id: int, followed_id: int) -> bool:
    """Follow another user"""
    if follower_id == followed_id:
        return False
    
    # Check if already following
    existing = db.query(models.Follow).filter(
        models.Follow.follower_id == follower_id,
        models.Follow.followed_id == followed_id
    ).first()
    
    if existing:
        return False
    
    follow = models.Follow(
        follower_id=follower_id,
        followed_id=followed_id,
        created_at=datetime.utcnow()
    )
    db.add(follow)
    db.commit()
    
    # Award social achievement
    following_count = db.query(models.Follow).filter(
        models.Follow.follower_id == follower_id
    ).count()
    
    # Social achievement milestones
    if following_count == 5:
        award_achievement(db, follower_id, "Social Butterfly", "Follow 5 users", 50)
    elif following_count == 10:
        award_achievement(db, follower_id, "Social Connector", "Follow 10 users", 100)
    elif following_count == 25:
        award_achievement(db, follower_id, "Social Guru", "Follow 25 users", 250)
    elif following_count == 50:
        award_achievement(db, follower_id, "Social Influencer", "Follow 50 users", 500)
    
    return True

def unfollow_user(db: Session, follower_id: int, followed_id: int) -> bool:
    """Unfollow a user"""
    follow = db.query(models.Follow).filter(
        models.Follow.follower_id == follower_id,
        models.Follow.followed_id == followed_id
    ).first()
    
    if follow:
        db.delete(follow)
        db.commit()
        return True
    
    return False

def get_user_followers(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Get list of user's followers"""
    followers = db.query(models.Follow, models.User).join(
        models.User, models.Follow.follower_id == models.User.id
    ).filter(models.Follow.followed_id == user_id).all()
    
    return [
        {
            "user_id": user.id,
            "name": user.full_name,
            "avatar_url": get_user_avatar_url(user),
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
            "followed_at": follow.created_at
        } for follow, user in followers
    ]

def get_user_following(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Get list of users followed by this user"""
    following = db.query(models.Follow, models.User).join(
        models.User, models.Follow.followed_id == models.User.id
    ).filter(models.Follow.follower_id == user_id).all()
    
    return [
        {
            "user_id": user.id,
            "name": user.full_name,
            "avatar_url": get_user_avatar_url(user),
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
            "followed_at": follow.created_at
        } for follow, user in following
    ]

def get_social_leaderboard(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """Get leaderboard of most social users"""
    # This is a simplified implementation
    # In production, you'd calculate social score based on followers, following, and engagement
    top_users = db.query(models.User).order_by(desc(models.User.followers_count)).limit(limit).all()
    
    leaderboard = []
    for rank, user in enumerate(top_users, 1):
        leaderboard.append({
            "rank": rank,
            "user_id": user.id,
            "name": user.full_name,
            "avatar_url": get_user_avatar_url(user),
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "social_score": user.followers_count + user.following_count
        })
    
    return leaderboard

# -----------------------
# Level System
# -----------------------
def calculate_level(xp: int) -> int:
    """Calculate user level based on XP"""
    return xp // XP_PER_LEVEL

def get_level_requirements(level: int) -> Dict[str, int]:
    """Get XP requirements for a specific level"""
    # Simple exponential progression for level requirements
    base_xp = 1000
    growth_rate = 1.2
    return {
        "level": level,
        "xp_required": int(base_xp * (growth_rate ** (level - 1))),
        "xp_to_next": int(base_xp * (growth_rate ** level)) - int(base_xp * (growth_rate ** (level - 1)))
    }

def level_up(db: Session, user_id: int) -> bool:
    """Check if user has leveled up and award rewards"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    
    current_level = user.level
    new_level = calculate_level(user.xp)
    
    if new_level > current_level:
        # Update level
        user.level = new_level
        db.commit()
        
        # Award level-specific rewards
        level_rewards = {
            2: {"coins": 50, "gems": 5, "title": "Level 2 - Quiz Novice"},
            5: {"coins": 100, "gems": 10, "title": "Level 5 - Quiz Enthusiast"},
            10: {"coins": 250, "gems": 25, "title": "Level 10 - Quiz Master"},
            20: {"coins": 500, "gems": 50, "title": "Level 20 - Quiz Champion"},
            30: {"coins": 1000, "gems": 100, "title": "Level 30 - Quiz Legend"},
            40: {"coins": 2500, "gems": 250, "title": "Level 40 - Quiz Grandmaster"},
            50: {"coins": 5000, "gems": 500, "title": "Level 50 - Quiz Supreme"}
        }
        
        if new_level in level_rewards:
            rewards = level_rewards[new_level]
            user.coins += rewards["coins"]
            user.gems += rewards["gems"]
            db.commit()
            
            # Award achievement for level up
            award_achievement(db, user_id, rewards["title"], f"Reached level {new_level}", 50 * new_level)
        
        # Special achievement for reaching level 10
        if new_level == 10:
            award_achievement(db, user_id, "Level 10 Master", "Reach level 10", 500)
        
        # Special achievement for reaching level 50
        if new_level == 50:
            award_achievement(db, user_id, "Level 50 Legend", "Reach level 50", 2500)
        
        return True
    
    return False

def get_level_progress(db: Session, user_id: int) -> Dict[str, Any]:
    """Get user's level progress"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {}
    
    current_level = user.level
    level_req = get_level_requirements(current_level + 1)
    xp_needed = level_req["xp_to_next"]
    xp_progress = user.xp % XP_PER_LEVEL
    
    return {
        "level": current_level,
        "xp": user.xp,
        "xp_to_next": xp_needed,
        "progress": min(100, (xp_progress / xp_needed) * 100) if xp_needed > 0 else 100
    }

# -----------------------
# Social Challenges
# -----------------------
def check_social_challenges(db: Session, user_id: int):
    """Check social challenges and award rewards"""
    # Check follower count challenges
    followers_count = db.query(models.Follow).filter(models.Follow.followed_id == user_id).count()
    
    if followers_count >= 10:
        award_achievement(db, user_id, "Social Star", "Get 10 followers", 100)
    if followers_count >= 50:
        award_achievement(db, user_id, "Social Influencer", "Get 50 followers", 500)
    if followers_count >= 100:
        award_achievement(db, user_id, "Social Celebrity", "Get 100 followers", 1000)
    
    # Check following count challenges
    following_count = db.query(models.Follow).filter(models.Follow.follower_id == user_id).count()
    
    if following_count >= 25:
        award_achievement(db, user_id, "Community Builder", "Follow 25 users", 250)
    if following_count >= 50:
        award_achievement(db, user_id, "Social Connector", "Follow 50 users", 500)
    
    # Check for completing a challenge with a friend
    # This would require additional challenge tracking in the database
    # For now, we'll just award a basic achievement
    award_achievement(db, user_id, "Team Player", "Complete a quiz with a friend", 150)

# -----------------------
# Premium Features
# -----------------------
def check_premium_features(db: Session, user_id: int):
    """Check premium features and award rewards"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return
    
    if user.is_premium:
        # Premium user benefits
        user.coins += 50  # Daily premium bonus
        db.commit()
        
        # Award achievement for premium subscription
        if user.premium_until and user.premium_until > datetime.utcnow():
            award_achievement(db, user_id, "Premium Member", "Subscribe to premium", 250)
        
        # Check for long-term premium subscription
        if user.premium_until and (user.premium_until - datetime.utcnow()).days > 30:
            award_achievement(db, user_id, "Premium Veteran", "Stay premium for 30+ days", 500)
        if user.premium_until and (user.premium_until - datetime.utcnow()).days > 90:
            award_achievement(db, user_id, "Premium Elite", "Stay premium for 90+ days", 1000)

# -----------------------
# Daily Challenges
# -----------------------
def check_daily_challenges(db: Session, user_id: int):
    """Check daily challenges and award rewards"""
    # This is a simplified implementation
    # In production, you'd track daily challenges in a separate table
    # For now, we'll just award basic achievements for completing daily activities
    
    # Daily quiz completion
    today = datetime.utcnow().date()
    quizzes_today = db.query(models.UserScore).filter(
        models.UserScore.user_id == user_id,
        func.date(models.UserScore.completed_at) == today
    ).count()
    
    if quizzes_today >= 1:
        award_achievement(db, user_id, "Daily Quiz Taker", "Complete 1 quiz today", 50)
    if quizzes_today >= 3:
        award_achievement(db, user_id, "Daily Quiz Master", "Complete 3 quizzes today", 100)
    
    # Daily social activity
    followers_count = db.query(models.Follow).filter(models.Follow.followed_id == user_id).count()
    following_count = db.query(models.Follow).filter(models.Follow.follower_id == user_id).count()
    
    if followers_count > 0 or following_count > 0:
        award_achievement(db, user_id, "Social Daily", "Engage with social features today", 50)

# -----------------------
# Community Contributions
# -----------------------
def check_community_contributions(db: Session, user_id: int):
    """Check community contributions and award rewards"""
    # This is a simplified implementation
    # In production, you'd track contributions like quiz creation, forum posts, etc.
    # For now, we'll just award basic achievements for quiz creation
    
    # Quiz creation
    quizzes_created = db.query(models.Quiz).filter(
        models.Quiz.created_by == user_id
    ).count()
    
    if quizzes_created >= 1:
        award_achievement(db, user_id, "Quiz Creator", "Create your first quiz", 100)
    if quizzes_created >= 5:
        award_achievement(db, user_id, "Quiz Builder", "Create 5 quizzes", 250)
    if quizzes_created >= 10:
        award_achievement(db, user_id, "Quiz Master", "Create 10 quizzes", 500)
    
    # Forum contributions
    # This would require a forum model
    # For now, we'll just award a basic achievement
    award_achievement(db, user_id, "Community Helper", "Help others in the community", 200)