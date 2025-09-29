"""
Core configuration for EduMosaic Backend
India's No 1 Quiz Application
"""

import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
import secrets

class Settings(BaseSettings):
    """Application settings"""
    
    # Application Settings
    APP_NAME: str = "EduMosaic"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "India's No 1 Quiz Application Backend"
    DEBUG: bool = Field(default=False)
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "EduMosaic Backend"
    
    # Security
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    BCRYPT_ROUNDS: int = 12
    
    # Database
    DATABASE_URL: Optional[str] = Field(default=None)
    POSTGRES_USER: Optional[str] = Field(default=None)
    POSTGRES_PASSWORD: Optional[str] = Field(default=None)
    POSTGRES_SERVER: Optional[str] = Field(default=None)
    POSTGRES_PORT: str = Field(default="5432")
    POSTGRES_DB: Optional[str] = Field(default=None)
    
    # Redis Cache
    REDIS_URL: Optional[str] = Field(default=None)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    CACHE_TTL: int = Field(default=300)  # 5 minutes
    
    # Cloudinary
    CLOUDINARY_CLOUD_NAME: Optional[str] = Field(default=None)
    CLOUDINARY_API_KEY: Optional[str] = Field(default=None)
    CLOUDINARY_API_SECRET: Optional[str] = Field(default=None)
    
    # CORS
    BACKEND_CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8081"
    )
    
    # Email (for future use)
    SMTP_TLS: bool = Field(default=True)
    SMTP_PORT: Optional[int] = Field(default=587)
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_USER: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    
    # Sentry
    SENTRY_DSN: Optional[str] = Field(default=None)
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_PERIOD: int = Field(default=60)  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def get_database_url(self) -> str:
        """Get database URL with proper formatting"""
        if self.DATABASE_URL:
            # Handle Render's postgres:// URLs
            db_url = self.DATABASE_URL
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            return db_url
        
        # Build URL from components
        if all([self.POSTGRES_USER, self.POSTGRES_PASSWORD, 
                self.POSTGRES_SERVER, self.POSTGRES_DB]):
            return (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        
        # Default for development
        return "sqlite:///./test.db"
    
    def get_redis_url(self) -> Optional[str]:
        """Get Redis URL"""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    def get_cors_origins(self) -> list[str]:
        """Get CORS origins as list"""
        if self.BACKEND_CORS_ORIGINS:
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return ["http://localhost:3000", "http://localhost:8081"]

settings = Settings()
