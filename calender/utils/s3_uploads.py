# utils/s3_upload.py
import boto3
from django.conf import settings
import uuid
from PIL import Image
import io

def upload_image_to_s3(file, folder='media'):
    """
    Upload image to S3 and return the URL
    Uses upload_fileobj for compatibility with InMemoryUploadedFile
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
        file_extension = file.name.split('.')[-1].lower()
        unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"

        # Compress and/or resize image (optional)
        image = Image.open(file)
        max_size = (1920, 1920)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        image_format = 'JPEG' if file_extension in ['jpg', 'jpeg'] else 'PNG'
        image.save(output, format=image_format, quality=85, optimize=True)
        output.seek(0)

        # Use upload_fileobj (recommended for file-like objects)
        s3_client.upload_fileobj(
            output,
            settings.AWS_STORAGE_BUCKET_NAME,
            unique_filename,
            ExtraArgs={
                "ContentType": f"image/{file_extension}",
                "ACL": "public-read"
            }
        )

        url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{unique_filename}"
        return url

    except Exception as e:
        raise Exception(f"Failed to upload image: {str(e)}")
