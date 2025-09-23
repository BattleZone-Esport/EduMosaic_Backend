"""Email service"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def is_configured() -> bool:
        """Check if email service is configured"""
        return settings.EMAILS_ENABLED and settings.SMTP_HOST is not None

    @staticmethod
    async def send_verification_email(email: str, name: str, token: str):
        """Send email verification"""
        if not EmailService.is_configured():
            logger.warning("Email service not configured")
            return

        # Placeholder implementation
        logger.info(f"Would send verification email to {email}")

    @staticmethod
    async def send_password_reset_email(email: str, name: str, token: str):
        """Send password reset email"""
        if not EmailService.is_configured():
            logger.warning("Email service not configured")
            return

        # Placeholder implementation
        logger.info(f"Would send password reset email to {email}")
