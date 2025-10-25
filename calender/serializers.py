from rest_framework import serializers
from .models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'name_marathi', 'product_type', 'created_at', 'updated_at']


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
