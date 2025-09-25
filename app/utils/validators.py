"""Validation utilities"""

import re
from typing import Optional


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> bool:
    """Basic password validation"""
    return len(password) >= 8


def validate_username(username: str) -> bool:
    """Validate username"""
    pattern = r"^[a-zA-Z0-9_-]{3,50}$"
    return bool(re.match(pattern, username))
