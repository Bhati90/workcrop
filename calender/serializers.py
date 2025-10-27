from rest_framework import serializers
from .models import Crop, CropVariety,AuditLog, Activity, Product, DayRange, DayRangeProduct
from django.conf import settings
from rest_framework import serializers
import boto3
from urllib.parse import urlparse
from rest_framework import serializers
from .models import Product
import boto3
from django.conf import settings

class ProductSerializer(serializers.ModelSerializer):
    discount_percentage = serializers.ReadOnlyField()
    display_size = serializers.ReadOnlyField()
    presigned_image_url = serializers.SerializerMethodField()

    def get_presigned_image_url(self, obj):
        key = getattr(obj, 'image_s3_key', None)
        if not key:
            return None
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        try:
            url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
                ExpiresIn=3600
            )
            return url
        except Exception:
            return None

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'name_marathi', 'product_type',
            'mrp', 'price', 'size', 'size_unit', 'display_size',
            'image_s3_key', 'presigned_image_url',
            'discount_percentage', 'created_at', 'updated_at'
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    model_display = serializers.CharField(source='get_model_name_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'

class DayRangeProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = DayRangeProduct
        fields = ['id', 'product', 'product_id', 'dosage', 'dosage_unit', 'created_at', 'updated_at']


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id', 'name', 'name_marathi', 'created_at', 'updated_at']


class DayRangeSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    products = DayRangeProductSerializer(many=True, read_only=True)
    
    class Meta:
        model = DayRange
        fields = ['id', 'activity', 'start_day', 'end_day', 'info', 'info_marathi', 
                  'products', 'created_at', 'updated_at']


class CropVarietyDetailSerializer(serializers.ModelSerializer):
    day_ranges = DayRangeSerializer(many=True, read_only=True)
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    crop_name_marathi = serializers.CharField(source='crop.name_marathi', read_only=True)
    
    class Meta:
        model = CropVariety
        fields = ['id', 'name', 'name_marathi', 'crop_name', 'crop_name_marathi', 
                  'day_ranges', 'created_at', 'updated_at']


class CropVarietySerializer(serializers.ModelSerializer):
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    
    class Meta:
        model = CropVariety
        fields = ['id', 'name', 'name_marathi', 'crop_name', 'created_at', 'updated_at']


class CropSerializer(serializers.ModelSerializer):
    varieties = CropVarietySerializer(many=True, read_only=True)
    
    class Meta:
        model = Crop
        fields = ['id', 'name', 'name_marathi', 'varieties', 'created_at', 'updated_at']


class CropScheduleSerializer(serializers.ModelSerializer):
    """Complete crop schedule with all activities and products"""
    varieties = CropVarietyDetailSerializer(many=True, read_only=True)
    
    class Meta:
        model = Crop
        fields = ['id', 'name', 'name_marathi', 'varieties', 'created_at', 'updated_at']
