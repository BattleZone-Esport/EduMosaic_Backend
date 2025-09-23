"""
Configuration management for EduMosaic Backend
Handles all environment variables and application settings
"""

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, BaseModel, EmailStr, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main Settings for EduMosaic Application"""

    # Application Settings
    PROJECT_NAME: str = "EduMosaic Backend API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    API_V2_STR: str = "/api/v2"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Security Settings
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_MIN_LENGTH: int = 8

    # CORS Settings - DO NOT MODIFY EXISTING CONFIGURATION
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    CORS_ALLOW_ALL_ORIGINS: bool = True
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "edumosaic"
    DATABASE_URL: Optional[str] = None

    # Connection Pool Settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=values.data.get("POSTGRES_USER"),
            password=values.data.get("POSTGRES_PASSWORD"),
            host=values.data.get("POSTGRES_SERVER"),
            path=values.data.get("POSTGRES_DB") or "",
        )

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_POOL_MAX_CONNECTIONS: int = 10
    REDIS_CACHE_TTL: int = 3600  # 1 hour default
    REDIS_ENABLED: bool = True

    # Cloudinary Settings
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    CLOUDINARY_ENABLED: bool = True

    # Email Settings
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = 587
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = "EduMosaic"
    EMAILS_ENABLED: bool = False

    # Sentry Settings
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1

    # Rate Limiting Settings
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "200 per minute"
    RATE_LIMIT_PER_IP: str = "100 per minute"
    RATE_LIMIT_AUTH: str = "5 per minute"

    # AI Module Settings
    AI_ENABLED: bool = True
    AI_SERVICE_URL: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-3.5-turbo"
    AI_MAX_TOKENS: int = 1000
    AI_TEMPERATURE: float = 0.7

    # Google reCAPTCHA Settings
    RECAPTCHA_SECRET_KEY: Optional[str] = None
    RECAPTCHA_SITE_KEY: Optional[str] = None
    RECAPTCHA_ENABLED: bool = False

    # File Upload Settings
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_IMAGE_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ALLOWED_DOCUMENT_EXTENSIONS: List[str] = [".pdf", ".doc", ".docx"]

    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = (
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )
    LOG_FILE: str = "logs/edumosaic.log"
    LOG_MAX_BYTES: int = 10485760  # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # Pagination Settings
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # XP and Gamification Settings
    XP_PER_CORRECT_ANSWER: int = 10
    XP_PER_QUIZ_COMPLETION: int = 50
    XP_PER_LEVEL: int = 1000
    XP_BONUS_STREAK: int = 5

    # Security Headers
    SECURITY_HEADERS_ENABLED: bool = True

    # Monitoring Settings
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # Feature Flags
    FEATURE_SOCIAL_LOGIN: bool = False
    FEATURE_PAYMENT: bool = False
    FEATURE_CHAT: bool = False
    FEATURE_VIDEO_QUIZ: bool = False
    FEATURE_AI_QUIZ_GENERATION: bool = True
    FEATURE_RECOMMENDATION_ENGINE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    def get_db_url(self) -> str:
        """Get database URL for SQLAlchemy"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

    def get_redis_url(self) -> str:
        """Get Redis URL with password if provided"""
        if self.REDIS_PASSWORD:
            return self.REDIS_URL.replace("redis://", f"redis://:{self.REDIS_PASSWORD}@")
        return self.REDIS_URL

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT.lower() in ["production", "prod"]

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT.lower() in ["development", "dev"]

    def is_testing(self) -> bool:
        """Check if running in testing"""
        return self.ENVIRONMENT.lower() in ["testing", "test"]


@lru_cache()
def get_settings() -> Settings:
    """
    Create cached settings instance
    Use this function to get settings throughout the application
    """
    return Settings()


# Create a global settings instance
settings = get_settings()
