import boto3
from django.conf import settings
import uuid
import os
from PIL import Image
import io
# utils/s3_uploads.py
def upload_image_to_s3(file, folder='media'):
    """
    Upload image to S3, return the full S3 URL.
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        original_filename = os.path.splitext(file.name)[0]
        file_extension = file.name.split('.')[-1].lower()
        safe_name = "".join(c for c in original_filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
        unique_filename = f"{folder}/{uuid.uuid4().hex}_{safe_name}.{file_extension}"

        image = Image.open(file)
        max_size = (1920, 1920)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        image_format = 'JPEG' if file_extension in ['jpg', 'jpeg'] else 'PNG'

        if image_format == 'JPEG':
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            image.save(output, format=image_format, quality=85, optimize=True)
        else:
            image.save(output, format=image_format, optimize=True)

        output.seek(0)

        s3_client.upload_fileobj(
            output,
            settings.AWS_STORAGE_BUCKET_NAME,
            unique_filename,
            ExtraArgs={"ContentType": f"image/{file_extension}"}
        )
        
        # Return the full URL instead of just the key
        full_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{unique_filename}"
        return full_url  # <--- Full URL!

    except Exception as e:
        raise Exception(f"Failed to upload image: {str(e)}")