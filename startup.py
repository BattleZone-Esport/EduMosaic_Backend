#!/usr/bin/env python3
"""
Startup script that detects which version of the app to run
This provides backward compatibility during migration
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_application():
    """Get the appropriate application object"""
    
    # Try to import the new modular app first
    try:
        from app.main import app
        logger.info("✅ Loading new modular application structure")
        return app
    except ImportError as e:
        logger.warning(f"Could not load new app structure: {e}")
        
    # Fall back to the original main.py
    try:
        # Add missing Language enum to fix the original code
        import enum
        import models
        
        # Patch the missing Language enum if it doesn't exist
        if not hasattr(models, 'Language'):
            class Language(enum.Enum):
                ENGLISH = "english"
                HINDI = "hindi"
                SPANISH = "spanish"
                FRENCH = "french"
                GERMAN = "german"
                CHINESE = "chinese"
                JAPANESE = "japanese"
                KOREAN = "korean"
                ARABIC = "arabic"
                RUSSIAN = "russian"
            
            models.Language = Language
            logger.info("✅ Patched missing Language enum")
        
        from main import app
        logger.info("⚠️ Loading legacy application structure")
        return app
    except ImportError as e:
        logger.error(f"Failed to load application: {e}")
        raise

# Export the app for Gunicorn
app = get_application()

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)