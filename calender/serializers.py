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
        key = getattr(obj, 'image', None)
        if not key:
            return None
        
        if key.startswith('http'):
            if 'amazonaws.com/' in key:
                key = key.split('amazonaws.com/')[-1]
            else:
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
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'name_marathi', 'product_type',
            'mrp', 'price', 'size', 'size_unit', 'display_size',
            'image', 'presigned_image_url',
            'discount_percentage', 'created_at', 'updated_at'
        ]
    
    def validate_name(self, value):
        # Check for uniqueness during creation
        if not self.instance and Product.objects.filter(name=value).exists():
            raise serializers.ValidationError("Product with this name already exists.")
        return value

class DayRangeProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    day_range_id = serializers.IntegerField(write_only=True)  # Remove required=False
    
    class Meta:
        model = DayRangeProduct
        fields = ['id', 'day_range', 'day_range_id', 'product', 'product_id', 'dosage', 'dosage_unit', 'created_at', 'updated_at']
        read_only_fields = ['id', 'day_range', 'created_at', 'updated_at']  # ← Make day_range read-only
        extra_kwargs = {
            'day_range': {'required': False}  # ← Not required for creation
        }
    
    def create(self, validated_data):
        # Get day_range_id and set it directly
        day_range_id = validated_data.pop('day_range_id')
        product_id = validated_data.pop('product_id')
        
        # Create with the IDs directly
        return DayRangeProduct.objects.create(
            day_range_id=day_range_id,
            product_id=product_id,
            **validated_data
        )
    
    def update(self, instance, validated_data):
        # Handle day_range_id if provided
        if 'day_range_id' in validated_data:
            instance.day_range_id = validated_data.pop('day_range_id')
        
        # Handle product_id if provided
        if 'product_id' in validated_data:
            instance.product_id = validated_data.pop('product_id')
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance
class AuditLogSerializer(serializers.ModelSerializer):
    model_display = serializers.CharField(source='get_model_name_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'



class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id', 'name', 'name_marathi', 'created_at', 'updated_at']


class DayRangeSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    activity_id = serializers.IntegerField(write_only=True)
    crop_variety_id = serializers.IntegerField(write_only=True)
    products = DayRangeProductSerializer(many=True, read_only=True)
    
    class Meta:
        model = DayRange
        fields = ['id', 'crop_variety_id', 'activity', 'activity_id', 
                  'start_day', 'end_day', 'info', 'info_marathi', 
                  'products', 'created_at', 'updated_at']
        read_only_fields = ['id', 'activity', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        return DayRange.objects.create(**validated_data)

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
    crop = serializers.PrimaryKeyRelatedField(
        queryset=Crop.objects.all(), 
        write_only=True,
        required=True
    )
    
    class Meta:
        model = CropVariety
        fields = ['id', 'crop', 'name', 'name_marathi', 'crop_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'crop_name', 'created_at', 'updated_at']


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
