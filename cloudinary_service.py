import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List, Tuple
import uuid
from datetime import datetime
import mimetypes
from PIL import Image
import io

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CloudinaryService")

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (increased from 5MB)
MAX_IMAGE_DIMENSION = 4096  # Max width/height for images
ALLOWED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "webp", "gif"]
ALLOWED_DOCUMENT_FORMATS = ["pdf", "doc", "docx", "txt"]
ALLOWED_VIDEO_FORMATS = ["mp4", "webm", "mov"]
COMPRESSION_QUALITY = 80  # Default compression quality

class CloudinaryService:
    """Enhanced Cloudinary service for EduMosaic media management"""
    
    @staticmethod
    def validate_file_size(file_content: bytes, max_size: int = MAX_FILE_SIZE) -> bool:
        """Validate file size"""
        return len(file_content) <= max_size
    
    @staticmethod
    def validate_image_dimensions(image_content: bytes) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """Validate image dimensions"""
        try:
            image = Image.open(io.BytesIO(image_content))
            width, height = image.size
            return (width <= MAX_IMAGE_DIMENSION and height <= MAX_IMAGE_DIMENSION), (width, height)
        except Exception as e:
            logger.error(f"Error validating image dimensions: {str(e)}")
            return False, None
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """Get file type from filename"""
        if not filename:
            return "unknown"
        
        ext = filename.split('.')[-1].lower() if '.' in filename else ""
        
        if ext in ALLOWED_IMAGE_FORMATS:
            return "image"
        elif ext in ALLOWED_VIDEO_FORMATS:
            return "video"
        elif ext in ALLOWED_DOCUMENT_FORMATS:
            return "document"
        else:
            return "raw"
    
    @staticmethod
    def optimize_image(image_content: bytes, quality: int = COMPRESSION_QUALITY) -> bytes:
        """Optimize image by compressing and resizing if needed"""
        try:
            image = Image.open(io.BytesIO(image_content))
            
            # Convert to RGB if necessary (for JPEG)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            # Resize if too large
            width, height = image.size
            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                ratio = min(MAX_IMAGE_DIMENSION / width, MAX_IMAGE_DIMENSION / height)
                new_size = (int(width * ratio), int(height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            output = io.BytesIO()
            image.save(output, format='JPEG' if image.format != 'PNG' else 'PNG', 
                      quality=quality, optimize=True)
            
            return output.getvalue()
        except Exception as e:
            logger.error(f"Error optimizing image: {str(e)}")
            return image_content  # Return original if optimization fails
    
    @staticmethod
    def upload_file(
        file_content: bytes, 
        folder: str, 
        resource_type: str = "auto",
        public_id: Optional[str] = None,
        overwrite: bool = True,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generic file upload to Cloudinary with enhanced options
        
        Args:
            file_content: File content as bytes
            folder: Cloudinary folder path
            resource_type: Type of resource (auto, image, video, raw)
            public_id: Custom public ID for the resource
            overwrite: Whether to overwrite existing file with same public_id
            tags: List of tags for the resource
            context: Key-value pairs for context metadata
            
        Returns:
            Upload result dictionary or None if failed
        """
        try:
            # Generate public ID if not provided
            if not public_id:
                public_id = f"{folder}_{uuid.uuid4().hex}"
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                file_content,
                folder=folder,
                public_id=public_id,
                overwrite=overwrite,
                resource_type=resource_type,
                tags=tags,
                context=context,
                # Additional optimization options
                quality=COMPRESSION_QUALITY,
                format="auto"  # Auto-format for best delivery
            )
            
            logger.info(f"File uploaded successfully to {folder}/{public_id}")
            return result
            
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            return None
    
    @staticmethod
    def upload_avatar(image_file, user_id: str, optimize: bool = True) -> Optional[Dict[str, Any]]:
        """
        Upload a user profile avatar to Cloudinary with enhanced features
        
        Args:
            image_file: File content or file-like object
            user_id: User ID for folder organization
            optimize: Whether to optimize the image before upload
            
        Returns:
            Upload result dictionary or None if failed
        """
        try:
            # Read file content
            if hasattr(image_file, 'read'):
                content = image_file.read()
            else:
                content = image_file
            
            # Size validation
            if not CloudinaryService.validate_file_size(content):
                raise ValueError(f"File size must be less than {MAX_FILE_SIZE/1024/1024}MB")
            
            # Validate image dimensions
            valid, dimensions = CloudinaryService.validate_image_dimensions(content)
            if not valid:
                logger.warning(f"Image dimensions {dimensions} exceed maximum allowed {MAX_IMAGE_DIMENSION}")
            
            # Optimize image if requested
            if optimize:
                content = CloudinaryService.optimize_image(content)
            
            # Upload to Cloudinary with user context
            result = CloudinaryService.upload_file(
                content,
                folder=f"quiz_app/avatars/{user_id}",
                resource_type="image",
                tags=["avatar", f"user:{user_id}"],
                context={"user_id": user_id, "upload_type": "avatar"}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Avatar upload error for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def upload_quiz_image(
        image_file, 
        category: str, 
        quiz_id: Optional[str] = None,
        question_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Upload quiz-related image to Cloudinary
        
        Args:
            image_file: File content or file-like object
            category: Quiz category for organization
            quiz_id: Optional quiz ID for specific organization
            question_id: Optional question ID for specific organization
            
        Returns:
            Upload result dictionary or None if failed
        """
        try:
            # Read file content
            if hasattr(image_file, 'read'):
                content = image_file.read()
            else:
                content = image_file
            
            # Size validation
            if not CloudinaryService.validate_file_size(content):
                raise ValueError(f"File size must be less than {MAX_FILE_SIZE/1024/1024}MB")
            
            # Validate image dimensions
            valid, dimensions = CloudinaryService.validate_image_dimensions(content)
            if not valid:
                logger.warning(f"Image dimensions {dimensions} exceed maximum allowed {MAX_IMAGE_DIMENSION}")
            
            # Optimize image
            content = CloudinaryService.optimize_image(content)
            
            # Build folder path
            folder_parts = ["quiz_app", "quizzes", category]
            if quiz_id:
                folder_parts.append(quiz_id)
            if question_id:
                folder_parts.append(question_id)
            
            folder = "/".join(folder_parts)
            
            # Upload to Cloudinary
            result = CloudinaryService.upload_file(
                content,
                folder=folder,
                resource_type="image",
                tags=["quiz", f"category:{category}", f"quiz:{quiz_id}" if quiz_id else "general"],
                context={"category": category, "quiz_id": quiz_id, "question_id": question_id}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Quiz image upload error: {str(e)}")
            return None
    
    @staticmethod
    def upload_document(
        file_content: bytes, 
        filename: str, 
        folder: str = "quiz_app/documents"
    ) -> Optional[Dict[str, Any]]:
        """
        Upload document to Cloudinary
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            folder: Cloudinary folder path
            
        Returns:
            Upload result dictionary or None if failed
        """
        try:
            # Size validation
            if not CloudinaryService.validate_file_size(file_content):
                raise ValueError(f"File size must be less than {MAX_FILE_SIZE/1024/1024}MB")
            
            # Get file extension for public ID
            ext = filename.split('.')[-1] if '.' in filename else ""
            public_id = f"{uuid.uuid4().hex}{f'.{ext}' if ext else ''}"
            
            # Upload to Cloudinary
            result = CloudinaryService.upload_file(
                file_content,
                folder=folder,
                resource_type="raw",
                public_id=public_id,
                tags=["document", f"ext:{ext}"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Document upload error: {str(e)}")
            return None
    
    @staticmethod
    def delete_resource(public_id: str, resource_type: str = "image") -> bool:
        """
        Delete a resource from Cloudinary
        
        Args:
            public_id: Public ID of the resource to delete
            resource_type: Type of resource (image, video, raw)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result.get("result") == "ok"
        except Exception as e:
            logger.error(f"Error deleting resource {public_id}: {str(e)}")
            return False
    
    @staticmethod
    def delete_folder(folder_path: str) -> bool:
        """
        Delete entire folder from Cloudinary (use with caution!)
        
        Args:
            folder_path: Path to the folder to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First delete all resources in the folder
            resources = cloudinary.api.resources(
                type="upload", 
                prefix=folder_path, 
                max_results=100
            )
            
            for resource in resources.get("resources", []):
                CloudinaryService.delete_resource(resource["public_id"], resource["resource_type"])
            
            # Then delete the folder itself
            result = cloudinary.api.delete_folder(folder_path)
            return True
        except Exception as e:
            logger.error(f"Error deleting folder {folder_path}: {str(e)}")
            return False
    
    @staticmethod
    def generate_url(
        public_id: str, 
        transformations: Optional[List[Dict]] = None,
        resource_type: str = "image",
        format: str = None
    ) -> Optional[str]:
        """
        Generate Cloudinary URL with transformations
        
        Args:
            public_id: Public ID of the resource
            transformations: List of transformation dictionaries
            resource_type: Type of resource (image, video, raw)
            format: Force specific format
            
        Returns:
            URL string or None if failed
        """
        try:
            # Default transformations for images
            if resource_type == "image" and not transformations:
                transformations = [
                    {"quality": "auto", "fetch_format": "auto"}
                ]
            
            url, options = cloudinary_url(
                public_id,
                transformation=transformations,
                resource_type=resource_type,
                format=format
            )
            
            return url
        except Exception as e:
            logger.error(f"Error generating URL for {public_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_avatar_url(public_id: str, size: int = 200, crop: str = "fill") -> Optional[str]:
        """
        Generate a Cloudinary URL for a user avatar with transformations
        
        Args:
            public_id: Public ID of the avatar
            size: Width and height of the avatar
            crop: Crop mode (fill, fit, limit, etc.)
            
        Returns:
            URL string or None if failed
        """
        transformations = [
            {"width": size, "height": size, "crop": crop, "gravity": "face"},
            {"quality": "auto", "fetch_format": "auto"}
        ]
        
        return CloudinaryService.generate_url(public_id, transformations)
    
    @staticmethod
    def get_resource_info(public_id: str, resource_type: str = "image") -> Optional[Dict[str, Any]]:
        """
        Get information about a Cloudinary resource
        
        Args:
            public_id: Public ID of the resource
            resource_type: Type of resource (image, video, raw)
            
        Returns:
            Resource information dictionary or None if failed
        """
        try:
            result = cloudinary.api.resource(public_id, resource_type=resource_type)
            return result
        except Exception as e:
            logger.error(f"Error getting resource info for {public_id}: {str(e)}")
            return None
    
    @staticmethod
    def list_resources(
        folder: str, 
        resource_type: str = "image", 
        max_results: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        List resources in a Cloudinary folder
        
        Args:
            folder: Folder path to list
            resource_type: Type of resources to list
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with list of resources or None if failed
        """
        try:
            result = cloudinary.api.resources(
                type=resource_type,
                prefix=folder,
                max_results=max_results
            )
            return result
        except Exception as e:
            logger.error(f"Error listing resources in {folder}: {str(e)}")
            return None
    
    @staticmethod
    def get_usage_stats() -> Optional[Dict[str, Any]]:
        """
        Get Cloudinary usage statistics
        
        Returns:
            Usage statistics dictionary or None if failed
        """
        try:
            result = cloudinary.api.usage()
            return result
        except Exception as e:
            logger.error(f"Error getting usage stats: {str(e)}")
            return None

# Backward compatibility functions
def upload_avatar(image_file, user_id: str) -> Optional[Dict[str, Any]]:
    """Backward compatible avatar upload function"""
    return CloudinaryService.upload_avatar(image_file, user_id)

def get_avatar_url(public_id: str, size: int = 200) -> Optional[str]:
    """Backward compatible avatar URL generation function"""
    return CloudinaryService.get_avatar_url(public_id, size)

# Initialize and test connection
try:
    # Test Cloudinary connection
    test_result = cloudinary.api.ping()
    if test_result.get("status") == "ok":
        logger.info("Cloudinary connection established successfully")
        
        # Log usage stats
        usage = CloudinaryService.get_usage_stats()
        if usage:
            logger.info(f"Cloudinary usage: {usage.get('plan')} plan, "
                       f"{usage.get('usage', {}).get('bandwidth', 0) / 1024 / 1024:.2f} MB bandwidth used")
    else:
        logger.warning("Cloudinary connection test failed")
except Exception as e:
    logger.error(f"Cloudinary connection error: {str(e)}")