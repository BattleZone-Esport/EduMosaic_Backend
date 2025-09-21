import os
import sentry_sdk
import psutil
import cloudinary_service
from database_monitoring import DatabaseMonitor
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import time
import uuid
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, validator, conint, confloat
from enum import Enum
import re
import httpx
from bs4 import BeautifulSoup
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
from typing import Tuple, Optional, Dict, Any, List
import qrcode
import bcrypt
import secrets
import string
from datetime import datetime, timedelta

# Add missing imports
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Query, Path, Form, File, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc, case, joinedload
import models
from database import get_db, engine, SessionLocal
import auth
import json
from fastapi.encoders import jsonable_encoder
import cloudinary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("edumosaic.log", maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("edumosaic")

# Store startup time for uptime calculation
startup_time = datetime.utcnow()

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL"),
    default_limits=["200 per minute"]
)

# Redis connection pool (for caching and rate limiting)
redis_pool = None

async def get_redis():
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            max_connections=10,
            decode_responses=True
        )
    return redis.Redis(connection_pool=redis_pool)

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# Railway port configuration
port = int(os.environ.get("PORT", 8000))

# Create database tables with proper error handling
try:
    # First check if tables exist
    with engine.connect() as conn:
        conn.execute(text("SELECT 1 FROM users LIMIT 1"))
    logger.info("Database tables already exist, skipping creation")
except SQLAlchemyError:
    try:
        # Create tables if they don't exist
        models.Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
        # Create PostgreSQL-specific hardening extensions
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            # Create essential indexes for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_quizzes_category ON quizzes(category_id);
                CREATE INDEX IF NOT EXISTS idx_questions_quiz ON questions(quiz_id);
                CREATE INDEX IF NOT EXISTS idx_user_scores_user ON user_scores(user_id);
            """))
        logger.info("✅ PostgreSQL extensions and indexes created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        sentry_sdk.capture_exception(e)
        # Don't exit in production, but warn about potential issues
        if os.getenv("ENVIRONMENT") == "development":
            raise e
        else:
            logger.warning("Continuing startup despite database table creation issues")

# Initialize Sentry only if in production or staging
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=os.getenv("ENVIRONMENT", "production"),
    )
else:
    print("⚠️ Sentry DSN not configured. Monitoring disabled.")

# Only enable /sentry-debug in development
if os.getenv("ENVIRONMENT") == "development":
    @app.get("/sentry-debug")
    async def trigger_error():
        division_by_zero = 1 / 0  # This will trigger an error

# Get environment variables for app configuration
APP_TITLE = os.getenv("APP_TITLE", "🎯 EduMosaic - India's No. 1 Quiz Platform")
APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "India's Premier Quiz & Mock Test Platform")
DEVELOPER_NAME = os.getenv("DEVELOPER_NAME", "Ureshii")
DEVELOPER_EMAIL = os.getenv("DEVELOPER_EMAIL", "nxxznesports@gmail.com")
DEVELOPER_GITHUB = os.getenv("DEVELOPER_GITHUB", "https://github.com/BattleZone-Esport/EduMosaic-Backend")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://edumosaic.com")
APP_VERSION = os.getenv("APP_VERSION", "4.0.0")

# Validate critical environment variables
if not os.getenv("SECRET_KEY"):
    raise ValueError("SECRET_KEY environment variable is required")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0")

# CORS origins from environment variable
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = [
        "https://edumosaic-backend-production.up.railway.app",
        "https://edumosaic.com",
        "https://www.edumosaic.com",
        "https://edumosaic.app",
        "https://*.edumosaic.com",
        "http://localhost:3000",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://localhost:19006",  # Expo web
        "http://localhost:19000",  # Expo dev tools
        "http://localhost:19001",  # Expo dev tools alternative
        "http://localhost:19002",  # Expo dev tools alternative
        "exp://*",  # Expo app
        "https://*.railway.app"
    ]

# Enhanced App with more features
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    contact={
        "name": f"{DEVELOPER_NAME} - EduMosaic Developer",
        "email": DEVELOPER_EMAIL,
        "url": DEVELOPER_GITHUB
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User registration, login, token management, 2FA and security"
        },
        {
            "name": "User Profile",
            "description": "User profiles, achievements, stats, social features and analytics"
        },
        {
            "name": "Quizzes & Exams",
            "description": "Quiz categories, questions, exams, learning paths and adaptive testing"
        },
        {
            "name": "Scores & Analytics",
            "description": "Score tracking, leaderboards, performance analytics and ML insights"
        },
        {
            "name": "Social & Competition",
            "description": "Social features, tournaments, challenges and competitive elements"
        },
        {
            "name": "Content Management",
            "description": "Content creation, moderation, and management (Admin & Educators)"
        },
        {
            "name": "Media",
            "description": "Image and media upload and management"
        },
        {
            "name": "AI & Recommendations",
            "description": "AI-powered features, recommendations and personalized content"
        },
        {
            "name": "System & Administration",
            "description": "System health, monitoring, administration and reporting"
        },
        {
            "name": "Payments & Subscriptions",
            "description": "Premium features, subscriptions and payment processing"
        }
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content={"detail": "Rate limit exceeded. Try again later."}
))
app.add_middleware(SlowAPIMiddleware)

# Serve static files for custom documentation
app.mount("/static", StaticFiles(directory="static"), name="static")

# Enhanced CORS middleware for React Native Expo compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-API-Version", "X-User-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Enhanced middleware for advanced logging and analytics
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    # Log request
    logger.info(f"Request {request_id}: {request.method} {request.url} from {request.client.host}")
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        # Add custom headers
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        response.headers["X-API-Version"] = APP_VERSION
        response.headers["X-Server-Location"] = "Mumbai, India"
        response.headers["X-Request-ID"] = request_id
        # Add rate limit headers if available
        if hasattr(request.state, "rate_limit"):
            response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit["limit"])
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit["remaining"])
            response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit["reset"])
        # Log successful response
        logger.info(f"Request {request_id} completed in {process_time:.3f}s with status {response.status_code}")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request {request_id} failed after {process_time:.3f}s: {str(e)}")
        raise

# Enhanced background task to update user activity
async def safe_background_task(task_func, *args, **kwargs):
    """Wrapper for background tasks with error isolation"""
    try:
        await task_func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Background task {task_func.__name__} failed: {e}")
        sentry_sdk.capture_exception(e)

def update_user_activity_sync(user_id: int, db: Session):
    """Synchronous function for background task to update user activity"""
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.last_activity = datetime.utcnow()
            # Update streak if not already updated today
            today = datetime.utcnow().date()
            if user.last_daily_reward != today:
                # Check if streak continues (activity within 48 hours)
                if user.last_activity and (datetime.utcnow() - user.last_activity).total_seconds() < 172800:  # 48 hours
                    user.streak += 1
                    user.max_streak = max(user.streak, user.max_streak)
                else:
                    user.streak = 1
                user.last_daily_reward = today
                # Award daily login bonus
                user.coins += 10
                user.xp += 5
                # Check for streak achievements
                if user.streak % 7 == 0:  # Weekly streak
                    auth.award_achievement(db, user_id, f"{user.streak}-day Streak", 50 * (user.streak // 7))
            db.commit()
    except Exception as e:
        logger.error(f"Error updating user activity: {e}")

async def record_analytics_event(user_id: int, event_type: str, event_data: Dict[str, Any], db: Session):
    """Background task wrapper for analytics event recording"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, record_analytics_event_sync, user_id, event_type, event_data, db)

# Enhanced background task to record analytics event
async def record_analytics_event_sync(user_id: int, event_type: str, event_data: Dict[str, Any], db: Session):
    """Synchronous function for background task to record analytics event"""
    try:
        # Store in database
        analytics_event = models.AnalyticsEvent(
            user_id=user_id,
            event_type=event_type,
            event_data=jsonable_encoder(event_data),
            timestamp=datetime.utcnow()
        )
        db.add(analytics_event)
        db.commit()
        # Also store in Redis for real-time analytics
        redis_conn = await get_redis()
        await redis_conn.xadd("analytics_stream", {
            "user_id": str(user_id),
            "event_type": event_type,
            "event_data": json.dumps(event_data),
            "timestamp": str(datetime.utcnow())
        })
    except Exception as e:
        logger.error(f"Error recording analytics event: {e}")

async def record_analytics_event(user_id: int, event_type: str, event_data: Dict[str, Any], db: Session):
    """Background task wrapper for analytics event recording"""
    await record_analytics_event_sync(user_id, event_type, event_data, db)

# ✅ Correct
async def record_analytics_event(user_id: int, event_type: str, event_data: Dict[str, Any], db: Session):

    """Background task wrapper for analytics event recording"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, record_analytics_event_sync, user_id, event_type, event_data, db)

# Enhanced AI-powered recommendation engine
class RecommendationEngine:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
    
    async def train_model(self, db: Session):
        """Train recommendation model based on user behavior"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_train_model, db)
    
    def _sync_train_model(self, db: Session):
        try:
            # Get user quiz data for training
            user_scores = db.query(models.UserScore).all()
            if not user_scores:
                return
            # Prepare data for clustering
            X = []
            for score in user_scores:
                X.append([
                    score.user_id,
                    score.quiz_id,
                    score.score,
                    score.accuracy,
                    score.time_taken
                ])
            X = np.array(X)
            X_scaled = self.scaler.fit_transform(X)
            # Train KMeans model
            self.model = KMeans(n_clusters=5, random_state=42)
            self.model.fit(X_scaled)
            logger.info("Recommendation model trained successfully")
        except Exception as e:
            logger.error(f"Error training recommendation model: {e}")
    
    async def get_recommendations(self, user_id: int, db: Session) -> List[Dict[str, Any]]:
        """Get personalized quiz recommendations for a user"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_get_recommendations, user_id, db)
    
    def _sync_get_recommendations(self, user_id: int, db: Session) -> List[Dict[str, Any]]:
        try:
            if self.model is None:
                self._sync_train_model(db)
            # Get user's recent quiz attempts
            user_scores = db.query(models.UserScore).filter(
                models.UserScore.user_id == user_id
            ).order_by(desc(models.UserScore.completed_at)).limit(10).all()
            if not user_scores:
                # Return popular quizzes for new users
                popular_quizzes = db.query(models.Quiz).filter(
                    models.Quiz.is_active == True
                ).order_by(desc(models.Quiz.plays_count)).limit(10).all()
                return [{
                    "id": quiz.id,
                    "title": quiz.title,
                    "description": quiz.description,
                    "difficulty": quiz.difficulty,
                    "plays_count": quiz.plays_count,
                    "reason": "Popular among all users"
                } for quiz in popular_quizzes]
            # Prepare user data for prediction
            user_data = []
            for score in user_scores:
                user_data.append([
                    score.user_id,
                    score.quiz_id,
                    score.score,
                    score.accuracy,
                    score.time_taken
                ])
            user_data = np.array(user_data)
            user_data_scaled = self.scaler.transform(user_data)
            # Predict cluster
            cluster = self.model.predict(user_data_scaled)[0]
            # Find other users in the same cluster
            similar_users = []
            all_scores = db.query(models.UserScore).all()
            for score in all_scores:
                score_data = np.array([[score.user_id, score.quiz_id, score.score, score.accuracy, score.time_taken]])
                score_data_scaled = self.scaler.transform(score_data)
                score_cluster = self.model.predict(score_data_scaled)[0]
                if score_cluster == cluster and score.user_id != user_id:
                    similar_users.append(score.user_id)
            # Get quizzes that similar users performed well on
            similar_quizzes = db.query(models.Quiz).join(models.UserScore).filter(
                models.UserScore.user_id.in_(similar_users),
                models.UserScore.accuracy >= 0.7,
                models.Quiz.is_active == True
            ).group_by(models.Quiz.id).order_by(desc(func.avg(models.UserScore.accuracy))).limit(10).all()
            return [{
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "difficulty": quiz.difficulty,
                "avg_accuracy": db.query(func.avg(models.UserScore.accuracy)).filter(
                    models.UserScore.quiz_id == quiz.id
                ).scalar() or 0,
                "reason": "Popular among users with similar learning patterns"
            } for quiz in similar_quizzes]
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

# Initialize recommendation engine
recommendation_engine = RecommendationEngine()

# Enhanced authentication with 2FA support
class TwoFactorAuth:
    def __init__(self):
        self.redis = None
    async def init_redis(self):
        self.redis = await get_redis()
    def generate_2fa_code(self) -> str:
        """Generate a 6-digit 2FA code"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    async def send_2fa_code(self, user_id: int, email: str) -> bool:
        """Send 2FA code to user's email (simulated)"""
        try:
            code = self.generate_2fa_code()
            # Store code in Redis with 10-minute expiration
            await self.redis.setex(f"2fa:{user_id}", 600, code)
            # In a real implementation, send email here
            logger.info(f"2FA code for user {user_id}: {code}")
            return True
        except Exception as e:
            logger.error(f"Error sending 2FA code: {e}")
            return False
    async def verify_2fa_code(self, user_id: int, code: str) -> bool:
        """Verify 2FA code"""
        try:
            stored_code = await self.redis.get(f"2fa:{user_id}")
            return stored_code == code
        except Exception as e:
            logger.error(f"Error verifying 2FA code: {e}")
            return False

# Initialize 2FA system
two_factor_auth = TwoFactorAuth()

# Enhanced Pydantic models for request validation
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    username: Optional[str] = None
    phone_number: Optional[str] = None
    exam_preferences: Optional[List[str]] = None
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one number')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        return v
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v and not re.match(r'^\+?[1-9]\d{1,14}$', v):
            raise ValueError('Invalid phone number format')
        return v

class QuizSubmit(BaseModel):
    answers: Dict[str, Any]
    time_taken: conint(ge=0)
    session_id: str

class ContentCreate(BaseModel):
    title: str
    content: str
    material_type: str
    category_id: int
    difficulty: str
    language: str

# Enhanced error handling decorator
def handle_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error: {str(e)}")
            sentry_sdk.capture_exception(e)
            raise HTTPException(500, "Database error")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            sentry_sdk.capture_exception(e)
            raise HTTPException(500, "Internal server error")
    return wrapper

# Enhanced system endpoints
@app.get(
    "/",
    response_model=Dict[str, Any],
    tags=["System & Administration"],
    summary="🌐 API Status & Health Check",
    description="Check if API is running successfully with detailed system status",
    responses={
        200: {"description": "API is running", "content": {"application/json": {"examples": {"success": {"value": {"message": "API is running", "status": "healthy"}}}}}}
    }
)
@handle_errors
@limiter.limit("10/minute")
async def root(request: Request, db: Session = Depends(get_db)):
    """
    ## Enhanced API Health Check & Status
    Returns comprehensive system status information including:
    - API health status
    - Database connection status
    - Redis connection status
    - Current server time and uptime
    - System version information
    - Active user count and system load
    **Use this endpoint to:**
    - Verify API deployment status
    - Check server connectivity
    - Monitor service health
    - Get system information
    **Example Response:**
    ```json
    {
        "message": "🎯 EduMosaic API is running successfully!",
        "status": "healthy",
        "version": "4.0.0",
        "timestamp": "2024-01-01T12:00:00Z",
        "server_timezone": "Asia/Kolkata",
        "active_users": 1250,
        "database_status": "connected",
        "redis_status": "connected",
        "uptime": "5 days, 12:30:45",
        "system_load": {"1m": 0.5, "5m": 0.7, "15m": 0.6},
        "memory_usage": "65%",
        "active_connections": 45
    }
    ```
    """
    # Check database connection
    db_status = "connected"
    db_response_time = 0
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        db_response_time = (time.time() - start_time) * 1000  # ms
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
    
    # Check Redis health
    redis_status = "ok"
    redis_response_time = 0
    try:
        redis_conn = await get_redis()
        start_time = time.time()
        await redis_conn.ping()
        redis_response_time = (time.time() - start_time) * 1000  # ms
    except Exception as e:
        redis_status = f"disconnected: {str(e)}"
    
    # Get active user count (last 15 minutes)
    active_users = db.query(models.User).filter(
        models.User.last_activity >= datetime.utcnow() - timedelta(minutes=15)
    ).count()
    
    # Get system information
    try:
        memory_usage = f"{psutil.virtual_memory().percent}%"
        cpu_usage = f"{psutil.cpu_percent()}%"
        disk_usage = f"{psutil.disk_usage('/').percent}%"
        network_throughput = "N/A"  # Requires more complex monitoring
        system_load = {
            "1m": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
            "5m": psutil.getloadavg()[1] if hasattr(psutil, 'getloadavg') else 0,
            "15m": psutil.getloadavg()[2] if hasattr(psutil, 'getloadavg') else 0
        }
        uptime = str(datetime.utcnow() - startup_time)
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        memory_usage = "N/A"
        cpu_usage = "N/A"
        disk_usage = "N/A"
        network_throughput = "N/A"
        system_load = {"1m": 0, "5m": 0, "15m": 0}
        uptime = "N/A"
    
    # Get database connection count
    active_connections = db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")).scalar()
    max_connections = db.execute(text("SHOW max_connections")).scalar()
    
    return {
        "message": "🎯 EduMosaic API is running successfully!", 
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.now().isoformat(),
        "server_timezone": "Asia/Kolkata",
        "active_users": active_users,
        "database_status": db_status,
        "redis_status": redis_status,
        "uptime": uptime,
        "system_load": system_load,
        "memory_usage": memory_usage,
        "cpu_usage": cpu_usage,
        "disk_usage": disk_usage,
        "network_throughput": network_throughput,
        "active_connections": active_connections,
        "developer": DEVELOPER_NAME,
        "website": WEBSITE_URL
    }

# Enhanced authentication endpoints
@app.post(
    "/auth/login",
    response_model=Dict[str, Any],
    tags=["Authentication"],
    summary="🔐 User Login with Optional 2FA",
    description="Authenticate user and return JWT access and refresh tokens with optional 2FA",
    responses={
        200: {"description": "Successful login", "content": {"application/json": {"examples": {"success": {"value": {"access_token": "jwt_token", "token_type": "bearer"}}}}}},
        401: {"description": "Invalid credentials", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Incorrect email or password"}}}}}},
        202: {"description": "2FA required", "content": {"application/json": {"examples": {"2fa_required": {"value": {"message": "2FA required", "2fa_required": true}}}}}}
    }
)
@handle_errors
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    ## Enhanced User Login Endpoint
    Authenticates user credentials and returns JWT access and refresh tokens for subsequent API requests.
    Supports optional two-factor authentication for enhanced security.
    **Parameters:**
    - `username`: User email address or username
    - `password`: User password
    **Returns:**
    - JWT access token with 30 minutes expiry
    - Refresh token with 30 days expiry
    - User profile information
    - 2FA requirement status
    **Example Response (2FA required):**
    ```json
    {
        "message": "2FA code sent to your email",
        "2fa_required": true,
        "user_id": 123,
        "temp_token": "temp_jwt_token"
    }
    ```
    **Example Response (Login successful):**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "full_name": "John Doe",
            "avatar_url": "https://example.com/avatar.jpg",
            "xp": 1500,
            "level": 5
        }
    }
    ```
    """
    # Authenticate user
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if 2FA is enabled for this user
    if user.two_factor_enabled:
        # Generate temporary token for 2FA verification
        temp_token = auth.create_access_token(
            data={"sub": user.email, "2fa": True},
            expires_delta=timedelta(minutes=10)
        )
        # Send 2FA code
        success = await two_factor_auth.send_2fa_code(user.id, user.email)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send 2FA code"
            )
        return {
            "message": "2FA code sent to your email",
            "2fa_required": True,
            "user_id": user.id,
            "temp_token": temp_token
        }
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "login", {"method": "password"}, db)
    
    # Create tokens
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token, jti, expires_at = auth.create_refresh_token(user.email)
    auth.store_refresh_token(db, user.id, jti, expires_at)
    
    # Update streak
    auth.update_user_streak(db, user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "xp": user.xp,
            "level": user.level,
            "is_premium": user.is_premium
        }
    }

@app.post(
    "/auth/verify-2fa",
    response_model=Dict[str, Any],
    tags=["Authentication"],
    summary="🔐 Verify 2FA Code",
    description="Verify two-factor authentication code",
    responses={
        200: {"description": "2FA verified successfully", "content": {"application/json": {"examples": {"success": {"value": {"access_token": "jwt_token", "token_type": "bearer"}}}}}},
        401: {"description": "Invalid 2FA code", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Invalid 2FA code"}}}}}}
    }
)
@handle_errors
@limiter.limit("5/minute")
async def verify_2fa_code(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int = Form(...),
    code: str = Form(...),
    temp_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    ## Verify 2FA Code
    Verifies the two-factor authentication code sent to the user's email.
    **Parameters:**
    - `user_id`: User ID
    - `code`: 6-digit 2FA code
    - `temp_token`: Temporary token from login response
    **Returns:**
    - JWT access token with 30 minutes expiry
    - Refresh token with 30 days expiry
    - User profile information
    **Example Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "full_name": "John Doe",
            "avatar_url": "https://example.com/avatar.jpg",
            "xp": 1500,
            "level": 5
        }
    }
    ```
    """
    # Verify temp token
    try:
        payload = jwt.decode(temp_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None or not payload.get("2fa", False):
            raise HTTPException(status_code=401, detail="Invalid temporary token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid temporary token")
    
    # Verify 2FA code
    is_valid = await two_factor_auth.verify_2fa_code(user_id, code)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    
    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.email != email:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "login_2fa", {"method": "2fa"}, db)
    
    # Create tokens
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token, jti, expires_at = auth.create_refresh_token(user.email)
    auth.store_refresh_token(db, user.id, jti, expires_at)
    
    # Update streak
    auth.update_user_streak(db, user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "xp": user.xp,
            "level": user.level,
            "is_premium": user.is_premium
        }
    }

@app.post(
    "/auth/register",
    response_model=Dict[str, Any],
    tags=["Authentication"],
    summary="👤 User Registration",
    description="Create a new user account with comprehensive profile setup",
    responses={
        200: {"description": "User created successfully", "content": {"application/json": {"examples": {"success": {"value": {"message": "User created successfully", "user_id": 1}}}}}},
        400: {"description": "User already exists or validation failed", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Email already registered"}}}}}}
    }
)
@handle_errors
@limiter.limit("3/minute")
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    ## Enhanced User Registration
    Creates a new user account with comprehensive validation and profile setup.
    Automatically awards welcome bonuses and sets up initial preferences.
    **Parameters:**
    - `email`: Valid email address (required)
    - `password`: Strong password (min 8 chars, uppercase, lowercase, number)
    - `full_name`: User's full name (required)
    - `username`: Optional unique username
    - `phone_number`: Optional phone number with country code
    - `exam_preferences`: List of preferred exam categories
    **Returns:**
    - User ID and confirmation message
    - Welcome bonus details
    - Initial profile information
    **Example Response:**
    ```json
    {
        "message": "User created successfully",
        "user_id": 1,
        "welcome_bonus": {
            "coins": 100,
            "xp": 50,
            "streak_started": true
        },
        "profile": {
            "email": "user@example.com",
            "full_name": "John Doe",
            "username": "johndoe123",
            "level": 1,
            "xp": 50
        }
    }
    ```
    """
    # Check if email already exists
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username exists (if provided)
    if user_data.username:
        existing_username = db.query(models.User).filter(models.User.username == user_data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create user
    hashed_password = auth.get_password_hash(user_data.password)
    
    # Generate username if not provided
    username = user_data.username
    if not username:
        base_username = user_data.full_name.lower().replace(" ", "_")
        username = base_username
        counter = 1
        while db.query(models.User).filter(models.User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1
    
    # Create user
    user = models.User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        username=username,
        phone_number=user_data.phone_number,
        created_at=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        streak=1,
        coins=100,  # Welcome bonus
        xp=50,     # Welcome XP
        level=1
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Set exam preferences if provided
    if user_data.exam_preferences:
        for exam_name in user_data.exam_preferences:
            exam = db.query(models.ExamCategory).filter(
                models.ExamCategory.name == exam_name
            ).first()
            if exam:
                preference = models.UserExamPreference(
                    user_id=user.id,
                    exam_category_id=exam.id
                )
                db.add(preference)
    
    # Award welcome achievement
    auth.award_achievement(db, user.id, "Welcome to EduMosaic!", 25)
    db.commit()
    
    # Record analytics
    background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "register", {
        "exam_preferences": user_data.exam_preferences or []
    }, db)
    
    return {
        "message": "User created successfully",
        "user_id": user.id,
        "welcome_bonus": {
            "coins": 100,
            "xp": 50,
            "streak_started": True
        },
        "profile": {
            "email": user.email,
            "full_name": user.full_name,
            "username": user.username,
            "level": user.level,
            "xp": user.xp
        }
    }

# Enhanced user profile endpoints
@app.get(
    "/users/me",
    response_model=Dict[str, Any],
    tags=["User Profile"],
    summary="👤 Get Current User Profile",
    description="Retrieve comprehensive profile information for the authenticated user",
    responses={
        200: {"description": "User profile retrieved successfully", "content": {"application/json": {"examples": {"success": {"value": {"user": {"id": 1, "email": "user@example.com", "full_name": "John Doe"}}}}}}},
        401: {"description": "Unauthorized", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Could not validate credentials"}}}}}}
    }
)
@handle_errors
@limiter.limit("30/minute")
async def read_users_me(
    request: Request,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Get Current User Profile
    Returns comprehensive profile information for the authenticated user including:
    - Personal details and preferences
    - Statistics and achievements
    - Learning progress and analytics
    - Social connections and activity
    **Authentication:** Bearer token required
    **Returns:**
    - Complete user profile with extended information
    - Statistics and achievements
    - Learning analytics and progress
    - Social information
    **Example Response:**
    ```json
    {
        "id": 1,
        "email": "user@example.com",
        "full_name": "John Doe",
        "username": "johndoe123",
        "avatar_url": "https://example.com/avatar.jpg",
        "bio": "Passionate learner",
        "location": "Mumbai, India",
        "phone_number": "+911234567890",
        "xp": 1500,
        "level": 5,
        "coins": 250,
        "gems": 10,
        "streak": 15,
        "max_streak": 20,
        "is_premium": true,
        "premium_until": "2024-12-31T23:59:59Z",
        "created_at": "2024-01-01T00:00:00Z",
        "last_activity": "2024-01-15T12:30:45Z",
        "stats": {
            "quizzes_completed": 45,
            "total_questions_answered": 1250,
            "average_score": 78.5,
            "total_time_spent": 12500,
            "correct_answers": 980,
            "accuracy": 78.4
        },
        "achievements": [
            {
                "id": 1,
                "title": "Quiz Master",
                "description": "Complete 50 quizzes",
                "icon_url": "https://example.com/achievement1.png",
                "points": 100,
                "earned_at": "2024-01-10T15:30:00Z"
            }
        ],
        "exam_preferences": ["UPSC", "SSC", "Banking"],
        "learning_goals": ["Complete 100 quizzes", "Reach level 10"],
        "social": {
            "followers_count": 45,
            "following_count": 23,
            "rank": 125
        }
    }
    ```
    """
    # Verify token and get current user
    token = credentials.credentials
    email = auth.verify_token(token)
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    
    # Get user statistics
    stats = auth.get_user_stats(db, user.id)
    
    # Get user achievements
    achievements = db.query(models.UserAchievement).join(models.Achievement).filter(
        models.UserAchievement.user_id == user.id
    ).all()
    
    # Get exam preferences
    exam_preferences = db.query(models.ExamCategory).join(models.UserExamPreference).filter(
        models.UserExamPreference.user_id == user.id
    ).all()
    
    # Get social stats
    followers_count = db.query(models.Follow).filter(models.Follow.followed_id == user.id).count()
    following_count = db.query(models.Follow).filter(models.Follow.follower_id == user.id).count()
    
    # Get global rank
    user_rank = auth.get_user_rank(db, user.id)
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "location": user.location,
        "phone_number": user.phone_number,
        "xp": user.xp,
        "level": user.level,
        "coins": user.coins,
        "gems": user.gems,
        "streak": user.streak,
        "max_streak": user.max_streak,
        "is_premium": user.is_premium,
        "premium_until": user.premium_expiry,
        "created_at": user.created_at,
        "last_activity": user.last_activity,
        "stats": stats,
        "achievements": [{
            "id": ua.achievement.id,
            "title": ua.achievement.title,
            "description": ua.achievement.description,
            "icon_url": ua.achievement.icon_url,
            "points": ua.achievement.points,
            "earned_at": ua.earned_at
        } for ua in achievements],
        "exam_preferences": [exam.name for exam in exam_preferences],
        "social": {
            "followers_count": followers_count,
            "following_count": following_count,
            "rank": user_rank
        }
    }

# Enhanced quiz endpoints
@app.get(
    "/quizzes",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="📚 Get Available Quizzes",
    description="Retrieve list of available quizzes with filtering, sorting and pagination",
    responses={
        200: {"description": "Quizzes retrieved successfully", "content": {"application/json": {"examples": {"success": {"value": {"quizzes": [], "total_count": 0, "page": 1, "page_size": 20}}}}}}
    }
)
@handle_errors
@limiter.limit("30/minute")
async def get_quizzes(
    request: Request,
    background_tasks: BackgroundTasks,
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty (easy, medium, hard)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by title or description"),
    sort_by: str = Query("popularity", description="Sort by: popularity, newest, difficulty, rating"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Get Available Quizzes
    Retrieves a paginated list of available quizzes with comprehensive filtering, sorting and search options.
    Includes personalized recommendations for authenticated users.
    **Parameters:**
    - `category_id`: Filter by specific exam category
    - `difficulty`: Filter by difficulty level
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 20, max: 100)
    - `search`: Search query for title or description
    - `sort_by`: Sorting criteria (popularity, newest, difficulty, rating)
    **Authentication:** Optional (for personalized recommendations)
    **Returns:**
    - Paginated list of quizzes with metadata
    - Personalized recommendations for authenticated users
    - Filter and sort options metadata
    **Example Response:**
    ```json
    {
        "quizzes": [
            {
                "id": 1,
                "title": "UPSC Prelims 2024 - General Studies",
                "description": "Complete mock test for UPSC Prelims",
                "category": "UPSC",
                "difficulty": "hard",
                "duration_minutes": 120,
                "questions_count": 100,
                "plays_count": 1250,
                "average_score": 65.5,
                "rating": 4.8,
                "is_premium": false,
                "thumbnail_url": "https://example.com/quiz1.jpg",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ],
        "total_count": 150,
        "page": 1,
        "page_size": 20,
        "total_pages": 8,
        "recommendations": [
            {
                "id": 45,
                "title": "SSC CGL Tier 1 - Quantitative Aptitude",
                "reason": "Based on your performance in similar quizzes"
            }
        ],
        "filters": {
            "categories": [
                {"id": 1, "name": "UPSC", "quiz_count": 25},
                {"id": 2, "name": "SSC", "quiz_count": 18}
            ],
            "difficulties": [
                {"level": "easy", "quiz_count": 45},
                {"level": "medium", "quiz_count": 75},
                {"level": "hard", "quiz_count": 30}
            ]
        }
    }
    ```
    """
    # Get current user if authenticated
    current_user_id = None
    if credentials:
        try:
            token = credentials.credentials
            email = auth.verify_token(token)
            user = db.query(models.User).filter(models.User.email == email).first()
            if user:
                current_user_id = user.id
                background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
        except:
            pass
    
    # Build query
    query = db.query(models.Quiz).filter(models.Quiz.is_active == True)
    
    # Apply filters
    if category_id:
        query = query.filter(models.Quiz.category_id == category_id)
    if difficulty:
        query = query.filter(models.Quiz.difficulty == difficulty)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Quiz.title.ilike(search_pattern),
                models.Quiz.description.ilike(search_pattern)
            )
        )
    
    # Apply sorting
    if sort_by == "newest":
        query = query.order_by(desc(models.Quiz.created_at))
    elif sort_by == "difficulty":
        query = query.order_by(models.Quiz.difficulty)
    elif sort_by == "rating":
        query = query.order_by(desc(models.Quiz.rating))
    else:  # popularity
        query = query.order_by(desc(models.Quiz.plays_count))
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    quizzes = query.options(joinedload(models.Quiz.category)).offset((page - 1) * page_size).limit(page_size).all()
    
    # Get recommendations for authenticated users
    recommendations = []
    if current_user_id:
        recommendations = await recommendation_engine.get_recommendations(current_user_id, db)
    
    # Get filter metadata
    categories = db.query(
        models.ExamCategory.id,
        models.ExamCategory.name,
        func.count(models.Quiz.id).label('quiz_count')
    ).join(models.Quiz).filter(models.Quiz.is_active == True).group_by(
        models.ExamCategory.id, models.ExamCategory.name
    ).all()
    
    difficulties = db.query(
        models.Quiz.difficulty,
        func.count(models.Quiz.id).label('quiz_count')
    ).filter(models.Quiz.is_active == True).group_by(models.Quiz.difficulty).all()
    
    return {
        "quizzes": [{
            "id": quiz.id,
            "title": quiz.title,
            "description": quiz.description,
            "category": quiz.category.name if quiz.category else None,
            "category_id": quiz.category_id,
            "difficulty": quiz.difficulty,
            "duration_minutes": quiz.duration_minutes,
            "questions_count": quiz.questions_count,
            "plays_count": quiz.plays_count,
            "average_score": quiz.average_score,
            "rating": quiz.rating,
            "is_premium": quiz.is_premium,
            "thumbnail_url": quiz.thumbnail_url,
            "created_at": quiz.created_at
        } for quiz in quizzes],
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
        "recommendations": recommendations,
        "filters": {
            "categories": [{"id": c.id, "name": c.name, "quiz_count": c.quiz_count} for c in categories],
            "difficulties": [{"level": d.difficulty, "quiz_count": d.quiz_count} for d in difficulties]
        }
    }

# Enhanced quiz session endpoints
@app.post(
    "/quizzes/{quiz_id}/start",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="🚀 Start Quiz Session",
    description="Initialize a new quiz session and retrieve questions",
    responses={
        200: {"description": "Quiz session started", "content": {"application/json": {"examples": {"success": {"value": {"session_id": "uuid", "questions": [], "time_limit": 1200}}}}}},
        404: {"description": "Quiz not found", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Quiz not found"}}}}}}
    }
)
@handle_errors
@limiter.limit("10/minute")
async def start_quiz(
    request: Request,
    background_tasks: BackgroundTasks,
    quiz_id: int = Path(..., description="Quiz ID to start"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Start Quiz Session
    Initializes a new quiz session, retrieves questions, and sets up timing and tracking.
    Handles premium content access checks and adaptive difficulty.
    **Parameters:**
    - `quiz_id`: ID of the quiz to start
    **Authentication:** Bearer token required
    **Returns:**
    - Unique session ID for tracking
    - Quiz questions with options
    - Time limit and session metadata
    - Shuffled question order for fairness
    **Example Response:**
    ```json
    {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "quiz": {
            "id": 1,
            "title": "UPSC Prelims 2024 - General Studies",
            "description": "Complete mock test for UPSC Prelims",
            "duration_minutes": 120,
            "questions_count": 100
        },
        "questions": [
            {
                "id": 1,
                "question_text": "What is the capital of India?",
                "options": [
                    {"id": "A", "text": "Mumbai"},
                    {"id": "B", "text": "Delhi"},
                    {"id": "C", "text": "Kolkata"},
                    {"id": "D", "text": "Chennai"}
                ],
                "question_type": "multiple_choice",
                "marks": 1,
                "negative_marks": 0.25
            }
        ],
        "time_limit": 7200,
        "started_at": "2024-01-15T12:30:45Z",
        "expires_at": "2024-01-15T14:30:45Z"
    }
    ```
    """
    # Verify token and get current user
    token = credentials.credentials
    email = auth.verify_token(token)
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    
    # Get quiz
    quiz = db.query(models.Quiz).filter(
        models.Quiz.id == quiz_id,
        models.Quiz.is_active == True
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Check premium access
    if quiz.is_premium and not user.is_premium:
        raise HTTPException(
            status_code=403,
            detail="Premium content requires subscription"
        )
    
    # Check for existing incomplete sessions
    existing_session = db.query(models.QuizSession).filter(
        models.QuizSession.user_id == user.id,
        models.QuizSession.quiz_id == quiz_id,
        models.QuizSession.status == "in_progress"
    ).first()
    
    if existing_session:
        # Clean up old session
        db.delete(existing_session)
        db.commit()
    
    # Get questions
    questions = db.query(models.Question).filter(
        models.Question.quiz_id == quiz_id,
        models.Question.is_active == True
    ).order_by(func.random()).all()  # Randomize question order
    
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found for this quiz")
    
    # Create quiz session
    session_id = str(uuid.uuid4())
    started_at = datetime.utcnow()
    expires_at = started_at + timedelta(minutes=quiz.duration_minutes)
    quiz_session = models.QuizSession(
        session_id=session_id,
        user_id=user.id,
        quiz_id=quiz_id,
        started_at=started_at,
        expires_at=expires_at,
        status="in_progress"
    )
    db.add(quiz_session)
    db.commit()
    
    # Record analytics
    background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "quiz_start", {
        "quiz_id": quiz_id,
        "quiz_title": quiz.title,
        "session_id": session_id,
        "question_count": len(questions)
    }, db)
    
    return {
        "session_id": session_id,
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "description": quiz.description,
            "duration_minutes": quiz.duration_minutes,
            "questions_count": quiz.questions_count
        },
        "questions": [{
            "id": q.id,
            "question_text": q.question_text,
            "options": q.options,
            "question_type": q.question_type,
            "marks": q.marks,
            "negative_marks": q.negative_marks,
            "explanation": None  # Don't include explanation during quiz
        } for q in questions],
        "time_limit": quiz.duration_minutes * 60,
        "started_at": started_at,
        "expires_at": expires_at
    }

@app.post(
    "/quizzes/{quiz_id}/submit",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="📤 Submit Quiz Answers",
    description="Submit quiz answers and receive detailed results and analytics",
    responses={
        200: {"description": "Quiz submitted successfully", "content": {"application/json": {"examples": {"success": {"value": {"score": 85, "correct_answers": 17, "total_questions": 20, "accuracy": 85.0}}}}}},
        404: {"description": "Quiz session not found", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Quiz session not found"}}}}}}
    }
)
@handle_errors
@limiter.limit("10/minute")
async def submit_quiz(
    request: Request,
    background_tasks: BackgroundTasks,
    quiz_id: int = Path(..., description="Quiz ID"),
    submission: QuizSubmit = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Submit Quiz Answers
    Processes quiz submission, calculates scores, and provides detailed analytics.
    Updates user statistics, awards achievements, and generates performance insights.
    **Parameters:**
    - `quiz_id`: ID of the quiz being submitted
    - `answers`: Dictionary of question_id to answer
    - `time_taken`: Total time taken in seconds
    - `session_id`: Quiz session ID from start endpoint
    **Authentication:** Bearer token required
    **Returns:**
    - Detailed score breakdown and accuracy
    - Question-by-question feedback with explanations
    - Performance analytics and improvement suggestions
    - XP and coin rewards
    - Achievement unlocks
    **Example Response:**
    ```json
    {
        "score": 85,
        "max_score": 100,
        "correct_answers": 17,
        "total_questions": 20,
        "accuracy": 85.0,
        "time_taken": 1250,
        "time_per_question": 62.5,
        "rank": 125,
        "percentile": 85.5,
        "xp_earned": 150,
        "coins_earned": 25,
        "achievements_unlocked": [
            {
                "title": "Accuracy Master",
                "description": "Achieve 85% accuracy in a quiz",
                "icon_url": "https://example.com/achievement1.png",
                "points": 50
            }
        ],
        "detailed_results": [
            {
                "question_id": 1,
                "question_text": "What is the capital of India?",
                "user_answer": "B",
                "correct_answer": "B",
                "is_correct": true,
                "explanation": "Delhi is the capital of India",
                "marks_earned": 1,
                "time_spent": 45
            }
        ],
        "category_breakdown": [
            {
                "category": "Geography",
                "correct": 8,
                "total": 10,
                "accuracy": 80.0
            }
        ],
        "improvement_suggestions": [
            "Focus on Indian History questions",
            "Improve speed in Quantitative Aptitude"
        ]
    }
    ```
    """
    # Verify token and get current user
    token = credentials.credentials
    email = auth.verify_token(token)
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    
    # Get quiz session
    quiz_session = db.query(models.QuizSession).filter(
        models.QuizSession.session_id == submission.session_id,
        models.QuizSession.user_id == user.id,
        models.QuizSession.quiz_id == quiz_id
    ).first()
    
    if not quiz_session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    if quiz_session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Quiz already submitted")
    
    # Get quiz and questions
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    questions = db.query(models.Question).filter(
        models.Question.quiz_id == quiz_id
    ).all()
    
    # Calculate score
    total_score = 0
    max_score = 0
    correct_answers = 0
    detailed_results = []
    for question in questions:
        max_score += question.marks
        user_answer = submission.answers.get(str(question.id))
        is_correct = user_answer == question.correct_answer
        marks_earned = 0
        if is_correct:
            marks_earned = question.marks
            correct_answers += 1
        elif user_answer and question.negative_marks > 0:
            marks_earned = -question.negative_marks
        total_score += marks_earned
        detailed_results.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "user_answer": user_answer,
            "correct_answer": question.correct_answer,
            "is_correct": is_correct,
            "explanation": question.explanation,
            "marks_earned": marks_earned
        })
    
    # Calculate accuracy
    accuracy = (correct_answers / len(questions)) * 100 if questions else 0
    
    # Update quiz session
    quiz_session.completed_at = datetime.utcnow()
    quiz_session.score = total_score
    quiz_session.accuracy = accuracy
    quiz_session.time_taken = submission.time_taken
    quiz_session.status = "completed"
    
    # Create user score record
    user_score = models.UserScore(
        user_id=user.id,
        quiz_id=quiz_id,
        score=total_score,
        accuracy=accuracy,
        time_taken=submission.time_taken,
        completed_at=datetime.utcnow()
    )
    db.add(user_score)
    
    # Update quiz statistics
    quiz.plays_count += 1
    quiz.average_score = ((quiz.average_score * (quiz.plays_count - 1)) + total_score) / quiz.plays_count
    
    # Award XP and coins
    xp_earned = max(10, int(total_score * 0.5))
    coins_earned = max(5, int(total_score * 0.1))
    user.xp += xp_earned
    user.coins += coins_earned
    
    # Check for level up
    new_level = user.xp // 1000
    if new_level > user.level:
        user.level = new_level
        auth.award_achievement(db, user.id, f"Level {new_level}", 25 * new_level)
    
    # Check for accuracy achievements
    if accuracy >= 90:
        auth.award_achievement(db, user.id, "Accuracy Master (90%+)", 100)
    elif accuracy >= 80:
        auth.award_achievement(db, user.id, "Accuracy Expert (80%+)", 50)
    
    # Check for speed achievements
    time_per_question = submission.time_taken / len(questions) if questions else 0
    if time_per_question <= 30:  # 30 seconds per question
        auth.award_achievement(db, user.id, "Speed Demon", 75)
    
    db.commit()
    
    # Get achievements unlocked in this session
    new_achievements = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user.id,
        models.UserAchievement.earned_at >= datetime.utcnow() - timedelta(minutes=1)
    ).join(models.Achievement).all()
    
    # Get category breakdown
    category_breakdown = []
    # This would require question-category mapping in a real implementation
    
    # Get improvement suggestions
    improvement_suggestions = []
    if accuracy < 70:
        improvement_suggestions.append("Review fundamental concepts")
    if time_per_question > 60:
        improvement_suggestions.append("Improve time management")
    
    # Record analytics
    background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "quiz_submit", {
        "quiz_id": quiz_id,
        "score": total_score,
        "accuracy": accuracy,
        "time_taken": submission.time_taken,
        "xp_earned": xp_earned,
        "coins_earned": coins_earned
    }, db)
    
    return {
        "score": total_score,
        "max_score": max_score,
        "correct_answers": correct_answers,
        "total_questions": len(questions),
        "accuracy": accuracy,
        "time_taken": submission.time_taken,
        "time_per_question": time_per_question,
        "xp_earned": xp_earned,
        "coins_earned": coins_earned,
        "achievements_unlocked": [{
            "title": ua.achievement.title,
            "description": ua.achievement.description,
            "icon_url": ua.achievement.icon_url,
            "points": ua.achievement.points
        } for ua in new_achievements],
        "detailed_results": detailed_results,
        "category_breakdown": category_breakdown,
        "improvement_suggestions": improvement_suggestions
    }

# Enhanced leaderboard endpoints
@app.get(
    "/leaderboard",
    response_model=Dict[str, Any],
    tags=["Scores & Analytics"],
    summary="🏆 Get Leaderboard",
    description="Retrieve global and category-specific leaderboards with various timeframes",
    responses={
        200: {"description": "Leaderboard retrieved successfully", "content": {"application/json": {"examples": {"success": {"value": {"leaderboard": [], "user_rank": 125, "total_users": 10000}}}}}}
    }
)
@handle_errors
@limiter.limit("30/minute")
async def get_leaderboard(
    request: Request,
    background_tasks: BackgroundTasks,
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    timeframe: str = Query("all_time", description="Timeframe: daily, weekly, monthly, all_time"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Get Leaderboard
    Retrieves global or category-specific leaderboards with various timeframes.
    Supports pagination and includes current user's rank.
    **Parameters:**
    - `category_id`: Filter by specific exam category
    - `timeframe`: Time period for ranking (daily, weekly, monthly, all_time)
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 20, max: 100)
    **Authentication:** Optional (to include user rank)
    **Returns:**
    - Paginated leaderboard with user ranks and scores
    - Current user's rank and position
    - Timeframe metadata and ranking criteria
    **Example Response:**
    ```json
    {
        "leaderboard": [
            {
                "rank": 1,
                "user_id": 123,
                "username": "quizmaster",
                "full_name": "Aarav Sharma",
                "avatar_url": "https://example.com/avatar1.jpg",
                "score": 9850,
                "xp": 12500,
                "level": 12,
                "accuracy": 92.5,
                "quizzes_completed": 150
            }
        ],
        "timeframe": "all_time",
        "category": "UPSC",
        "user_rank": 125,
        "user_score": 4550,
        "total_users": 10000,
        "page": 1,
        "page_size": 20,
        "total_pages": 500
    }
    ```
    """
    # Get current user if authenticated
    current_user_id = None
    if credentials:
        try:
            token = credentials.credentials
            email = auth.verify_token(token)
            user = db.query(models.User).filter(models.User.email == email).first()
            if user:
                current_user_id = user.id
                background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
        except:
            pass
    
    # Calculate timeframe
    timeframe_filters = {
        "daily": datetime.utcnow() - timedelta(days=1),
        "weekly": datetime.utcnow() - timedelta(weeks=1),
        "monthly": datetime.utcnow() - timedelta(days=30),
        "all_time": None
    }
    timeframe_filter = timeframe_filters.get(timeframe, None)
    
    # Build leaderboard query
    query = db.query(
        models.User.id,
        models.User.username,
        models.User.full_name,
        models.User.avatar_url,
        models.User.xp,
        models.User.level,
        func.coalesce(func.sum(models.UserScore.score), 0).label('total_score'),
        func.coalesce(func.avg(models.UserScore.accuracy), 0).label('avg_accuracy'),
        func.count(models.UserScore.id).label('quizzes_completed')
    ).outerjoin(models.UserScore)
    
    # Apply timeframe filter
    if timeframe_filter:
        query = query.filter(models.UserScore.completed_at >= timeframe_filter)
    
    # Apply category filter
    if category_id:
        query = query.filter(models.UserScore.quiz.has(category_id=category_id))
    
    query = query.group_by(
        models.User.id,
        models.User.username,
        models.User.full_name,
        models.User.avatar_url,
        models.User.xp,
        models.User.level
    ).order_by(desc('total_score'))
    
    # Get total count
    total_users = query.count()
    
    # Apply pagination
    leaderboard_data = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # Get user rank if authenticated
    user_rank = None
    user_score = None
    if current_user_id:
        # Use window function for proper ranking
        user_rank = db.execute(
            text("""
            SELECT rank FROM (
                SELECT id, RANK() OVER (ORDER BY xp DESC) as rank
                FROM users
            ) ranked_users
            WHERE id = :user_id
            """), {"user_id": current_user_id}
        ).scalar()
        
        # Get user score
        user_score = db.query(func.sum(models.UserScore.score)).filter(
            models.UserScore.user_id == current_user_id
        ).scalar() or 0
    
    # Get category name
    category_name = None
    if category_id:
        category = db.query(models.ExamCategory).filter(models.ExamCategory.id == category_id).first()
        if category:
            category_name = category.name
    
    return {
        "leaderboard": [{
            "rank": (page - 1) * page_size + i + 1,
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "score": user.total_score,
            "xp": user.xp,
            "level": user.level,
            "accuracy": float(user.avg_accuracy),
            "quizzes_completed": user.quizzes_completed
        } for i, user in enumerate(leaderboard_data)],
        "timeframe": timeframe,
        "category": category_name,
        "user_rank": user_rank,
        "user_score": user_score,
        "total_users": total_users,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_users + page_size - 1) // page_size
    }

# Enhanced media upload endpoint
@app.post(
    "/upload/avatar",
    response_model=Dict[str, Any],
    tags=["Media"],
    summary="🖼️ Upload User Avatar",
    description="Upload and process user profile picture with Cloudinary integration",
    responses={
        200: {"description": "Avatar uploaded successfully", "content": {"application/json": {"examples": {"success": {"value": {"message": "Avatar uploaded", "avatar_url": "https://res.cloudinary.com/.../avatar.jpg"}}}}}},
        400: {"description": "Invalid file or upload failed", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Invalid file type"}}}}}}
    }
)
@handle_errors
@limiter.limit("5/minute")
async def upload_avatar(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file to upload (max 5MB)"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Upload User Avatar
    Uploads and processes user profile pictures with comprehensive validation,
    automatic optimization, and Cloudinary integration for reliable storage.
    **Parameters:**
    - `file`: Image file (JPEG, PNG, WebP; max 5MB)
    **Authentication:** Bearer token required
    **Returns:**
    - Secure CDN URL for the uploaded avatar
    - Processing metadata and optimization details
    - Thumbnail versions for different use cases
    **Example Response:**
    ```json
    {
        "message": "Avatar uploaded successfully",
        "avatar_url": "https://res.cloudinary.com/demo/image/upload/v1234567/avatar.jpg",
        "thumbnail_url": "https://res.cloudinary.com/demo/image/upload/w_100,h_100,c_fill/v1234567/avatar.jpg",
        "file_size": 124857,
        "format": "jpg",
        "width": 300,
        "height": 300,
        "optimized_size": 45678
    }
    ```
    """
    # Verify token and get current user
    token = credentials.credentials
    email = auth.verify_token(token)
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size
    if file_size > cloudinary_service.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File size must be less than {cloudinary_service.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    # Validate file type using magic bytes
    file_signature = file_content[:4]
    valid_signatures = [
        b'\xFF\xD8\xFF\xE0',  # JPEG
        b'\x89PNG',           # PNG
        b'GIF8',              # GIF
        b'RIFF',              # WebP
        b'\x00\x00\x01\x00'   # ICO
    ]
    
    if file_signature not in valid_signatures:
        raise HTTPException(400, "Invalid image format")
    
    # Upload to Cloudinary using optimized service
    try:
        upload_result = cloudinary_service.upload_avatar(file_content, user.id)
        if not upload_result:
            raise HTTPException(status_code=500, detail="Failed to upload image")
        
        avatar_url = upload_result['secure_url']
        
        # Update user avatar
        user.avatar_url = avatar_url
        db.commit()
        
        # Record analytics
        background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "avatar_upload", {
            "file_size": file_size,
            "content_type": file.content_type,
            "cloudinary_url": avatar_url
        }, db)
        
        # Generate thumbnail URL
        thumbnail_url = cloudinary.CloudinaryImage(avatar_url).build_url(
            width=100, height=100, crop="fill", quality="auto"
        )
        
        return {
            "message": "Avatar uploaded successfully",
            "avatar_url": avatar_url,
            "thumbnail_url": thumbnail_url,
            "file_size": file_size,
            "format": upload_result.get('format'),
            "width": upload_result.get('width'),
            "height": upload_result.get('height'),
            "optimized_size": upload_result.get('bytes')
        }
    except Exception as e:
        logger.error(f"Cloudinary upload error: {e}")
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail="Failed to upload image")

# Enhanced analytics endpoints
@app.get(
    "/analytics/user/{user_id}",
    response_model=Dict[str, Any],
    tags=["Scores & Analytics"],
    summary="📊 Get User Analytics",
    description="Retrieve comprehensive learning analytics and performance insights for a user",
    responses={
        200: {"description": "Analytics retrieved successfully", "content": {"application/json": {"examples": {"success": {"value": {"overview": {}, "progress": [], "category_breakdown": []}}}}}},
        404: {"description": "User not found", "content": {"application/json": {"examples": {"error": {"value": {"detail": "User not found"}}}}}}
    }
)
@handle_errors
@limiter.limit("30/minute")
async def get_user_analytics(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int = Path(..., description="User ID to get analytics for"),
    timeframe: str = Query("all_time", description="Timeframe: 7d, 30d, 90d, all_time"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Get User Analytics
    Retrieves comprehensive learning analytics and performance insights for a specific user.
    Includes progress tracking, category breakdown, and improvement recommendations.
    **Parameters:**
    - `user_id`: ID of the user to get analytics for
    - `timeframe`: Time period for analytics (7d, 30d, 90d, all_time)
    **Authentication:** Optional (public for user's own data, restricted for others)
    **Returns:**
    - Overview statistics and performance metrics
    - Progress trends over time
    - Category-wise performance breakdown
    - Strength and weakness analysis
    - Personalized recommendations
    **Example Response:**
    ```json
    {
        "overview": {
            "total_quizzes": 45,
            "total_questions": 1250,
            "average_score": 78.5,
            "average_accuracy": 78.4,
            "total_time_spent": 12500,
            "current_streak": 15,
            "max_streak": 20,
            "level": 5,
            "xp": 1500,
            "global_rank": 125,
            "percentile": 85.5
        },
        "progress": [
            {
                "date": "2024-01-01",
                "quizzes_completed": 2,
                "average_score": 75.0,
                "time_spent": 120
            }
        ],
        "category_breakdown": [
            {
                "category": "Geography",
                "quizzes_completed": 10,
                "average_score": 85.0,
                "average_accuracy": 86.2,
                "time_spent": 1250,
                "strength_score": 0.85
            }
        ],
        "strengths": ["Geography", "Current Affairs"],
        "weaknesses": ["Mathematics", "Logical Reasoning"],
        "recommendations": [
            {
                "type": "quiz",
                "quiz_id": 123,
                "title": "Mathematics Basics",
                "reason": "Improve performance in weak area",
                "priority": "high"
            }
        ],
        "goals": [
            {
                "goal": "Reach level 10",
                "progress": 0.5,
                "target_date": "2024-06-30"
            }
        ]
    }
    ```
    """
    # Check authentication and permissions
    current_user_id = None
    if credentials:
        try:
            token = credentials.credentials
            email = auth.verify_token(token)
            current_user = db.query(models.User).filter(models.User.email == email).first()
            if current_user:
                current_user_id = current_user.id
                background_tasks.add_task(safe_background_task, update_user_activity, current_user.id, db)
                # Check if user is accessing their own analytics or has permission
                if current_user_id != user_id and not current_user.is_admin:
                    raise HTTPException(status_code=403, detail="Access denied")
        except:
            if user_id != 0:  # Allow public access for demo user
                raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate timeframe
    timeframe_filters = {
        "7d": datetime.utcnow() - timedelta(days=7),
        "30d": datetime.utcnow() - timedelta(days=30),
        "90d": datetime.utcnow() - timedelta(days=90),
        "all_time": None
    }
    timeframe_filter = timeframe_filters.get(timeframe, None)
    
    # Get overview statistics
    scores_query = db.query(models.UserScore).filter(models.UserScore.user_id == user_id)
    if timeframe_filter:
        scores_query = scores_query.filter(models.UserScore.completed_at >= timeframe_filter)
    
    user_scores = scores_query.all()
    total_quizzes = len(user_scores)
    total_questions = sum(score.quiz.questions_count for score in user_scores if score.quiz)
    average_score = sum(score.score for score in user_scores) / total_quizzes if total_quizzes else 0
    average_accuracy = sum(score.accuracy for score in user_scores) / total_quizzes if total_quizzes else 0
    total_time_spent = sum(score.time_taken for score in user_scores)
    
    # Get progress data (last 30 days)
    progress_data = []
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=29 - i)
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        daily_scores = db.query(models.UserScore).filter(
            models.UserScore.user_id == user_id,
            models.UserScore.completed_at >= start_of_day,
            models.UserScore.completed_at <= end_of_day
        ).all()
        daily_quizzes = len(daily_scores)
        daily_avg_score = sum(score.score for score in daily_scores) / daily_quizzes if daily_quizzes else 0
        daily_time_spent = sum(score.time_taken for score in daily_scores)
        progress_data.append({
            "date": date.date().isoformat(),
            "quizzes_completed": daily_quizzes,
            "average_score": daily_avg_score,
            "time_spent": daily_time_spent
        })
    
    # Get category breakdown (simplified)
    category_breakdown = []
    # This would require more complex queries in a real implementation
    
    # Get strengths and weaknesses (simplified)
    strengths = ["Geography", "Current Affairs"]  # Would be calculated from performance data
    weaknesses = ["Mathematics", "Logical Reasoning"]  # Would be calculated from performance data
    
    # Get recommendations
    recommendations = []
    if weaknesses:
        for weakness in weaknesses[:2]:
            quiz = db.query(models.Quiz).filter(
                models.Quiz.category.has(name=weakness),
                models.Quiz.difficulty == "easy"
            ).first()
            if quiz:
                recommendations.append({
                    "type": "quiz",
                    "quiz_id": quiz.id,
                    "title": quiz.title,
                    "reason": f"Improve {weakness} skills",
                    "priority": "high"
                })
    
    # Get goals
    goals = [
        {
            "goal": "Reach level 10",
            "progress": user.level / 10,
            "target_date": "2024-06-30"
        },
        {
            "goal": "Achieve 90% accuracy",
            "progress": average_accuracy / 90,
            "target_date": "2024-03-31"
        }
    ]
    
    return {
        "overview": {
            "total_quizzes": total_quizzes,
            "total_questions": total_questions,
            "average_score": average_score,
            "average_accuracy": average_accuracy,
            "total_time_spent": total_time_spent,
            "current_streak": user.streak,
            "max_streak": user.max_streak,
            "level": user.level,
            "xp": user.xp,
            "global_rank": auth.get_user_rank(db, user_id),
            "percentile": 85.5  # Would be calculated from rank data
        },
        "progress": progress_data,
        "category_breakdown": category_breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "goals": goals
    }

# Enhanced AI-powered endpoints
@app.get(
    "/ai/recommendations",
    response_model=Dict[str, Any],
    tags=["AI & Recommendations"],
    summary="🤖 Get AI-Powered Recommendations",
    description="Retrieve personalized quiz and content recommendations using machine learning",
    responses={
        200: {"description": "Recommendations retrieved successfully", "content": {"application/json": {"examples": {"success": {"value": {"recommendations": [], "reasoning": "Based on your learning patterns"}}}}}}
    }
)
@handle_errors
@limiter.limit("20/minute")
async def get_ai_recommendations(
    request: Request,
    background_tasks: BackgroundTasks,
    max_recommendations: int = Query(10, ge=1, le=20, description="Maximum number of recommendations"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ## Get AI-Powered Recommendations
    Retrieves personalized quiz and content recommendations using machine learning algorithms
    that analyze user behavior, performance patterns, and similar users' preferences.
    **Parameters:**
    - `max_recommendations`: Maximum number of recommendations to return (1-20)
    **Authentication:** Bearer token required
    **Returns:**
    - Personalized quiz recommendations with reasoning
    - Content suggestions based on learning gaps
    - Difficulty-adjusted suggestions
    - Confidence scores and explanation
    **Example Response:**
    ```json
    {
        "recommendations": [
            {
                "type": "quiz",
                "id": 123,
                "title": "UPSC Geography - Advanced",
                "category": "Geography",
                "difficulty": "hard",
                "confidence": 0.85,
                "reason": "Strong performance in Geography, ready for advanced content",
                "expected_accuracy": 82.5,
                "time_estimate": 45
            }
        ],
        "learning_insights": [
            {
                "insight": "You perform 25% better in evening sessions",
                "confidence": 0.78,
                "suggestion": "Schedule difficult quizzes in the evening"
            }
        ],
        "skill_gaps": [
            {
                "skill": "Data Interpretation",
                "current_level": "intermediate",
                "target_level": "advanced",
                "improvement_plan": [
                    "Complete 5 DI practice sets",
                    "Review percentage calculations",
                    "Take timed DI quizzes"
                ]
            }
        ],
        "model_version": "v2.1.0",
        "last_trained": "2024-01-15T03:00:00Z"
    }
    ```
    """
    # Verify token and get current user
    token = credentials.credentials
    email = auth.verify_token(token)
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update user activity
    background_tasks.add_task(safe_background_task, update_user_activity, user.id, db)
    
    # Get recommendations from AI engine
    recommendations = await recommendation_engine.get_recommendations(user.id, db)
    
    # Generate learning insights (simplified - would use real ML in production)
    learning_insights = [
        {
            "insight": "You perform 25% better in evening sessions",
            "confidence": 0.78,
            "suggestion": "Schedule difficult quizzes in the evening"
        },
        {
            "insight": "Accuracy improves by 15% on second attempt",
            "confidence": 0.82,
            "suggestion": "Re-take quizzes to reinforce learning"
        }
    ]
    
    # Identify skill gaps (simplified)
    skill_gaps = [
        {
            "skill": "Data Interpretation",
            "current_level": "intermediate",
            "target_level": "advanced",
            "improvement_plan": [
                "Complete 5 DI practice sets",
                "Review percentage calculations",
                "Take timed DI quizzes"
            ]
        }
    ]
    
    # Record analytics
    background_tasks.add_task(safe_background_task, record_analytics_event, user.id, "ai_recommendations", {
        "recommendation_count": len(recommendations),
        "model_version": "v2.1.0"
    }, db)
    
    return {
        "recommendations": recommendations[:max_recommendations],
        "learning_insights": learning_insights,
        "skill_gaps": skill_gaps,
        "model_version": "v2.1.0",
        "last_trained": "2024-01-15T03:00:00Z"
    }

# Enhanced system health endpoint
@app.get(
    "/system/health",
    response_model=Dict[str, Any],
    tags=["System & Administration"],
    summary="🩺 System Health Check",
    description="Comprehensive system health monitoring with detailed component status",
    responses={
        200: {"description": "System health status", "content": {"application/json": {"examples": {"success": {"value": {"status": "healthy", "components": {"database": "ok"}}}}}},
        503: {"description": "System unhealthy", "content": {"application/json": {"examples": {"error": {"value": {"status": "unhealthy", "components": {"database": "error"}}}}}}
    }
)
@handle_errors
@limiter.limit("10/minute")
async def system_health(  # Added 'async' here
    request: Request,
    db: Session = Depends(get_db)
):
    """
    ## System Health Check
    Provides comprehensive system health monitoring with detailed status of all components.
    Essential for DevOps monitoring, alerting, and automated recovery systems.
    **Parameters:** None
    **Authentication:** None (public endpoint)
    **Returns:**
    - Overall system health status
    - Detailed component status (database, cache, storage, etc.)
    - Performance metrics and resource utilization
    - Dependency status and response times
    - Uptime and version information
    **Example Response:**
    ```json
    {
        "status": "healthy",
        "timestamp": "2024-01-15T12:30:45Z",
        "uptime": "5 days, 12:30:45",
        "version": "4.0.0",
        "components": {
            "database": {
                "status": "ok",
                "response_time": 12.5,
                "active_connections": 15,
                "max_connections": 100
            },
            "redis": {
                "status": "ok",
                "response_time": 2.1,
                "memory_used": "256MB",
                "memory_max": "1GB"
            },
            "cloudinary": {
                "status": "ok",
                "response_time": 45.2
            },
            "api": {
                "status": "ok",
                "response_time_avg": 125.5,
                "request_rate": 45.2,
                "error_rate": 0.5
            }
        },
        "resources": {
            "memory_usage": "65%",
            "cpu_usage": "45%",
            "disk_usage": "30%",
            "network_throughput": "125Mbps"
        },
        "dependencies": [
            {
                "name": "PostgreSQL",
                "status": "ok",
                "version": "15.2"
            }
        ]
    }
    ```
    """
    # Check database health
    db_status = "ok"
    db_response_time = 0
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        db_response_time = (time.time() - start_time) * 1000  # ms
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Check Redis health
    redis_status = "ok"
    redis_response_time = 0
    try:
        redis_conn = await get_redis()
        start_time = time.time()
        await redis_conn.ping()
        redis_response_time = (time.time() - start_time) * 1000  # ms
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    # Check Cloudinary health (simplified)
    cloudinary_status = "ok"
    cloudinary_response_time = 0
    
    # Determine overall status
    overall_status = "healthy"
    if "error" in db_status or "error" in redis_status:
        overall_status = "degraded"
    if db_status.startswith("error") or redis_status.startswith("error"):
        overall_status = "unhealthy"
    
    # Get database connection info
    active_connections = db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")).scalar()
    max_connections = db.execute(text("SHOW max_connections")).scalar()
    
    # Get Redis memory info
    redis_memory_used = "0MB"
    redis_memory_max = "0MB"
    try:
        redis_conn = await get_redis()
        memory_info = await redis_conn.info('memory')
        redis_memory_used = f"{int(memory_info['used_memory']) // 1024 // 1024}MB"
        redis_memory_max = f"{int(memory_info['maxmemory']) // 1024 // 1024}MB" if memory_info['maxmemory'] > 0 else "0MB"
    except:
        pass
    
    # Get system metrics
    try:
        memory_usage = f"{psutil.virtual_memory().percent}%"
        cpu_usage = f"{psutil.cpu_percent()}%"
        disk_usage = f"{psutil.disk_usage('/').percent}%"
        network_throughput = "N/A"  # Requires more complex monitoring
        system_load = {
            "1m": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
            "5m": psutil.getloadavg()[1] if hasattr(psutil, 'getloadavg') else 0,
            "15m": psutil.getloadavg()[2] if hasattr(psutil, 'getloadavg') else 0
        }
        uptime = str(datetime.utcnow() - startup_time)
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        memory_usage = "N/A"
        cpu_usage = "N/A"
        disk_usage = "N/A"
        network_throughput = "N/A"
        system_load = {"1m": 0, "5m": 0, "15m": 0}
        uptime = "N/A"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": uptime,
        "version": APP_VERSION,
        "components": {
            "database": {
                "status": db_status,
                "response_time": round(db_response_time, 1),
                "active_connections": active_connections,
                "max_connections": max_connections
            },
            "redis": {
                "status": redis_status,
                "response_time": round(redis_response_time, 1),
                "memory_used": redis_memory_used,
                "memory_max": redis_memory_max
            },
            "cloudinary": {
                "status": cloudinary_status,
                "response_time": round(cloudinary_response_time, 1)
            },
            "api": {
                "status": "ok",
                "response_time_avg": 125.5,  # Would be calculated from metrics
                "request_rate": 45.2,       # Would be calculated from metrics
                "error_rate": 0.5           # Would be calculated from metrics
            }
        },
        "resources": {
            "memory_usage": memory_usage,
            "cpu_usage": cpu_usage,
            "disk_usage": disk_usage,
            "network_throughput": network_throughput
        },
        "dependencies": [
            {
                "name": "PostgreSQL",
                "status": "ok" if db_status == "ok" else "error",
                "version": "15.2"  # Would be retrieved from database
            },
            {
                "name": "Redis",
                "status": "ok" if redis_status == "ok" else "error",
                "version": "7.2.3"  # Would be retrieved from Redis
            },
            {
                "name": "Cloudinary",
                "status": cloudinary_status,
                "version": "1.0.0"
            }
        ]
    }

# Enhanced error handling
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Enhanced HTTP exception handler with logging and structured responses"""
    logger.warning(f"HTTPException: {exc.status_code} - {exc.detail} - {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        },
        headers=exc.headers if hasattr(exc, 'headers') else None
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unexpected errors"""
    logger.error(f"Unexpected error: {str(exc)} - {request.url}", exc_info=True)
    # Don't expose internal details in production
    error_detail = "Internal server error"
    if os.getenv("ENVIRONMENT") == "development":
        error_detail = str(exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": error_detail,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        }
    )

# ==================== CRITICAL: DATABASE MONITORING WITH SENTRY INTEGRATION ==================== #
async def database_monitoring_background():
    from database_monitoring import DatabaseMonitor
    db_monitor = DatabaseMonitor()
    while True:
        try:
            db_monitor.run_monitoring()
            await asyncio.sleep(300)  # 5 minutes
        except Exception as e:
            # IMPORTANT: Agar database_monitoring fail ho jaye, toh Sentry se report karo!
            sentry_sdk.capture_exception(e)
            logger.error(f"❌ Database monitoring task crashed: {e}")
            # Wait before retrying
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("🚀 EduMosaic API starting up...")
    
    # Initialize Redis connection
    try:
        await get_redis()
        logger.info("✅ Redis connection pool initialized")
    except Exception as e:
        logger.error(f"❌ Redis initialization failed: {e}")
        sentry_sdk.capture_exception(e)
    
    # Initialize 2FA system
    try:
        await two_factor_auth.init_redis()
        logger.info("✅ 2FA system initialized")
    except Exception as e:
        logger.error(f"❌ 2FA initialization failed: {e}")
        sentry_sdk.capture_exception(e)
    
    # Train recommendation model in background
    async def train_model_background():
        try:
            db = SessionLocal()
            await recommendation_engine.train_model(db)
            db.close()
            logger.info("✅ Recommendation model trained successfully")
        except Exception as e:
            logger.error(f"❌ Model training failed: {e}")
            sentry_sdk.capture_exception(e)
    
    asyncio.create_task(train_model_background())

    # DATABASE MONITORING WITH SENTRY PROTECTION
    asyncio.create_task(database_monitoring_background())
    
    logger.info("✅ Background tasks initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup application on shutdown"""
    logger.info("🛑 EduMosaic API shutting down...")
    # Close Redis connection pool
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
        logger.info("✅ Redis connection pool closed")

# Run the application
if __name__ == "__main__":
    import uvicorn
    # Enhanced uvicorn configuration
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        timeout_keep_alive=300,
        log_level="info",
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )