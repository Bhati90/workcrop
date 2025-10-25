# utils/s3_upload.py
import boto3
from django.conf import settings
import uuid
from PIL import Image
import io


def upload_image_to_s3(file, folder='products'):
    """
    Upload image to S3 and return the URL
    """
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        # Generate unique filename
        file_extension = file.name.split('.')[-1]
        unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"
        
        # Compress image if it's too large
        image = Image.open(file)
        
        # Resize if larger than 1920px
        max_size = (1920, 1920)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = io.BytesIO()
        image_format = 'JPEG' if file_extension.lower() in ['jpg', 'jpeg'] else 'PNG'
        image.save(output, format=image_format, quality=85, optimize=True)
        output.seek(0)
        
        # Upload to S3
        s3_client.put_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=unique_filename,
            Body=output,
            ContentType=f'image/{file_extension.lower()}',
            ACL='public-read'  # Make image publicly accessible
        )
        
        # Return the URL
        url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{unique_filename}"
        return url
        
    except Exception as e:
        raise Exception(f"Failed to upload image: {str(e)}")
