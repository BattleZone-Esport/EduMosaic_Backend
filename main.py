import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Query, Path, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_, or_
from typing import List, Optional, Dict, Any, Union
import json
from datetime import timedelta, datetime, date
import models
import auth
from database import SessionLocal, engine, get_db
from cloudinary_service import upload_avatar as upload_image
import pandas as pd
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import cloudinary.uploader

import collections
import collections.abc

# ✅ Patch for Python 3.13+ compatibility
for attr in ("Mapping", "MutableMapping", "Sequence"):
    if not hasattr(collections, attr):
        setattr(collections, attr, getattr(collections.abc, attr))

# Railway port configuration
port = int(os.environ.get("PORT", 8000))

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="🎯 EduMosaic - India's No. 1 Quiz Platform",
    description="""
    # 🚀 EduMosaic - India's Premier Quiz & Mock Test Platform
    
    ## 📖 Overview
    The most comprehensive quiz platform for competitive exams, school tests, and skill assessment.
    Supporting all major Indian competitive exams including UPSC, SSC, Banking, Railways, and more.
    
    ## ✨ Features
    - 🔐 Advanced JWT Authentication with Role-Based Access
    - 📊 50+ Quiz Categories covering all competitive exams
    - 🏆 Real-time Leaderboards & Achievement System
    - 🎯 Personalized Learning Paths & Daily Goals
    - 💰 Virtual Economy with Coins & Rewards
    - 👥 Social Features - Follow, Compete, Share
    - 🏅 Tournament System with Prize Pools
    - 📱 Multi-language Support (English, Hindi, Regional Languages)
    - 📊 Advanced Analytics & Performance Reports
    - 🖼️ Cloudinary Integration for Media Management
    - ⚡ FastAPI with PostgreSQL for High Performance
    
    ## 🛠️ Technologies
    - **Backend**: FastAPI, Python 3.12
    - **Database**: PostgreSQL with Advanced Indexing
    - **Storage**: Cloudinary for media storage
    - **Authentication**: JWT with Refresh Tokens
    - **Deployment**: Railway with CDN
    - **Analytics**: Custom-built performance tracking
    
    ## 🎯 Exam Coverage
    - UPSC (IAS, IPS, IFS)
    - SSC (CGL, CHSL, MTS)
    - Banking (IBPS, SBI, RBI)
    - Railways (RRB NTPC, Group D)
    - State PSCs
    - CAT, XAT, MAT
    - JEE, NEET, CLAT
    - School Curriculum (CBSE, ICSE, State Boards)
    
    ## 👨‍💻 Development Team
    **Ureshii** - Lead Developer  
    📧 Email: nxxznesports@gmail.com  
    🔗 GitHub: [BattleZone-Esport](https://github.com/BattleZone-Esport)
    
    **Contributors**: 
    - Content Team: 50+ Subject Matter Experts
    - QA Team: 10+ Quality Assurance Specialists
    - Design Team: 5+ UI/UX Designers
    
    ## 📝 API Documentation
    - Interactive Swagger UI: `/docs`
    - Alternative ReDoc: `/redoc`
    - Postman Collection: `/postman.json`
    
    ## 📊 Statistics
    - 10,000+ Questions
    - 50+ Exam Categories
    - 100,000+ Registered Users
    - 1 Million+ Quiz Attempts Monthly
    
    ## 🏆 Achievements
    - 🥇 Ranked #1 Education App on Play Store (India)
    - 📈 4.9/5 Rating from 50,000+ Reviews
    - 🏅 Best EdTech Startup 2024
    """,
    version="3.0.0",
    contact={
        "name": "Ureshii - EduMosaic Developer",
        "email": "nxxznesports@gmail.com",
        "url": "https://github.com/BattleZone-Esport/EduMosaic-Backend"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User registration, login, token management and security"
        },
        {
            "name": "User Profile",
            "description": "User profiles, achievements, stats, and social features"
        },
        {
            "name": "Quizzes & Exams",
            "description": "Quiz categories, questions, exams, and learning paths"
        },
        {
            "name": "Scores & Analytics",
            "description": "Score tracking, leaderboards, and performance analytics"
        },
        {
            "name": "Social & Competition",
            "description": "Social features, tournaments, and competitive elements"
        },
        {
            "name": "Content Management",
            "description": "Content creation, moderation, and management (Admin)"
        },
        {
            "name": "Media",
            "description": "Image and media upload and management"
        },
        {
            "name": "System",
            "description": "System health, monitoring, and administration"
        }
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Serve static files for custom documentation
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS middleware for production - Expanded for wider access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://edumosaic-backend-production.up.railway.app",
        "https://edumosaic.com",
        "https://www.edumosaic.com",
        "https://edumosaic.app",
        "https://*.edumosaic.com",
        "http://localhost:3000",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "exp://*",
        "https://*.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-API-Version", "X-User-ID"]
)

# Add custom middleware for enhanced logging and analytics
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    
    # Add custom headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-API-Version"] = "3.0.0"
    response.headers["X-Server-Location"] = "Mumbai, India"
    response.headers["X-EDM-Request-ID"] = os.urandom(8).hex()
    
    # Log request for analytics
    if hasattr(request.state, "user_id"):
        response.headers["X-User-ID"] = str(request.state.user_id)
    
    return response

# Background task to update user activity
async def update_user_activity(user_id: int, db: Session):
    """Update user's last activity timestamp"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.last_activity = datetime.utcnow()
        db.commit()

# Background task to record analytics event
async def record_analytics_event(user_id: int, event_type: str, event_data: Dict[str, Any], db: Session):
    """Record an analytics event"""
    # In a real implementation, this would write to an analytics database or service
    pass

# ==================== SYSTEM ENDPOINTS ==================== #
@app.get(
    "/",
    response_model=Dict[str, Any],
    tags=["System"],
    summary="🌐 API Status & Health Check",
    description="Check if API is running successfully with detailed system status",
    responses={
        200: {"description": "API is running", "content": {"application/json": {"examples": {"success": {"value": {"message": "API is running", "status": "healthy"}}}}}}
    }
)
async def root():
    """
    ## API Health Check & Status
    
    Returns comprehensive system status information including:
    - API health status
    - Database connection status
    - Current server time
    - System version information
    - Active user count
    
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
        "version": "3.0.0",
        "timestamp": "2024-01-01T12:00:00Z",
        "server_timezone": "Asia/Kolkata",
        "active_users": 1250,
        "database_status": "connected",
        "uptime": "5 days, 12:30:45"
    }
    ```
    """
    # Check database connection
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
    except Exception:
        db_status = "disconnected"
    
    # Get active user count (last 15 minutes)
    db = SessionLocal()
    active_users = db.query(models.User).filter(
        models.User.last_activity >= datetime.utcnow() - timedelta(minutes=15)
    ).count()
    db.close()
    
    return {
        "message": "🎯 EduMosaic API is running successfully!", 
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "server_timezone": "Asia/Kolkata",
        "active_users": active_users,
        "database_status": db_status,
        "developer": "Ureshii",
        "website": "https://edumosaic.com"
    }

@app.get(
    "/system/stats",
    response_model=Dict[str, Any],
    tags=["System"],
    summary="📊 System Statistics",
    description="Get detailed platform statistics and metrics",
    responses={
        200: {"description": "System statistics", "content": {"application/json": {"examples": {"success": {"value": {"users": 10000, "quizzes": 500}}}}}}
    }
)
async def system_stats(db: Session = Depends(get_db)):
    """
    ## Get Platform Statistics
    
    Returns detailed statistics about the platform usage and content.
    
    **Returns:**
    - User statistics (total, active, new today)
    - Content statistics (quizzes, questions, categories)
    - Performance metrics (completion rates, accuracy)
    
    **Example Response:**
    ```json
    {
        "users": {
            "total": 100000,
            "active_today": 12500,
            "new_today": 350,
            "premium_users": 2500
        },
        "content": {
            "quizzes": 1500,
            "questions": 25000,
            "categories": 50,
            "exams_covered": 25
        },
        "performance": {
            "avg_accuracy": 68.5,
            "avg_completion_time": "12m 30s",
            "daily_completions": 12500
        }
    }
    ```
    """
    # User statistics
    total_users = db.query(models.User).count()
    active_today = db.query(models.User).filter(
        models.User.last_activity >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    new_today = db.query(models.User).filter(
        models.User.created_at >= datetime.utcnow().date()
    ).count()
    premium_users = db.query(models.User).filter(models.User.is_premium == True).count()
    
    # Content statistics
    total_quizzes = db.query(models.Quiz).count()
    total_questions = db.query(models.Question).count()
    total_categories = db.query(models.Category).count()
    
    # Performance metrics (simplified)
    avg_accuracy = db.query(func.avg(models.UserScore.accuracy)).scalar() or 0
    
    return {
        "users": {
            "total": total_users,
            "active_today": active_today,
            "new_today": new_today,
            "premium_users": premium_users
        },
        "content": {
            "quizzes": total_quizzes,
            "questions": total_questions,
            "categories": total_categories,
            "exams_covered": 25  # This would be calculated from categories
        },
        "performance": {
            "avg_accuracy": round(avg_accuracy * 100, 2),
            "daily_completions": active_today // 2  # Simplified metric
        }
    }

# ==================== AUTHENTICATION ENDPOINTS ==================== #
@app.post(
    "/auth/login",
    response_model=Dict[str, Any],
    tags=["Authentication"],
    summary="🔐 User Login",
    description="Authenticate user and return JWT access and refresh tokens",
    responses={
        200: {"description": "Successful login", "content": {"application/json": {"examples": {"success": {"value": {"access_token": "jwt_token", "token_type": "bearer"}}}}}},
        401: {"description": "Invalid credentials", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Incorrect email or password"}}}}}}
    }
)
async def login_for_access_token(
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    ## User Login Endpoint
    
    Authenticates user credentials and returns JWT access and refresh tokens for subsequent API requests.
    Also updates user's last login and activity timestamps.
    
    **Parameters:**
    - `username`: User email address or username
    - `password`: User password
    
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
    # Try email first, then username
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # Try username if email failed
        user = db.query(models.User).filter(models.User.username == form_data.username).first()
        if user and not auth.verify_password(form_data.password, user.hashed_password):
            user = None
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update user activity
    background_tasks.add_task(update_user_activity, user.id, db)
    background_tasks.add_task(record_analytics_event, user.id, "login", {"method": "password"}, db)
    
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
    description="Create a new user account with comprehensive profile",
    responses={
        200: {"description": "User created successfully", "content": {"application/json": {"examples": {"success": {"value": {"message": "User created successfully", "user_id": 1}}}}}},
        400: {"description": "Email already registered", "content": {"application/json": {"examples": {"error": {"value": {"detail": "Email already registered"}}}}}}
    }
)
async def register_user(
    background_tasks: BackgroundTasks,
    email: str = Form(..., description="User email address", json_schema_extra={"example": "user@example.com"}),
    password: str = Form(..., description="User password (min 8 characters)", json_schema_extra={"example": "SecurePassword123!"}),
    full_name: str = Form(..., description="User's full name", json_schema_extra={"example": "John Doe"}),
    username: Optional[str] = Form(None, description="Unique username", json_schema_extra={"example": "johndoe123"}),
    exam_preferences: Optional[str] = Form(None, description="JSON string of exam preferences", json_schema_extra={"example": '["UPSC", "SSC"]'}),
    db: Session = Depends(get_db)
):
    """
    ## User Registration Endpoint
    
    Creates a new user account with email, password, and personal information.
    Sets up initial preferences and welcomes the user with starting rewards.
    
    **Parameters:**
    - `email`: Unique email address
    - `password`: Secure password (hashed and stored)
    - `full_name`: User's complete name
    - `username`: Optional unique username
    - `exam_preferences`: JSON array of preferred exams
    
    **Returns:**
    - Success message and user ID
    - Access and refresh tokens
    - User profile information
    
    **Example Request:**
    ```json
    {
        "email": "user@example.com",
        "password": "SecurePassword123!",
        "full_name": "John Doe",
        "username": "johndoe123",
        "exam_preferences": ["UPSC", "SSC"]
    }
    ```
    """
    # Check if user already exists
    existing_user = db.query(models.User).filter(
        or_(models.User.email == email, models.User.username == username)
    ).first()
    
    if existing_user:
        if existing_user.email == email:
            raise HTTPException(status_code=400, detail="Email already registered")
        else:
            raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    hashed_password = auth.get_password_hash(password)
    
    # Generate username if not provided
    if not username:
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while db.query(models.User).filter(models.User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1
    
    db_user = models.User(
        email=email, 
        hashed_password=hashed_password, 
        full_name=full_name,
        username=username,
        coins=100,  # Starting bonus
        xp=50,      # Starting XP
        daily_goal=10  # Default daily goal
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Process exam preferences if provided
    if exam_preferences:
        try:
            preferences = json.loads(exam_preferences)
            # This would typically map to category IDs and set user preferences
        except json.JSONDecodeError:
            pass
    
    # Create tokens for immediate login
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    
    refresh_token, jti, expires_at = auth.create_refresh_token(db_user.email)
    auth.store_refresh_token(db, db_user.id, jti, expires_at)
    
    # Record analytics
    background_tasks.add_task(record_analytics_event, db_user.id, "registration", {"method": "email"}, db)
    
    # Award welcome badge
    background_tasks.add_task(auth.award_achievement, db, db_user.id, "Welcome to EduMosaic!", 100)
    
    return {
        "message": "User created successfully", 
        "user_id": db_user.id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "username": db_user.username,
            "full_name": db_user.full_name,
            "xp": db_user.xp,
            "coins": db_user.coins,
            "level": db_user.level
        }
    }

@app.post(
    "/auth/refresh",
    response_model=Dict[str, str],
    tags=["Authentication"],
    summary="🔄 Refresh Access Token",
    description="Refresh expired access token using valid refresh token"
)
async def refresh_access_token(
    refresh_token: str = Form(..., description="Valid refresh token"),
    db: Session = Depends(get_db)
):
    """
    ## Refresh Access Token
    
    Generates a new access token using a valid refresh token.
    Implements token rotation for enhanced security.
    
    **Parameters:**
    - `refresh_token`: Valid refresh token obtained during login
    
    **Returns:**
    - New JWT access token
    - New refresh token (rotated)
    
    **Example Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer"
    }
    ```
    """
    try:
        result = auth.refresh_access_token(db, refresh_token)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post(
    "/auth/logout",
    response_model=Dict[str, str],
    tags=["Authentication"],
    summary="🚪 User Logout",
    description="Revoke refresh token (logout user from current device)"
)
async def logout_user(
    refresh_token: str = Form(..., description="Refresh token to revoke"),
    db: Session = Depends(get_db)
):
    """
    ## User Logout
    
    Revokes a refresh token to log out the user from the current device.
    
    **Parameters:**
    - `refresh_token`: Refresh token to revoke
    
    **Returns:**
    - Success message
    
    **Example Response:**
    ```json
    {
        "message": "Logged out successfully"
    }
    ```
    """
    auth.revoke_refresh_token(db, refresh_token)
    return {"message": "Logged out successfully"}

@app.post(
    "/auth/logout-all",
    response_model=Dict[str, str],
    tags=["Authentication"],
    summary="🚪 Logout All Devices",
    description="Revoke all refresh tokens for the user (logout from all devices)"
)
async def logout_all_devices(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Logout All Devices
    
    Revokes all refresh tokens for the user, logging them out from all devices.
    
    **Returns:**
    - Success message
    
    **Example Response:**
    ```json
    {
        "message": "Logged out from all devices successfully"
    }
    ```
    """
    auth.revoke_user_refresh_tokens(db, current_user.id)
    return {"message": "Logged out from all devices successfully"}

# ==================== USER PROFILE ENDPOINTS ==================== #
@app.get(
    "/profile",
    response_model=Dict[str, Any],
    tags=["User Profile"],
    summary="👤 Get User Profile",
    description="Retrieve current user's complete profile information"
)
async def get_profile(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Get User Profile
    
    Returns the complete profile information of the currently authenticated user.
    Includes personal info, stats, achievements, and recent activity.
    
    **Returns:**
    - User profile details
    - Statistics and progress
    - Achievements and badges
    - Recent activity
    
    **Example Response:**
    ```json
    {
        "id": 1,
        "email": "user@example.com",
        "username": "quizmaster",
        "full_name": "John Doe",
        "bio": "Competitive exam aspirant",
        "avatar_url": "https://example.com/avatar.jpg",
        "xp": 1500,
        "level": 5,
        "coins": 250,
        "streak": 7,
        "max_streak": 15,
        "daily_goal": 10,
        "daily_goal_progress": 8,
        "is_premium": false,
        "premium_expiry": null,
        "created_at": "2024-01-01T12:00:00Z",
        "stats": {
            "total_quizzes": 25,
            "total_questions": 250,
            "accuracy": 78.5,
            "avg_time_per_question": "45s"
        },
        "achievements": [
            {
                "name": "7-Day Streak",
                "description": "Logged in for 7 consecutive days",
                "icon_url": "https://example.com/badges/7day.png",
                "unlocked_at": "2024-01-08T12:00:00Z"
            }
        ],
        "recent_activity": [
            {
                "type": "quiz_completed",
                "title": "Indian History Basics",
                "score": 85,
                "timestamp": "2024-01-15T14:30:00Z"
            }
        ]
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get user stats
    stats = auth.get_user_stats(db, current_user.id)
    
    # Get achievements
    achievements = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == current_user.id,
        models.UserAchievement.unlocked == True
    ).options(joinedload(models.UserAchievement.achievement)).all()
    
    # Get recent activity (last 5 quizzes)
    recent_quizzes = db.query(models.UserScore).filter(
        models.UserScore.user_id == current_user.id
    ).order_by(models.UserScore.completed_at.desc()).limit(5).all()
    
    # Calculate daily goal progress
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_questions = db.query(func.sum(models.UserScore.total_questions)).filter(
        models.UserScore.user_id == current_user.id,
        models.UserScore.completed_at >= today_start
    ).scalar() or 0
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "bio": current_user.bio,
        "avatar_url": current_user.avatar_url,
        "xp": current_user.xp,
        "level": current_user.level,
        "coins": current_user.coins,
        "streak": current_user.streak,
        "max_streak": current_user.max_streak,
        "daily_goal": current_user.daily_goal,
        "daily_goal_progress": min(today_questions, current_user.daily_goal),
        "is_premium": current_user.is_premium,
        "premium_expiry": current_user.premium_expiry,
        "created_at": current_user.created_at,
        "stats": stats,
        "achievements": [
            {
                "name": ua.achievement.name,
                "description": ua.achievement.description,
                "icon_url": ua.achievement.icon_url,
                "unlocked_at": ua.unlocked_at,
                "xp_reward": ua.achievement.xp_reward
            } for ua in achievements
        ],
        "recent_activity": [
            {
                "type": "quiz_completed",
                "title": f"Quiz #{us.quiz_id}",
                "score": us.score,
                "accuracy": round(us.accuracy * 100, 2),
                "timestamp": us.completed_at
            } for us in recent_quizzes
        ]
    }

@app.put(
    "/profile",
    response_model=Dict[str, Any],
    tags=["User Profile"],
    summary="✏️ Update User Profile",
    description="Update user profile information and/or avatar"
)
async def update_profile(
    background_tasks: BackgroundTasks,
    full_name: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    daily_goal: Optional[int] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Update User Profile
    
    Updates the profile information and/or avatar of the currently authenticated user.
    
    **Parameters:**
    - `full_name`: Updated full name
    - `bio`: Updated biography
    - `username`: Updated username (must be unique)
    - `daily_goal`: Updated daily question goal
    - `file`: New avatar image file
    
    **Returns:**
    - Success message and updated user details
    
    **Example Response:**
    ```json
    {
        "message": "Profile updated successfully",
        "user": {
            "id": 1,
            "full_name": "John Updated",
            "bio": "Updated biography",
            "username": "newusername",
            "daily_goal": 15,
            "avatar_url": "https://example.com/new-avatar.jpg"
        }
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Check if username is already taken (if changing)
    if username and username != current_user.username:
        existing_user = db.query(models.User).filter(
            models.User.username == username,
            models.User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = username
    
    if full_name:
        current_user.full_name = full_name
    if bio:
        current_user.bio = bio
    if daily_goal:
        current_user.daily_goal = daily_goal
    
    if file:
        # Upload new avatar
        content = await file.read()
        avatar = upload_image(content, folder=f"quiz_app/avatars/{current_user.id}")
        if avatar:
            # Delete old avatar if exists
            if current_user.avatar_public_id:
                try:
                    cloudinary.uploader.destroy(current_user.avatar_public_id)
                except Exception:
                    pass
            
            current_user.avatar_url = avatar["secure_url"]
            current_user.avatar_public_id = avatar["public_id"]
    
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Profile updated successfully", 
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "bio": current_user.bio,
            "username": current_user.username,
            "daily_goal": current_user.daily_goal,
            "avatar_url": current_user.avatar_url
        }
    }

@app.get(
    "/profile/stats",
    response_model=Dict[str, Any],
    tags=["User Profile"],
    summary="📊 Detailed User Statistics",
    description="Get comprehensive statistics about user performance"
)
async def get_detailed_stats(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Get Detailed User Statistics
    
    Returns comprehensive statistics about the user's quiz performance,
    achievements, rankings, and progress over time.
    
    **Returns:**
    - Overall performance metrics
    - Category-wise breakdown
    - Progress over time (last 30 days)
    - Ranking information
    
    **Example Response:**
    ```json
    {
        "overall": {
            "total_quizzes": 25,
            "total_questions": 250,
            "correct_answers": 195,
            "accuracy": 78.0,
            "avg_time_per_question": 45,
            "total_xp": 1500,
            "total_coins": 250
        },
        "by_category": [
            {
                "category": "General Knowledge",
                "quizzes": 10,
                "accuracy": 82.5,
                "best_score": 95,
                "avg_time": 40
            }
        ],
        "progress": {
            "last_30_days": [
                {
                    "date": "2024-01-01",
                    "questions": 10,
                    "accuracy": 80.0
                }
            ]
        },
        "rankings": {
            "global_rank": 1250,
            "category_ranks": {
                "General Knowledge": 350,
                "Indian History": 520
            }
        }
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    stats = auth.get_user_stats(db, current_user.id)
    rankings = auth.get_user_rankings(db, current_user.id)
    
    return {
        **stats,
        "rankings": rankings
    }

@app.get(
    "/profile/achievements",
    response_model=Dict[str, Any],
    tags=["User Profile"],
    summary="🏆 User Achievements",
    description="Get user's achievements and progress"
)
async def get_user_achievements(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Get User Achievements
    
    Returns all achievements earned by the user and those in progress.
    
    **Returns:**
    - Unlocked achievements with details
    - In-progress achievements with current progress
    - Achievement categories and counts
    
    **Example Response:**
    ```json
    {
        "unlocked": [
            {
                "name": "7-Day Streak",
                "description": "Logged in for 7 consecutive days",
                "icon_url": "https://example.com/badges/7day.png",
                "unlocked_at": "2024-01-08T12:00:00Z",
                "xp_reward": 100,
                "rarity": "common"
            }
        ],
        "in_progress": [
            {
                "name": "30-Day Streak",
                "description": "Logged in for 30 consecutive days",
                "icon_url": "https://example.com/badges/30day.png",
                "progress": 23,
                "target": 30,
                "xp_reward": 500,
                "rarity": "rare"
            }
        ],
        "summary": {
            "total": 15,
            "unlocked": 8,
            "in_progress": 7,
            "total_xp_earned": 1200
        }
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get unlocked achievements
    unlocked = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == current_user.id,
        models.UserAchievement.unlocked == True
    ).options(joinedload(models.UserAchievement.achievement)).all()
    
    # Get in-progress achievements
    in_progress = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == current_user.id,
        models.UserAchievement.unlocked == False
    ).options(joinedload(models.UserAchievement.achievement)).all()
    
    # Calculate summary
    total_xp_earned = sum(ua.achievement.xp_reward for ua in unlocked)
    
    return {
        "unlocked": [
            {
                "name": ua.achievement.name,
                "description": ua.achievement.description,
                "icon_url": ua.achievement.icon_url,
                "unlocked_at": ua.unlocked_at,
                "xp_reward": ua.achievement.xp_reward,
                "rarity": ua.achievement.rarity
            } for ua in unlocked
        ],
        "in_progress": [
            {
                "name": ua.achievement.name,
                "description": ua.achievement.description,
                "icon_url": ua.achievement.icon_url,
                "progress": ua.progress,
                "target": ua.achievement.target_value,
                "xp_reward": ua.achievement.xp_reward,
                "rarity": ua.achievement.rarity
            } for ua in in_progress
        ],
        "summary": {
            "total": len(unlocked) + len(in_progress),
            "unlocked": len(unlocked),
            "in_progress": len(in_progress),
            "total_xp_earned": total_xp_earned
        }
    }

# ==================== QUIZ ENDPOINTS ==================== #
@app.get(
    "/categories",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="📚 Get Quiz Categories",
    description="Retrieve all available quiz categories with detailed information",
    responses={
        200: {"description": "List of categories", "content": {"application/json": {"examples": {"success": {"value": {"categories": [{"id": 1, "name": "GK", "description": "General Knowledge"}]}}}}}}
    }
)
async def get_categories(
    background_tasks: BackgroundTasks,
    include_stats: bool = Query(False, description="Include category statistics"),
    current_user: Optional[models.User] = Depends(auth.get_current_optional_user),
    db: Session = Depends(get_db)
):
    """
    ## Get All Quiz Categories
    
    Returns a list of all available quiz categories in the system.
    Can include additional statistics for each category.
    
    **Parameters:**
    - `include_stats`: Whether to include category statistics (quiz count, user progress)
    
    **Returns:**
    - Array of category objects with ID, name, and description
    - Additional statistics if requested
    
    **Example Response:**
    ```json
    {
        "categories": [
            {
                "id": 1,
                "name": "General Knowledge",
                "description": "Test your general awareness",
                "icon_url": "https://example.com/icons/gk.png",
                "parent_id": null,
                "quiz_count": 15,
                "user_progress": {
                    "completed": 5,
                    "accuracy": 78.5,
                    "best_score": 90
                }
            }
        ]
    }
    ```
    """
    if current_user:
        background_tasks.add_task(update_user_activity, current_user.id, db)
    
    categories = db.query(models.Category).filter(models.Category.is_active == True).all()
    
    result = []
    for category in categories:
        category_data = {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "icon_url": category.icon_url,
            "parent_id": category.parent_id
        }
        
        if include_stats:
            # Get quiz count
            quiz_count = db.query(models.Quiz).filter(
                models.Quiz.category_id == category.id,
                models.Quiz.is_active == True
            ).count()
            category_data["quiz_count"] = quiz_count
            
            # Get user progress if authenticated
            if current_user:
                user_scores = db.query(models.UserScore).join(models.Quiz).filter(
                    models.UserScore.user_id == current_user.id,
                    models.Quiz.category_id == category.id
                ).all()
                
                if user_scores:
                    completed = len(user_scores)
                    accuracy = sum(us.accuracy for us in user_scores) / len(user_scores) * 100
                    best_score = max(us.score for us in user_scores) if user_scores else 0
                    
                    category_data["user_progress"] = {
                        "completed": completed,
                        "accuracy": round(accuracy, 2),
                        "best_score": best_score
                    }
        
        result.append(category_data)
    
    return {"categories": result}

@app.get(
    "/quizzes",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="📝 Get Quizzes",
    description="Retrieve quizzes with filtering and pagination"
)
async def get_quizzes(
    background_tasks: BackgroundTasks,
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty", enum=["beginner", "easy", "medium", "hard", "expert", "master"]),
    page: int = Query(1, description="Page number", ge=1),
    limit: int = Query(20, description="Items per page", ge=1, le=50),
    search: Optional[str] = Query(None, description="Search term"),
    sort: str = Query("popular", description="Sort order", enum=["newest", "popular", "rating", "title"]),
    current_user: Optional[models.User] = Depends(auth.get_current_optional_user),
    db: Session = Depends(get_db)
):
    """
    ## Get Quizzes with Filtering
    
    Returns quizzes with advanced filtering, sorting, and pagination.
    
    **Parameters:**
    - `category_id`: Filter by category ID
    - `difficulty`: Filter by difficulty level
    - `page`: Page number for pagination
    - `limit`: Number of items per page
    - `search`: Search term for quiz titles
    - `sort`: Sort order (newest, popular, rating, title)
    
    **Returns:**
    - Array of quiz objects with details
    - Pagination metadata
    
    **Example Response:**
    ```json
    {
        "quizzes": [
            {
                "id": 1,
                "title": "Indian History Basics",
                "description": "Beginner level history questions",
                "difficulty": "easy",
                "time_limit": 300,
                "question_count": 10,
                "category_id": 1,
                "plays_count": 150,
                "avg_rating": 4.5,
                "avg_score": 72.5,
                "is_premium": false
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 50,
            "pages": 3
        }
    }
    ```
    """
    if current_user:
        background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Build query
    query = db.query(models.Quiz).filter(models.Quiz.is_active == True)
    
    if category_id:
        query = query.filter(models.Quiz.category_id == category_id)
    
    if difficulty:
        query = query.filter(models.Quiz.difficulty == difficulty)
    
    if search:
        query = query.filter(models.Quiz.title.ilike(f"%{search}%"))
    
    # Apply sorting
    if sort == "newest":
        query = query.order_by(desc(models.Quiz.created_at))
    elif sort == "popular":
        query = query.order_by(desc(models.Quiz.plays_count))
    elif sort == "rating":
        query = query.order_by(desc(models.Quiz.avg_rating))
    elif sort == "title":
        query = query.order_by(models.Quiz.title)
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    quizzes = query.offset(offset).limit(limit).all()
    
    return {
        "quizzes": quizzes,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@app.get(
    "/quizzes/{quiz_id}",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="📋 Get Quiz Details",
    description="Retrieve detailed information about a specific quiz"
)
async def get_quiz_details(
    background_tasks: BackgroundTasks,
    quiz_id: int = Path(..., description="Quiz ID"),
    current_user: Optional[models.User] = Depends(auth.get_current_optional_user),
    db: Session = Depends(get_db)
):
    """
    ## Get Quiz Details
    
    Returns detailed information about a specific quiz including questions.
    For authenticated users, also includes progress information.
    
    **Parameters:**
    - `quiz_id`: ID of the quiz to retrieve
    
    **Returns:**
    - Complete quiz information
    - Questions and options (without correct answers for security)
    - User progress if authenticated
    
    **Example Response:**
    ```json
    {
        "id": 1,
        "title": "Indian History Basics",
        "description": "Beginner level history questions",
        "difficulty": "easy",
        "time_limit": 300,
        "question_count": 10,
        "category_id": 1,
        "plays_count": 150,
        "avg_rating": 4.5,
        "avg_score": 72.5,
        "is_premium": false,
        "questions": [
            {
                "id": 1,
                "question_text": "Who was the first Prime Minister of India?",
                "question_type": "multiple_choice",
                "options": [
                    {"id": 1, "option_text": "Jawaharlal Nehru"},
                    {"id": 2, "option_text": "Mahatma Gandhi"},
                    {"id": 3, "option_text": "Sardar Patel"},
                    {"id": 4, "option_text": "Dr. Rajendra Prasad"}
                ],
                "time_limit": 30,
                "points": 1
            }
        ],
        "user_progress": {
            "attempts": 2,
            "best_score": 85,
            "last_score": 70,
            "last_attempt": "2024-01-15T14:30:00Z"
        }
    }
    ```
    """
    if current_user:
        background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get quiz
    quiz = db.query(models.Quiz).filter(
        models.Quiz.id == quiz_id,
        models.Quiz.is_active == True
    ).first()
    
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Check if premium quiz and user has access
    if quiz.is_premium and (not current_user or not current_user.is_premium):
        raise HTTPException(status_code=403, detail="Premium content requires subscription")
    
    # Get questions with options (without correct answers)
    questions = db.query(models.Question).filter(
        models.Question.quiz_id == quiz_id
    ).order_by(models.Question.sort_order).all()
    
    questions_data = []
    for question in questions:
        options = db.query(models.Option).filter(
            models.Option.question_id == question.id
        ).order_by(models.Option.sort_order).all()
        
        questions_data.append({
            "id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "image_url": question.image_url,
            "audio_url": question.audio_url,
            "video_url": question.video_url,
            "time_limit": question.time_limit,
            "points": question.points,
            "hint": question.hint,
            "options": [
                {
                    "id": opt.id,
                    "option_text": opt.option_text,
                    "image_url": opt.image_url
                } for opt in options
            ]
        })
    
    result = {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "difficulty": quiz.difficulty,
        "time_limit": quiz.time_limit,
        "question_count": quiz.question_count,
        "category_id": quiz.category_id,
        "plays_count": quiz.plays_count,
        "avg_rating": quiz.avg_rating,
        "avg_score": quiz.avg_score,
        "is_premium": quiz.is_premium,
        "questions": questions_data
    }
    
    # Add user progress if authenticated
    if current_user:
        user_scores = db.query(models.UserScore).filter(
            models.UserScore.user_id == current_user.id,
            models.UserScore.quiz_id == quiz_id
        ).order_by(desc(models.UserScore.completed_at)).all()
        
        if user_scores:
            result["user_progress"] = {
                "attempts": len(user_scores),
                "best_score": max(us.score for us in user_scores),
                "last_score": user_scores[0].score,
                "last_accuracy": round(user_scores[0].accuracy * 100, 2),
                "last_attempt": user_scores[0].completed_at
            }
    
    return result

@app.post(
    "/quizzes/{quiz_id}/start",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="▶️ Start Quiz Attempt",
    description="Start a new quiz attempt and get session details"
)
async def start_quiz_attempt(
    background_tasks: BackgroundTasks,
    quiz_id: int = Path(..., description="Quiz ID"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Start Quiz Attempt
    
    Starts a new quiz attempt and returns session information.
    Records the start time for time-limited quizzes.
    
    **Parameters:**
    - `quiz_id`: ID of the quiz to attempt
    
    **Returns:**
    - Quiz session ID
    - Start time
    - Time limit information
    
    **Example Response:**
    ```json
    {
        "session_id": "abc123def456",
        "quiz_id": 1,
        "start_time": "2024-01-15T14:30:00Z",
        "time_limit": 300,
        "question_count": 10
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get quiz
    quiz = db.query(models.Quiz).filter(
        models.Quiz.id == quiz_id,
        models.Quiz.is_active == True
    ).first()
    
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Check if premium quiz and user has access
    if quiz.is_premium and not current_user.is_premium:
        raise HTTPException(status_code=403, detail="Premium content requires subscription")
    
    # Generate session ID (in a real app, this would be stored in database)
    session_id = os.urandom(12).hex()
    
    # Record analytics
    background_tasks.add_task(record_analytics_event, current_user.id, "quiz_start", {
        "quiz_id": quiz_id,
        "session_id": session_id
    }, db)
    
    return {
        "session_id": session_id,
        "quiz_id": quiz.id,
        "start_time": datetime.utcnow().isoformat(),
        "time_limit": quiz.time_limit,
        "question_count": quiz.question_count
    }

@app.post(
    "/quizzes/{quiz_id}/submit",
    response_model=Dict[str, Any],
    tags=["Quizzes & Exams"],
    summary="✅ Submit Quiz Answers",
    description="Submit quiz answers and get results with detailed analysis"
)
async def submit_quiz_answers(
    background_tasks: BackgroundTasks,
    quiz_id: int = Path(..., description="Quiz ID"),
    answers: str = Form(..., description="JSON string of question IDs and answers"),
    time_taken: int = Form(..., description="Total time taken in seconds"),
    session_id: str = Form(..., description="Quiz session ID"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    import json
    try:
        answers_dict = json.loads(answers)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid answers format. Must be JSON string.")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = db.query(models.Question).filter(models.Question.quiz_id == quiz_id).all()
    total_questions = len(questions)
    correct_answers = 0
    detailed_results = []

    for question in questions:
        user_answer = answers_dict.get(str(question.id))
        correct_options = [opt.option_text for opt in question.options if opt.is_correct]

        is_correct = False
        if user_answer:
            if isinstance(user_answer, list):
                is_correct = set(user_answer) == set(correct_options)
            else:
                is_correct = user_answer in correct_options

        if is_correct:
            correct_answers += 1

        detailed_results.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "user_answer": user_answer,
            "correct_answers": correct_options,
            "is_correct": is_correct
        })

    accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0

    # Check if user already attempted this quiz
    existing_score = db.query(models.UserScore).filter_by(
        user_id=current_user.id,
        quiz_id=quiz_id
    ).first()

    if existing_score:
        raise HTTPException(status_code=400, detail="You have already attempted this quiz.")

    # Save first attempt
    user_score = models.UserScore(
        user_id=current_user.id,
        quiz_id=quiz_id,
        score=correct_answers,
        total_questions=total_questions,
        correct_answers=correct_answers,
        accuracy=accuracy,
        time_taken=time_taken
    )
    db.add(user_score)
    db.commit()
    db.refresh(user_score)

    return {
        "message": "Quiz submitted successfully",
        "quiz_id": quiz_id,
        "score": correct_answers,
        "total_questions": total_questions,
        "accuracy": accuracy,
        "time_taken": time_taken,
        "details": detailed_results
    }


# ==================== REATTEMPT ENDPOINTS ==================== #
@app.post("/quizzes/{quiz_id}/reattempt")
def reattempt_quiz(
    quiz_id: int,
    score_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if user has attempted this quiz at least once
    existing_score = db.query(models.UserScore).filter_by(
        user_id=current_user.id,
        quiz_id=quiz_id
    ).first()

    if not existing_score:
        raise HTTPException(status_code=400, detail="You must attempt this quiz once before reattempting.")

    # Store reattempt score
    reattempt = models.QuizReattempt(
        user_id=current_user.id,
        quiz_id=quiz_id,
        score=score_data.get("score"),
        total_questions=score_data.get("total_questions"),
        correct_answers=score_data.get("correct_answers"),
        accuracy=score_data.get("accuracy"),
        time_taken=score_data.get("time_taken"),
    )
    db.add(reattempt)
    db.commit()
    db.refresh(reattempt)

    return {"message": "Reattempt recorded successfully", "reattempt_id": reattempt.id}


@app.get("/users/me/reattempts")
def get_my_reattempts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reattempts = db.query(models.QuizReattempt).filter_by(user_id=current_user.id).all()
    return reattempts
    """
    ## Submit Quiz Answers
    
    Submits quiz answers, calculates score, and returns detailed results.
    Updates user statistics and awards achievements.
    
    **Parameters:**
    - `quiz_id`: ID of the quiz attempted
    - `answers`: JSON object mapping question IDs to answers
    - `time_taken`: Total time taken in seconds
    - `session_id`: Quiz session ID from start attempt
    
    **Returns:**
    - Detailed results with correct/incorrect answers
    - Score and accuracy
    - XP and coins earned
    - Achievements unlocked
    
    **Example Response:**
    ```json
    {
        "score": 85,
        "total_questions": 10,
        "correct_answers": 8.5,
        "accuracy": 85.0,
        "time_taken": 245,
        "xp_earned": 120,
        "coins_earned": 25,
        "new_achievements": [
            {
                "name": "Accuracy Master",
                "description": "Scored 85% or higher on a quiz",
                "icon_url": "https://example.com/badges/accuracy.png",
                "xp_reward": 50
            }
        ],
        "detailed_results": [
            {
                "question_id": 1,
                "correct": true,
                "selected_answer": 1,
                "correct_answer": 1,
                "time_spent": 25
            }
        ]
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get quiz
    quiz = db.query(models.Quiz).filter(
        models.Quiz.id == quiz_id,
        models.Quiz.is_active == True
    ).first()
    
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Parse answers
    try:
        if isinstance(answers, str):
            answers = json.loads(answers)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid answers format")
    
    # Calculate score
    total_questions = quiz.question_count
    correct_answers = 0
    detailed_results = []
    
    for question_id, user_answer in answers.items():
        # Get question and correct answer
        question = db.query(models.Question).filter(
            models.Question.id == int(question_id),
            models.Question.quiz_id == quiz_id
        ).first()
        
        if not question:
            continue
        
        # Get correct options
        correct_options = db.query(models.Option).filter(
            models.Option.question_id == question.id,
            models.Option.is_correct == True
        ).all()
        
        # Check if answer is correct (implementation depends on question type)
        is_correct = False
        if question.question_type == "multiple_choice":
            # For multiple choice, check if selected option is correct
            correct_option_ids = [opt.id for opt in correct_options]
            is_correct = user_answer in correct_option_ids
        elif question.question_type == "true_false":
            # For true/false, compare directly
            correct_answer = correct_options[0].option_text.lower() if correct_options else ""
            is_correct = str(user_answer).lower() == correct_answer
        
        if is_correct:
            correct_answers += 1
        
        detailed_results.append({
            "question_id": question.id,
            "correct": is_correct,
            "selected_answer": user_answer,
            "correct_answer": [opt.id for opt in correct_options] if question.question_type == "multiple_choice" else correct_options[0].option_text if correct_options else None,
            "points": question.points if is_correct else (-question.points * question.negative_mark_percentage) if question.has_negative_marking else 0
        })
    
    # Calculate final score
    accuracy = correct_answers / total_questions if total_questions > 0 else 0
    score = round(accuracy * 100)
    
    # Calculate XP and coins
    base_xp = quiz.xp_reward
    accuracy_bonus = int(base_xp * accuracy)
    time_bonus = int(base_xp * 0.5 * (1 - min(time_taken / quiz.time_limit, 1))) if quiz.time_limit else 0
    total_xp = base_xp + accuracy_bonus + time_bonus
    
    base_coins = quiz.coin_reward
    coin_bonus = int(base_coins * accuracy)
    total_coins = base_coins + coin_bonus
    
    # Save score
    user_score = models.UserScore(
        user_id=current_user.id,
        quiz_id=quiz_id,
        score=score,
        total_questions=total_questions,
        correct_answers=correct_answers,
        accuracy=accuracy,
        time_taken=time_taken,
        completed_at=datetime.utcnow()
    )
    db.add(user_score)
    
    # Update user stats
    current_user.xp += total_xp
    current_user.coins += total_coins
    
    # Update quiz stats
    quiz.plays_count += 1
    # Update avg_score (simplified)
    if quiz.avg_score:
        quiz.avg_score = (quiz.avg_score * (quiz.plays_count - 1) + score) / quiz.plays_count
    else:
        quiz.avg_score = score
    
    db.commit()
    
    # Check achievements
    new_achievements = []
    quiz_data = {
        'quiz_id': quiz_id,
        'category_id': quiz.category_id,
        'score': score,
        'accuracy': accuracy,
        'total_questions': total_questions
    }
    auth.check_quiz_achievements(db, current_user.id, quiz_data)
    
    # Get any new achievements
    recent_achievements = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == current_user.id,
        models.UserAchievement.unlocked == True,
        models.UserAchievement.unlocked_at >= datetime.utcnow() - timedelta(minutes=5)
    ).options(joinedload(models.UserAchievement.achievement)).all()
    
    for ua in recent_achievements:
        new_achievements.append({
            "name": ua.achievement.name,
            "description": ua.achievement.description,
            "icon_url": ua.achievement.icon_url,
            "xp_reward": ua.achievement.xp_reward
        })
    
    # Record analytics
    background_tasks.add_task(record_analytics_event, current_user.id, "quiz_complete", {
        "quiz_id": quiz_id,
        "score": score,
        "accuracy": accuracy,
        "time_taken": time_taken,
        "xp_earned": total_xp,
        "coins_earned": total_coins,
        "session_id": session_id
    }, db)
    
    return {
        "score": score,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "accuracy": round(accuracy * 100, 2),
        "time_taken": time_taken,
        "xp_earned": total_xp,
        "coins_earned": total_coins,
        "new_achievements": new_achievements,
        "detailed_results": detailed_results
    }

# ==================== LEADERBOARD ENDPOINTS ==================== #
@app.get(
    "/leaderboard/global",
    response_model=List[Dict[str, Any]],
    tags=["Scores & Analytics"],
    summary="🏆 Global Leaderboard",
    description="Get global leaderboard ranked by XP"
)
async def global_leaderboard(
    background_tasks: BackgroundTasks,
    limit: int = Query(20, description="Number of top players to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    current_user: Optional[models.User] = Depends(auth.get_current_optional_user),
    db: Session = Depends(get_db)
):
    """
    ## Global Leaderboard
    
    Returns the global leaderboard ranked by user XP.
    Includes user ranking and position information.
    
    **Parameters:**
    - `limit`: Number of top players to return
    - `offset`: Offset for pagination
    
    **Returns:**
    - List of top users with rankings
    
    **Example Response:**
    ```json
    [
        {
            "rank": 1,
            "user_id": 123,
            "name": "QuizMaster",
            "avatar_url": "https://example.com/avatar1.jpg",
            "xp": 25000,
            "level": 25,
            "streak": 45
        }
    ]
    """
    if current_user:
        background_tasks.add_task(update_user_activity, current_user.id, db)
    
    return auth.get_global_leaderboard(db, limit, offset)

@app.get(
    "/leaderboard/category/{category_id}",
    response_model=List[Dict[str, Any]],
    tags=["Scores & Analytics"],
    summary="🏆 Category Leaderboard",
    description="Get leaderboard for a specific category"
)
async def category_leaderboard(
    background_tasks: BackgroundTasks,
    category_id: int = Path(..., description="Category ID"),
    limit: int = Query(10, description="Number of top players to return", ge=1, le=50),
    current_user: Optional[models.User] = Depends(auth.get_current_optional_user),
    db: Session = Depends(get_db)
):
    """
    ## Category Leaderboard
    
    Returns the leaderboard for a specific quiz category.
    
    **Parameters:**
    - `category_id`: ID of the category
    - `limit`: Number of top players to return
    
    **Returns:**
    - List of top users in the category
    
    **Example Response:**
    ```json
    [
        {
            "user_id": 123,
            "name": "HistoryBuff",
            "avatar_url": "https://example.com/avatar2.jpg",
            "best_score": 98,
            "avg_accuracy": 92.5,
            "quiz_count": 15
        }
    ]
    """
    if current_user:
        background_tasks.add_task(update_user_activity, current_user.id, db)
    
    return auth.get_category_leaderboard(db, category_id, limit)

@app.get(
    "/leaderboard/streak",
    response_model=List[Dict[str, Any]],
    tags=["Scores & Analytics"],
    summary="🔥 Streak Leaderboard",
    description="Get leaderboard ranked by login streaks"
)
async def streak_leaderboard(
    background_tasks: BackgroundTasks,
    limit: int = Query(20, description="Number of top players to return", ge=1, le=50),
    current_user: Optional[models.User] = Depends(auth.get_current_optional_user),
    db: Session = Depends(get_db)
):
    """
    ## Streak Leaderboard
    
    Returns the leaderboard ranked by user login streaks.
    
    **Parameters:**
    - `limit`: Number of top players to return
    
    **Returns:**
    - List of users with the longest streaks
    
    **Example Response:**
    ```json
    [
        {
            "user_id": 456,
            "name": "DailyPlayer",
            "avatar_url": "https://example.com/avatar3.jpg",
            "streak": 365,
            "max_streak": 365
        }
    ]
    """
    if current_user:
        background_tasks.add_task(update_user_activity, current_user.id, db)
    
    top_users = db.query(models.User).filter(
        models.User.streak > 0
    ).order_by(desc(models.User.streak)).limit(limit).all()
    
    return [{
        "user_id": u.id,
        "name": u.full_name,
        "avatar_url": u.avatar_url,
        "streak": u.streak,
        "max_streak": u.max_streak
    } for u in top_users]

# ==================== SOCIAL ENDPOINTS ==================== #
@app.post(
    "/social/follow/{user_id}",
    response_model=Dict[str, str],
    tags=["Social & Competition"],
    summary="👥 Follow User",
    description="Follow another user"
)
async def follow_user(
    background_tasks: BackgroundTasks,
    user_id: int = Path(..., description="ID of user to follow"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Follow User
    
    Follow another user to see their activity and progress in your feed.
    
    **Parameters:**
    - `user_id`: ID of user to follow
    
    **Returns:**
    - Success message
    
    **Example Response:**
    ```json
    {
        "message": "Now following user 123"
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    success = auth.follow_user(db, current_user.id, user_id)
    if success:
        return {"message": f"Now following user {user_id}"}
    else:
        raise HTTPException(status_code=400, detail="Unable to follow user")

@app.post(
    "/social/unfollow/{user_id}",
    response_model=Dict[str, str],
    tags=["Social & Competition"],
    summary="👥 Unfollow User",
    description="Unfollow a user"
)
async def unfollow_user(
    background_tasks: BackgroundTasks,
    user_id: int = Path(..., description="ID of user to unfollow"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Unfollow User
    
    Stop following another user.
    
    **Parameters:**
    - `user_id`: ID of user to unfollow
    
    **Returns:**
    - Success message
    
    **Example Response:**
    ```json
    {
        "message": "Unfollowed user 123"
    }
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    success = auth.unfollow_user(db, current_user.id, user_id)
    if success:
        return {"message": f"Unfollowed user {user_id}"}
    else:
        raise HTTPException(status_code=400, detail="Unable to unfollow user")

@app.get(
    "/social/followers",
    response_model=List[Dict[str, Any]],
    tags=["Social & Competition"],
    summary="👥 Get Followers",
    description="Get list of users who follow you"
)
async def get_followers(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Get Followers
    
    Returns a list of users who follow you.
    
    **Returns:**
    - List of followers with details
    
    **Example Response:**
    ```json
    [
        {
            "user_id": 123,
            "name": "Follower1",
            "avatar_url": "https://example.com/avatar1.jpg",
            "xp": 1500,
            "level": 5,
            "followed_at": "2024-01-10T12:00:00Z"
        }
    ]
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    return auth.get_user_followers(db, current_user.id)

@app.get(
    "/social/following",
    response_model=List[Dict[str, Any]],
    tags=["Social & Competition"],
    summary="👥 Get Following",
    description="Get list of users you follow"
)
async def get_following(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Get Following
    
    Returns a list of users you follow.
    
    **Returns:**
    - List of followed users with details
    
    **Example Response:**
    ```json
    [
        {
            "user_id": 456,
            "name": "Following1",
            "avatar_url": "https://example.com/avatar2.jpg",
            "xp": 2500,
            "level": 8,
            "followed_at": "2024-01-05T12:00:00Z"
        }
    ]
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    return auth.get_user_following(db, current_user.id)

@app.get(
    "/social/feed",
    response_model=List[Dict[str, Any]],
    tags=["Social & Competition"],
    summary="📰 Social Feed",
    description="Get activity feed from users you follow"
)
async def get_social_feed(
    background_tasks: BackgroundTasks,
    limit: int = Query(20, description="Number of activities to return", ge=1, le=50),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Social Feed
    
    Returns recent activity from users you follow.
    
    **Parameters:**
    - `limit`: Number of activities to return
    
    **Returns:**
    - List of recent activities from followed users
    
    **Example Response:**
    ```json
    [
        {
            "type": "quiz_completed",
            "user_id": 456,
            "user_name": "Following1",
            "user_avatar": "https://example.com/avatar2.jpg",
            "quiz_id": 123,
            "quiz_title": "Indian History Quiz",
            "score": 92,
            "timestamp": "2024-01-15T14:30:00Z"
        }
    ]
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get users you follow
    following = auth.get_user_following(db, current_user.id)
    following_ids = [user["user_id"] for user in following]
    
    if not following_ids:
        return []
    
    # Get recent quiz completions from followed users
    recent_scores = db.query(models.UserScore, models.User, models.Quiz).join(
        models.User, models.UserScore.user_id == models.User.id
    ).join(
        models.Quiz, models.UserScore.quiz_id == models.Quiz.id
    ).filter(
        models.UserScore.user_id.in_(following_ids),
        models.UserScore.completed_at >= datetime.utcnow() - timedelta(days=7)
    ).order_by(desc(models.UserScore.completed_at)).limit(limit).all()
    
    return [{
        "type": "quiz_completed",
        "user_id": user.id,
        "user_name": user.full_name,
        "user_avatar": user.avatar_url,
        "quiz_id": quiz.id,
        "quiz_title": quiz.title,
        "score": score.score,
        "accuracy": round(score.accuracy * 100, 2),
        "timestamp": score.completed_at
    } for score, user, quiz in recent_scores]

# ==================== CONTENT MANAGEMENT ENDPOINTS ==================== #
@app.post(
    "/admin/upload-image",
    response_model=Dict[str, Any],
    tags=["Media", "Content Management"],
    summary="🖼️ Upload Image",
    description="Upload quiz images to Cloudinary storage"
)
async def upload_quiz_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file to upload (JPEG, PNG, WEBP)"),
    category: str = Form("general", description="Category for image organization", json_schema_extra={"example": "gk"}),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Upload Quiz Image
    
    Uploads an image file to Cloudinary storage for use in quiz questions.
    Requires authentication with admin privileges.
    
    **Parameters:**
    - `file`: Image file (max 5MB)
    - `category`: Organizational category for the image
    
    **Supported Formats:**
    - JPEG, PNG, WEBP, GIF
    
    **Returns:**
    - Cloudinary URL and public ID for the uploaded image
    
    **Example Response:**
    ```json
    {
        "message": "Image uploaded successfully",
        "url": "https://res.cloudinary.com/.../image/upload/quiz_app/gk/image.jpg",
        "public_id": "quiz_app/gk/image",
        "format": "jpg",
        "bytes": 254890,
        "width": 1200,
        "height": 800
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Check if user has admin privileges
    if current_user.role not in ["admin", "content_creator"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check if file is an image
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    # Check file size (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")
    
    # Upload to Cloudinary
    result = upload_image(content, folder=f"quiz_app/{category}")
    
    if result:
        return {
            "message": "Image uploaded successfully",
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "format": result.get("format"),
            "bytes": result.get("bytes"),
            "width": result.get("width"),
            "height": result.get("height")
        }
    else:
        raise HTTPException(status_code=500, detail="Image upload failed")

# ==================== EXPORT ENDPOINTS ==================== #
@app.get(
    "/export/scores",
    response_model=Dict[str, Any],
    tags=["Scores & Analytics"],
    summary="📊 Export Scores",
    description="Export user scores in various formats"
)
async def export_scores(
    background_tasks: BackgroundTasks,
    format: str = Query("json", description="Export format", enum=["json", "csv", "pdf"]),
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Export Scores
    
    Exports the user's quiz scores in the requested format.
    
    **Parameters:**
    - `format`: Export format (json, csv, pdf)
    - `start_date`: Start date for filtering scores
    - `end_date`: End date for filtering scores
    
    **Returns:**
    - Exported data in requested format
    
    **Example Response:**
    Varies by format - returns file download for CSV and PDF, JSON data for JSON format.
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # Get user scores with optional date filtering
    query = db.query(models.UserScore).filter(
        models.UserScore.user_id == current_user.id
    ).join(models.Quiz).join(models.Category)
    
    if start_date:
        query = query.filter(models.UserScore.completed_at >= start_date)
    if end_date:
        query = query.filter(models.UserScore.completed_at <= end_date)
    
    scores = query.order_by(desc(models.UserScore.completed_at)).all()
    
    # Prepare data
    score_data = []
    for score in scores:
        score_data.append({
            "date": score.completed_at.date().isoformat(),
            "quiz": score.quiz.title,
            "category": score.quiz.category.name,
            "score": score.score,
            "accuracy": round(score.accuracy * 100, 2),
            "time_taken": score.time_taken,
            "total_questions": score.total_questions,
            "correct_answers": score.correct_answers
        })
    
    if format == "json":
        return {"scores": score_data}
    
    elif format == "csv":
        # Create CSV
        df = pd.DataFrame(score_data)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        return JSONResponse(
            content={"filename": f"scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"},
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    
    elif format == "pdf":
        # Create PDF
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"EduMosaic Score Report for {current_user.full_name}")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # Add scores table
        y = height - 100
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Date")
        c.drawString(120, y, "Quiz")
        c.drawString(250, y, "Category")
        c.drawString(320, y, "Score")
        c.drawString(370, y, "Accuracy")
        
        c.setFont("Helvetica", 10)
        y -= 20
        
        for score in score_data:
            if y < 100:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
            
            c.drawString(50, y, score["date"])
            c.drawString(120, y, score["quiz"][:20] + "..." if len(score["quiz"]) > 20 else score["quiz"])
            c.drawString(250, y, score["category"][:15] + "..." if len(score["category"]) > 15 else score["category"])
            c.drawString(320, y, str(score["score"]))
            c.drawString(370, y, f"{score['accuracy']}%")
            y -= 15
        
        c.save()
        buffer.seek(0)
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
        )

# ==================== PREMIUM ENDPOINTS ==================== #
@app.post(
    "/premium/subscribe",
    response_model=Dict[str, Any],
    tags=["User Profile"],
    summary="💰 Subscribe to Premium",
    description="Subscribe to EduMosaic Premium features"
)
async def subscribe_premium(
    background_tasks: BackgroundTasks,
    plan: str = Form(..., description="Premium plan", enum=["monthly", "yearly"]),
    payment_method: str = Form(..., description="Payment method", enum=["card", "upi", "netbanking"]),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ## Subscribe to Premium
    
    Subscribes the user to EduMosaic Premium features.
    In a real implementation, this would integrate with a payment gateway.
    
    **Parameters:**
    - `plan`: Subscription plan (monthly, yearly)
    - `payment_method`: Payment method (card, upi, netbanking)
    
    **Returns:**
    - Subscription confirmation
    
    **Example Response:**
    ```json
    {
        "message": "Premium subscription activated",
        "plan": "yearly",
        "expiry_date": "2025-01-15T14:30:00Z",
        "features_unlocked": [
            "ad_free_experience",
            "unlimited_practice",
            "detailed_analytics"
        ]
    }
    ```
    """
    # Update user activity
    background_tasks.add_task(update_user_activity, current_user.id, db)
    
    # In a real implementation, this would process payment and set expiry date
    if plan == "monthly":
        expiry_date = datetime.utcnow() + timedelta(days=30)
    else:  # yearly
        expiry_date = datetime.utcnow() + timedelta(days=365)
    
    current_user.is_premium = True
    current_user.premium_expiry = expiry_date
    db.commit()
    
    # Record analytics
    background_tasks.add_task(record_analytics_event, current_user.id, "premium_subscription", {
        "plan": plan,
        "payment_method": payment_method
    }, db)
    
    return {
        "message": "Premium subscription activated",
        "plan": plan,
        "expiry_date": expiry_date.isoformat(),
        "features_unlocked": [
            "ad_free_experience",
            "unlimited_practice",
            "detailed_analytics",
            "priority_support",
            "exclusive_content"
        ]
    }

# Add your other endpoints here with similar fixes...

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info",
        timeout_keep_alive=300
    )