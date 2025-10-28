from rest_framework import serializers
from .models import Product, DayRangeProduct, AuditLog, Activity, DayRange, CropVariety, Crop
from django.conf import settings
import boto3
from functools import lru_cache

# ============================================
# SOLUTION 1: Cached S3 Client (Reuse connection)
# ============================================
@lru_cache(maxsize=1)
def get_s3_client():
    """Reuse S3 client instead of creating new one each time"""
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


# ============================================
# SOLUTION 2: Batch Presigned URL Generation
# ============================================
def generate_presigned_urls_bulk(image_keys):
    """
    Generate presigned URLs for multiple images at once
    Returns dict: {image_key: presigned_url}
    """
    if not image_keys:
        return {}
    
    s3_client = get_s3_client()
    urls = {}
    
    for key in image_keys:
        if not key:
            continue
            
        # Extract S3 key from full URL if needed
        if key.startswith('http'):
            if 'amazonaws.com/' in key:
                key = key.split('amazonaws.com/')[-1]
            else:
                continue
        
        try:
            url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
                ExpiresIn=3600
            )
            urls[key] = url
        except Exception as e:
            print(f"Error generating presigned URL for {key}: {e}")
            urls[key] = None
    
    return urls


# ============================================
# SOLUTION 3: Optimized List Serializer
# ============================================
class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view - NO presigned URLs"""
    discount_percentage = serializers.ReadOnlyField()
    display_size = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'name_marathi', 'product_type',
            'mrp', 'price', 'size', 'size_unit', 'display_size',
            'image',  # Just the key, no URL generation
            'discount_percentage', 'created_at', 'updated_at'
        ]
    
    def validate_name(self, value):
        if not self.instance and Product.objects.filter(name=value).exists():
            raise serializers.ValidationError("Product with this name already exists.")
        return value


# ============================================
# SOLUTION 4: Optimized Detail Serializer with Bulk URLs
# ============================================
class ProductDetailSerializer(serializers.ModelSerializer):
    """Full serializer with presigned URL - optimized for bulk operations"""
    discount_percentage = serializers.ReadOnlyField()
    display_size = serializers.ReadOnlyField()
    presigned_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'name_marathi', 'product_type',
            'mrp', 'price', 'size', 'size_unit', 'display_size',
            'image', 'presigned_image_url',
            'discount_percentage', 'created_at', 'updated_at'
        ]
    
    def get_presigned_image_url(self, obj):
        # Check if bulk URLs were pre-generated and stored in context
        presigned_urls = self.context.get('presigned_urls', {})
        
        key = getattr(obj, 'image', None)
        if not key:
            return None
        
        # Extract S3 key if full URL provided
        original_key = key
        if key.startswith('http') and 'amazonaws.com/' in key:
            key = key.split('amazonaws.com/')[-1]
        
        # Return pre-generated URL if available
        if key in presigned_urls:
            return presigned_urls[key]
        
        # Fallback: generate single URL (for detail view of single product)
        return self._generate_single_url(key)
    
    def _generate_single_url(self, key):
        """Fallback for single product detail view"""
        s3_client = get_s3_client()
        try:
            return s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
                ExpiresIn=3600
            )
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None


# ============================================
# SOLUTION 5: Custom List Serializer for Bulk Operations
# ============================================
class ProductDetailListSerializer(serializers.ListSerializer):
    """Custom list serializer that generates presigned URLs in bulk"""
    
    def to_representation(self, data):
        # Extract all image keys
        image_keys = [
            item.image for item in data 
            if hasattr(item, 'image') and item.image
        ]
        
        # Generate all presigned URLs at once
        presigned_urls = generate_presigned_urls_bulk(image_keys)
        
        # Add to context so child serializer can access them
        self.child.context['presigned_urls'] = presigned_urls
        
        # Let parent class handle the rest
        return super().to_representation(data)


# Update ProductDetailSerializer to use the custom list serializer
ProductDetailSerializer.Meta.list_serializer_class = ProductDetailListSerializer


# ============================================
# Other Serializers (unchanged but shown for completeness)
# ============================================
class DayRangeProductSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)  # Use lightweight serializer
    product_id = serializers.IntegerField(write_only=True)
    day_range_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = DayRangeProduct
        fields = ['id', 'day_range', 'day_range_id', 'product', 'product_id', 
                  'dosage', 'dosage_unit', 'created_at', 'updated_at']
        read_only_fields = ['id', 'day_range', 'created_at', 'updated_at']
        extra_kwargs = {'day_range': {'required': False}}
    
    def create(self, validated_data):
        day_range_id = validated_data.pop('day_range_id')
        product_id = validated_data.pop('product_id')
        return DayRangeProduct.objects.create(
            day_range_id=day_range_id,
            product_id=product_id,
            **validated_data
        )
    
    def update(self, instance, validated_data):
        if 'day_range_id' in validated_data:
            instance.day_range_id = validated_data.pop('day_range_id')
        if 'product_id' in validated_data:
            instance.product_id = validated_data.pop('product_id')
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
# from rest_framework import serializers
# from .models import Crop, CropVariety,AuditLog, Activity, Product, DayRange, DayRangeProduct
# from django.conf import settings
# from rest_framework import serializers
# import boto3
# from urllib.parse import urlparse
# from rest_framework import serializers
# from .models import Product
# import boto3
# from django.conf import settings

# class ProductListSerializer(serializers.ModelSerializer):
#     discount_percentage = serializers.ReadOnlyField()
#     display_size = serializers.ReadOnlyField()
    
    
#     class Meta:
#         model = Product
#         fields = [
#             'id', 'name', 'name_marathi', 'product_type',
#             'mrp', 'price', 'size', 'size_unit', 'display_size',
#             'image', 
#             'discount_percentage', 'created_at', 'updated_at'
#         ]
    
#     def validate_name(self, value):
#         # Check for uniqueness during creation
#         if not self.instance and Product.objects.filter(name=value).exists():
#             raise serializers.ValidationError("Product with this name already exists.")
#         return value


# class ProductDetailSerializer(serializers.ModelSerializer):
#     """Full serializer with presigned URL for detail view only"""
#     discount_percentage = serializers.ReadOnlyField()
#     display_size = serializers.ReadOnlyField()
#     presigned_image_url = serializers.SerializerMethodField()
    
#     def get_presigned_image_url(self, obj):
#         key = getattr(obj, 'image', None)
#         if not key:
#             return None
        
#         if key.startswith('http'):
#             if 'amazonaws.com/' in key:
#                 key = key.split('amazonaws.com/')[-1]
#             else:
#                 return None
        
#         s3_client = boto3.client(
#             's3',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_S3_REGION_NAME,
#         )
#         try:
#             url = s3_client.generate_presigned_url(
#                 ClientMethod="get_object",
#                 Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
#                 ExpiresIn=3600
#             )
#             return url
#         except Exception as e:
#             print(f"Error generating presigned URL: {e}")
#             return None

#     # Keep your existing get_presigned_image_url method
    
#     class Meta:
#         model = Product
#         fields = [
#             'id', 'name', 'name_marathi', 'product_type',
#             'mrp', 'price', 'size', 'size_unit', 'display_size',
#             'image', 'presigned_image_url',
#             'discount_percentage', 'created_at', 'updated_at'
#         ]


# class DayRangeProductSerializer(serializers.ModelSerializer):
#     product = ProductListSerializer(read_only=True)
#     product_id = serializers.IntegerField(write_only=True)
#     day_range_id = serializers.IntegerField(write_only=True)  # Remove required=False
    
#     class Meta:
#         model = DayRangeProduct
#         fields = ['id', 'day_range', 'day_range_id', 'product', 'product_id', 'dosage', 'dosage_unit', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'day_range', 'created_at', 'updated_at']  # ← Make day_range read-only
#         extra_kwargs = {
#             'day_range': {'required': False}  # ← Not required for creation
#         }
    
#     def create(self, validated_data):
#         # Get day_range_id and set it directly
#         day_range_id = validated_data.pop('day_range_id')
#         product_id = validated_data.pop('product_id')
        
#         # Create with the IDs directly
#         return DayRangeProduct.objects.create(
#             day_range_id=day_range_id,
#             product_id=product_id,
#             **validated_data
#         )
    
#     def update(self, instance, validated_data):
#         # Handle day_range_id if provided
#         if 'day_range_id' in validated_data:
#             instance.day_range_id = validated_data.pop('day_range_id')
        
#         # Handle product_id if provided
#         if 'product_id' in validated_data:
#             instance.product_id = validated_data.pop('product_id')
        
#         # Update other fields
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
        
#         instance.save()
#         return instance
    
# class AuditLogSerializer(serializers.ModelSerializer):
#     model_display = serializers.CharField(source='get_model_name_display', read_only=True)
#     action_display = serializers.CharField(source='get_action_display', read_only=True)
    
#     class Meta:
#         model = AuditLog
#         fields = '__all__'



# class ActivitySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Activity
#         fields = ['id', 'name', 'name_marathi', 'created_at', 'updated_at']


# class DayRangeSerializer(serializers.ModelSerializer):
#     activity = ActivitySerializer(read_only=True)
#     activity_id = serializers.IntegerField(write_only=True)
#     crop_variety_id = serializers.IntegerField(write_only=True)
#     products = DayRangeProductSerializer(many=True, read_only=True)
    
#     class Meta:
#         model = DayRange
#         fields = ['id', 'crop_variety_id', 'activity', 'activity_id', 
#                   'start_day', 'end_day', 'info', 'info_marathi', 
#                   'products', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'activity', 'created_at', 'updated_at']
    
#     def create(self, validated_data):
#         return DayRange.objects.create(**validated_data)

# class CropVarietyDetailSerializer(serializers.ModelSerializer):
#     day_ranges = DayRangeSerializer(many=True, read_only=True)
#     crop_name = serializers.CharField(source='crop.name', read_only=True)
#     crop_name_marathi = serializers.CharField(source='crop.name_marathi', read_only=True)
    
#     class Meta:
#         model = CropVariety
#         fields = ['id', 'name', 'name_marathi', 'crop_name', 'crop_name_marathi', 
#                   'day_ranges', 'created_at', 'updated_at']


# class CropVarietySerializer(serializers.ModelSerializer):
#     crop_name = serializers.CharField(source='crop.name', read_only=True)
#     crop = serializers.PrimaryKeyRelatedField(
#         queryset=Crop.objects.all(), 
#         write_only=True,
#         required=True
#     )
    
#     class Meta:
#         model = CropVariety
#         fields = ['id', 'crop', 'name', 'name_marathi', 'crop_name', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'crop_name', 'created_at', 'updated_at']


# class CropSerializer(serializers.ModelSerializer):
#     varieties = CropVarietySerializer(many=True, read_only=True)
    
#     class Meta:
#         model = Crop
#         fields = ['id', 'name', 'name_marathi', 'varieties', 'created_at', 'updated_at']


# class CropScheduleSerializer(serializers.ModelSerializer):
#     """Complete crop schedule with all activities and products"""
#     varieties = CropVarietyDetailSerializer(many=True, read_only=True)
    
#     class Meta:
#         model = Crop
#         fields = ['id', 'name', 'name_marathi', 'varieties', 'created_at', 'updated_at']
