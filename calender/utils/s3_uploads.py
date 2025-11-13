
# utils/s3_uploads.py - OPTIMIZED VERSION
import boto3
from django.conf import settings
import uuid
import os
from PIL import Image
import io
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# ============================================
# SOLUTION 14: Cached S3 Client
# ============================================
@lru_cache(maxsize=1)
def get_s3_client():
    """
    Create and cache S3 client to reuse connection
    Performance boost: ~50-100ms saved per upload
    """
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )


# ============================================
# SOLUTION 15: Optimized Image Processing
# ============================================
def optimize_image(file, max_size=(1920, 1920), quality=85):
    """
    Optimized image processing with better error handling
    """
    try:
        image = Image.open(file)
        
        # Convert EXIF orientation
        try:
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        
        # Resize if needed
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Determine format
        file_extension = file.name.split('.')[-1].lower()
        image_format = 'JPEG' if file_extension in ['jpg', 'jpeg'] else 'PNG'
        
        # Convert to RGB for JPEG
        if image_format == 'JPEG':
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if len(image.split()) > 3 else None)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
        
        # Save to bytes
        output = io.BytesIO()
        if image_format == 'JPEG':
            image.save(output, format=image_format, quality=quality, optimize=True)
        else:
            image.save(output, format=image_format, optimize=True)
        
        output.seek(0)
        return output, image_format, file_extension
        
    except Exception as e:
        logger.error(f"Image optimization failed: {e}")
        raise


def upload_image_to_s3(file, folder='media'):
    """
    Upload image to S3 with optimizations:
    - Cached S3 client
    - Better error handling
    - Optimized image processing
    - Returns only S3 key (not full URL)
    """
    try:
        s3_client = get_s3_client()  # Use cached client
        
        # Generate unique filename
        original_filename = os.path.splitext(file.name)[0]
        file_extension = file.name.split('.')[-1].lower()
        safe_name = "".join(c for c in original_filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
        unique_filename = f"{folder}/{uuid.uuid4().hex}_{safe_name}.{file_extension}"

        # Optimize image
        output, image_format, file_ext = optimize_image(file)

        # Upload to S3
        s3_client.upload_fileobj(
            output,
            settings.AWS_STORAGE_BUCKET_NAME,
            unique_filename,
            ExtraArgs={
                "ContentType": f"image/{file_ext}",
                "CacheControl": "max-age=31536000",  # Cache for 1 year
            }
        )
        
        logger.info(f"Successfully uploaded: {unique_filename}")
        
        # Return ONLY the S3 key
        return unique_filename

    except Exception as e:
        logger.error(f"Failed to upload image: {str(e)}")
        raise Exception(f"Failed to upload image: {str(e)}")