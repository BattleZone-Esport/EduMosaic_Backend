# auth.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid
import jwt  # PyJWT
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
import models
from database import get_db
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# -----------------------
# Password helpers
# -----------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# -----------------------
# Authenticate user
# -----------------------
def authenticate_user(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    
    # Update last login time
    user.last_login = _now_utc()
    db.commit()
    
    return user

# -----------------------
# Token creation helpers
# -----------------------
def _now_utc() -> datetime:
    return datetime.utcnow()

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = {"sub": subject, "type": "access"}
    if expires_delta:
        expire = _now_utc() + expires_delta
    else:
        expire = _now_utc() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": _now_utc()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> (str, str, datetime):
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
def store_refresh_token(db: Session, user_id: int, jti: str, expires_at: datetime):
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

def revoke_refresh_token(db: Session, jti: str):
    rt = db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()
    if rt:
        rt.revoked = True
        rt.revoked_at = _now_utc()
        db.add(rt)
        db.commit()
    return rt

def revoke_user_refresh_tokens(db: Session, user_id: int):
    q = db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user_id,
        models.RefreshToken.revoked == False
    )
    for rt in q:
        rt.revoked = True
        rt.revoked_at = _now_utc()
        db.add(rt)
    db.commit()
    return True

def _get_refresh_record(db: Session, jti: str):
    return db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()

# -----------------------
# Exchange refresh -> new tokens (rotation)
# -----------------------
def refresh_access_token(db: Session, refresh_token: str):
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

    # check DB for jti and revoked status & expiration
    rt = _get_refresh_record(db, jti)
    if not rt or rt.revoked:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    if rt.expires_at < _now_utc():
        # token expired server-side (extra safety)
        rt.revoked = True
        db.add(rt)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # rotate: revoke old refresh token, issue new pair
    revoke_refresh_token(db, jti)

    new_access = create_access_token(subject, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    new_refresh_jwt, new_jti, new_expires = create_refresh_token(subject)

    # store new refresh token record
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
# Current user dependency (for access tokens)
# -----------------------
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError:
        raise credentials_exception

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

# -----------------------
# Enhanced User Profile Functions
# -----------------------
def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
    """Get comprehensive user statistics"""
    # Basic stats
    total_quizzes = db.query(models.UserScore).filter(models.UserScore.user_id == user_id).count()
    total_questions = db.query(func.sum(models.UserScore.total_questions)).filter(
        models.UserScore.user_id == user_id
    ).scalar() or 0
    total_correct = db.query(func.sum(models.UserScore.correct_answers)).filter(
        models.UserScore.user_id == user_id
    ).scalar() or 0
    
    accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
    
    # Category-wise performance
    category_stats = db.query(
        models.Category.name,
        func.count(models.UserScore.id).label("quiz_count"),
        func.avg(models.UserScore.accuracy).label("avg_accuracy"),
        func.max(models.UserScore.score).label("best_score")
    ).join(models.Quiz, models.Quiz.id == models.UserScore.quiz_id
    ).join(models.Category, models.Category.id == models.Quiz.category_id
    ).filter(models.UserScore.user_id == user_id
    ).group_by(models.Category.name).all()
    
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
                "accuracy": round(quiz.accuracy * 100, 2),
                "completed_at": quiz.completed_at
            } for quiz in recent_quizzes
        ],
        "achievements": [
            {
                "name": ua.achievement.name,
                "description": ua.achievement.description,
                "icon": ua.achievement.icon,
                "unlocked_at": ua.unlocked_at,
                "progress": ua.progress,
                "target": ua.achievement.target_value
            } for ua in achievements
        ]
    }

def update_user_streak(db: Session, user_id: int) -> bool:
    """Update user's login streak"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    
    today = datetime.utcnow().date()
    last_login = user.last_login.date() if user.last_login else None
    
    if last_login == today:
        return False  # Already logged in today
    
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
    
    # Check for streak achievements
    check_streak_achievements(db, user_id)
    
    return True

def check_streak_achievements(db: Session, user_id: int):
    """Check and award streak-based achievements"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return
    
    streak_achievements = {
        7: "7-Day Streak",
        30: "30-Day Streak",
        90: "90-Day Streak",
        365: "365-Day Streak"
    }
    
    for days, achievement_name in streak_achievements.items():
        if user.streak >= days:
            award_achievement(db, user_id, achievement_name)

def award_achievement(db: Session, user_id: int, achievement_name: str, progress: float = 100.0):
    """Award an achievement to a user"""
    achievement = db.query(models.Achievement).filter(
        models.Achievement.name == achievement_name
    ).first()
    
    if not achievement:
        return False
    
    # Check if user already has this achievement
    existing = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user_id,
        models.UserAchievement.achievement_id == achievement.id
    ).first()
    
    if existing:
        # Update progress if needed
        if progress > existing.progress:
            existing.progress = progress
            db.commit()
        return True
    
    # Award new achievement
    user_achievement = models.UserAchievement(
        user_id=user_id,
        achievement_id=achievement.id,
        progress=progress,
        unlocked_at=datetime.utcnow()
    )
    db.add(user_achievement)
    db.commit()
    
    # Add XP reward
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.xp += achievement.xp_reward
        db.commit()
    
    return True

def check_quiz_achievements(db: Session, user_id: int, quiz_score: Dict[str, Any]):
    """Check achievements based on quiz performance"""
    # Total quizzes achievement
    total_quizzes = db.query(models.UserScore).filter(models.UserScore.user_id == user_id).count()
    quiz_milestones = {10: "Novice Quizzer", 50: "Experienced Quizzer", 100: "Quiz Master"}
    
    for count, achievement_name in quiz_milestones.items():
        if total_quizzes >= count:
            award_achievement(db, user_id, achievement_name)
    
    # Accuracy achievements
    if quiz_score.get('accuracy', 0) >= 0.9:  # 90% accuracy
        award_achievement(db, user_id, "Accuracy Master")
    
    # Category-specific achievements
    category = db.query(models.Category).filter(models.Category.id == quiz_score.get('category_id')).first()
    if category:
        category_quizzes = db.query(models.UserScore).join(models.Quiz).filter(
            models.UserScore.user_id == user_id,
            models.Quiz.category_id == category.id
        ).count()
        
        if category_quizzes >= 5:
            award_achievement(db, user_id, f"{category.name} Specialist")

def get_global_leaderboard(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """Get global leaderboard with rankings"""
    top_users = db.query(models.User).order_by(models.User.xp.desc()).limit(limit).all()
    
    leaderboard = []
    for rank, user in enumerate(top_users, 1):
        total_quizzes = db.query(models.UserScore).filter(models.UserScore.user_id == user.id).count()
        
        leaderboard.append({
            "rank": rank,
            "user_id": user.id,
            "name": user.full_name,
            "xp": user.xp,
            "streak": user.streak,
            "max_streak": user.max_streak,
            "total_quizzes": total_quizzes,
            "avatar_url": user.avatar_url
        })
    
    return leaderboard

def get_category_leaderboard(db: Session, category_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get leaderboard for specific category"""
    category_scores = db.query(
        models.User.id,
        models.User.full_name,
        models.User.avatar_url,
        func.max(models.UserScore.score).label("best_score"),
        func.avg(models.UserScore.accuracy).label("avg_accuracy"),
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
            "avatar_url": score[2],
            "best_score": float(score[3] or 0),
            "avg_accuracy": round(float(score[4] or 0) * 100, 2),
            "quiz_count": score[5]
        } for score in category_scores
    ]

def get_user_rankings(db: Session, user_id: int) -> Dict[str, Any]:
    """Get user's rankings across different categories"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {}
    
    # Global rank
    all_users = db.query(models.User).order_by(models.User.xp.desc()).all()
    global_rank = next((i+1 for i, u in enumerate(all_users) if u.id == user_id), None)
    
    # Category ranks
    categories = db.query(models.Category).all()
    category_ranks = {}
    
    for category in categories:
        category_users = db.query(
            models.User.id,
            func.max(models.UserScore.score).label("best_score")
        ).join(models.UserScore, models.UserScore.user_id == models.User.id
        ).join(models.Quiz, models.Quiz.id == models.UserScore.quiz_id
        ).filter(models.Quiz.category_id == category.id
        ).group_by(models.User.id).order_by(desc("best_score")).all()
        
        user_rank = next((i+1 for i, (uid, _) in enumerate(category_users) if uid == user_id), None)
        if user_rank:
            category_ranks[category.name] = {
                "rank": user_rank,
                "total_players": len(category_users)
            }
    
    return {
        "global_rank": global_rank,
        "total_players": len(all_users),
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
    existing = db.query(models.UserFollow).filter(
        models.UserFollow.follower_id == follower_id,
        models.UserFollow.followed_id == followed_id
    ).first()
    
    if existing:
        return False
    
    follow = models.UserFollow(
        follower_id=follower_id,
        followed_id=followed_id,
        created_at=datetime.utcnow()
    )
    db.add(follow)
    db.commit()
    
    # Award social achievement
    following_count = db.query(models.UserFollow).filter(
        models.UserFollow.follower_id == follower_id
    ).count()
    
    if following_count >= 10:
        award_achievement(db, follower_id, "Social Butterfly")
    
    return True

def unfollow_user(db: Session, follower_id: int, followed_id: int) -> bool:
    """Unfollow a user"""
    follow = db.query(models.UserFollow).filter(
        models.UserFollow.follower_id == follower_id,
        models.UserFollow.followed_id == followed_id
    ).first()
    
    if follow:
        db.delete(follow)
        db.commit()
        return True
    
    return False

def get_user_followers(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Get list of user's followers"""
    followers = db.query(models.UserFollow, models.User).join(
        models.User, models.UserFollow.follower_id == models.User.id
    ).filter(models.UserFollow.followed_id == user_id).all()
    
    return [
        {
            "user_id": user.id,
            "name": user.full_name,
            "avatar_url": user.avatar_url,
            "xp": user.xp,
            "followed_at": follow.created_at
        } for follow, user in followers
    ]

def get_user_following(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Get list of users followed by this user"""
    following = db.query(models.UserFollow, models.User).join(
        models.User, models.UserFollow.followed_id == models.User.id
    ).filter(models.UserFollow.follower_id == user_id).all()
    
    return [
        {
            "user_id": user.id,
            "name": user.full_name,
            "avatar_url": user.avatar_url,
            "xp": user.xp,
            "followed_at": follow.created_at
        } for follow, user in following
    ]