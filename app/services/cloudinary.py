"""
Cloudinary service for EduMosaic
Handles image uploads for quizzes and user avatars
"""

import cloudinary
import cloudinary.uploader
from typing import Optional, Dict, Any
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class CloudinaryService:
    """Cloudinary service for media uploads"""
    
    def __init__(self):
        """Initialize Cloudinary configuration"""
        if all([
            settings.CLOUDINARY_CLOUD_NAME,
            settings.CLOUDINARY_API_KEY,
            settings.CLOUDINARY_API_SECRET
        ]):
            cloudinary.config(
                cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                api_key=settings.CLOUDINARY_API_KEY,
                api_secret=settings.CLOUDINARY_API_SECRET
            )
            self.is_configured = True
            logger.info("Cloudinary configured successfully")
        else:
            self.is_configured = False
            logger.warning("Cloudinary not configured - missing credentials")
    
    def upload_image(
        self,
        file_path: str,
        folder: str = "edumosaic",
        public_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Upload image to Cloudinary
        
        Args:
            file_path: Path to the image file
            folder: Cloudinary folder name
            public_id: Optional custom public ID
            
        Returns:
            Upload result dict or None if failed
        """
        if not self.is_configured:
            logger.warning("Cloudinary not configured, skipping upload")
            return None
        
        try:
            result = cloudinary.uploader.upload(
                file_path,
                folder=folder,
                public_id=public_id,
                overwrite=True,
                resource_type="image",
                transformation=[
                    {"quality": "auto:good"},
                    {"fetch_format": "auto"}
                ]
            )
            logger.info(f"Image uploaded successfully: {result.get('public_id')}")
            return result
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return None
    
    def upload_quiz_image(self, file_path: str, quiz_id: int) -> Optional[str]:
        """
        Upload quiz thumbnail image
        
        Args:
            file_path: Path to the image file
            quiz_id: Quiz ID for naming
            
        Returns:
            Cloudinary URL or None
        """
        result = self.upload_image(
            file_path=file_path,
            folder="edumosaic/quizzes",
            public_id=f"quiz_{quiz_id}"
        )
        return result.get("secure_url") if result else None
    
    def upload_user_avatar(self, file_path: str, user_id: int) -> Optional[str]:
        """
        Upload user avatar image
        
        Args:
            file_path: Path to the image file
            user_id: User ID for naming
            
        Returns:
            Cloudinary URL or None
        """
        result = self.upload_image(
            file_path=file_path,
            folder="edumosaic/avatars",
            public_id=f"user_{user_id}"
        )
        return result.get("secure_url") if result else None
    
    def upload_question_image(
        self,
        file_path: str,
        quiz_id: int,
        question_id: int
    ) -> Optional[str]:
        """
        Upload question image
        
        Args:
            file_path: Path to the image file
            quiz_id: Quiz ID
            question_id: Question ID
            
        Returns:
            Cloudinary URL or None
        """
        result = self.upload_image(
            file_path=file_path,
            folder="edumosaic/questions",
            public_id=f"quiz_{quiz_id}_question_{question_id}"
        )
        return result.get("secure_url") if result else None
    
    def delete_image(self, public_id: str) -> bool:
        """
        Delete image from Cloudinary
        
        Args:
            public_id: Cloudinary public ID
            
        Returns:
            True if deleted successfully
        """
        if not self.is_configured:
            return False
        
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get("result") == "ok"
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return False

# Global service instance
cloudinary_service = CloudinaryService()