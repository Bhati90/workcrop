from rest_framework import serializers
from django.utils import timezone
from .models import *

class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = '__all__'

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id', 'name', 'description']
# Update serializers.py
class MukadamActivityRateSerializer(serializers.ModelSerializer):
    activity_name = serializers.CharField(source='activity.name', read_only=True)
    
    class Meta:
        model = MukadamActivityRate
        fields = ['id', 'activity', 'activity_name', 'rate_per_acre', 'is_available', 'created_at']

class MukadamDetailSerializer(serializers.ModelSerializer):
    activity_rates = MukadamActivityRateSerializer(many=True, read_only=True)
    total_jobs = serializers.SerializerMethodField()
    completed_jobs = serializers.SerializerMethodField()
    won_bids = serializers.SerializerMethodField()
    avg_bid_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Mukadam
        fields = [
            'id', 'name', 'phone', 'location', 'number_of_labourers', 
            'is_active', 'created_at', 'activity_rates',
            'total_jobs', 'completed_jobs', 'won_bids', 'avg_bid_price'
        ]
    
    def get_total_jobs(self, obj):
        return Job.objects.filter(finalized_mukadam=obj).count()
    
    def get_completed_jobs(self, obj):
        return Job.objects.filter(finalized_mukadam=obj, status='completed').count()
    
    def get_won_bids(self, obj):
        return MukadamBid.objects.filter(mukadam=obj, status='selected').count()
    
    def get_avg_bid_price(self, obj):
        from django.db.models import Avg
        avg = MukadamBid.objects.filter(mukadam=obj, status='selected').aggregate(
            avg_price=Avg('bid_price_per_acre')
        )['avg_price']
        return round(float(avg), 2) if avg else 0

class MukadamSerializer(serializers.ModelSerializer):
    activity_rates = MukadamActivityRateSerializer(many=True, read_only=True)
    
    class Meta:
        model = Mukadam
        fields = [
            'id', 'name', 'phone', 'location', 'number_of_labourers', 
            'is_active', 'created_at', 'activity_rates'
        ]

class JobSerializer(serializers.ModelSerializer):
    farmer = FarmerSerializer(read_only=True)
    activity = ActivitySerializer(read_only=True)
    finalized_mukadam = MukadamSerializer(read_only=True)
    
    class Meta:
        model = Job
        fields = '__all__'




class JobCreateSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(write_only=True)
    farmer_phone = serializers.CharField(write_only=True)
    farmer_village = serializers.CharField(write_only=True)
    activity_name = serializers.CharField(write_only=True)
    
    class Meta:
        model = Job
        fields = [
            'farmer_name', 'farmer_phone', 'farmer_village',
            'activity_name', 'farm_size_acres', 'location',
            'requested_date', 'requested_time', 'farmer_price_per_acre',
            'notes'
        ]
    
    def create(self, validated_data):
        # Get or create farmer
        farmer, _ = Farmer.objects.get_or_create(
            phone=validated_data.pop('farmer_phone'),
            defaults={
                'name': validated_data.pop('farmer_name'),
                'village': validated_data.pop('farmer_village')
            }
        )
        
        # Get or create activity
        activity, _ = Activity.objects.get_or_create(
            name=validated_data.pop('activity_name'),
            defaults={'description': ''}
        )
        
        # Create job
        job = Job.objects.create(
            farmer=farmer,
            activity=activity,
            **validated_data
        )
        
        return job

class MukadamBidSerializer(serializers.ModelSerializer):
    mukadam = MukadamSerializer(read_only=True)
    
    class Meta:
        model = MukadamBid
        fields = '__all__'

class MukadamBidCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MukadamBid
        fields = [
            'job', 'mukadam', 'bid_price_per_acre', 
            'estimated_duration_hours', 'comments'
        ]
    
    def create(self, validated_data):
        # Update existing bid or create new one
        job = validated_data['job']
        mukadam = validated_data['mukadam']
        
        bid, created = MukadamBid.objects.update_or_create(
            job=job,
            mukadam=mukadam,
            defaults={
                'status': 'interested',
                'bid_price_per_acre': validated_data['bid_price_per_acre'],
                'estimated_duration_hours': validated_data.get('estimated_duration_hours'),
                'comments': validated_data.get('comments', ''),
                'responded_at': timezone.now()
            }
        )
        
        return bid

class WhatsAppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppNotification
        fields = '__all__'

class JobStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobStatusHistory
        fields = '__all__'

# Add this to your serializers.py

class MukadamSerializer(serializers.ModelSerializer):
    # Add calculated fields
    total_jobs = serializers.SerializerMethodField()
    completed_jobs = serializers.SerializerMethodField()
    current_jobs = serializers.SerializerMethodField()
    
    class Meta:
        model = Mukadam
        fields = [
            'id', 'name', 'phone', 'location', 'number_of_labourers', 
            'is_active', 'created_at', 'total_jobs', 'completed_jobs', 'current_jobs'
        ]
    
    def get_total_jobs(self, obj):
        """Get total number of jobs assigned to this mukadam"""
        return Job.objects.filter(finalized_mukadam=obj).count()
    
    def get_completed_jobs(self, obj):
        """Get number of completed jobs"""
        return Job.objects.filter(finalized_mukadam=obj, status='completed').count()
    
    def get_current_jobs(self, obj):
        """Get number of current active jobs"""
        return Job.objects.filter(
            finalized_mukadam=obj,
            status__in=['finalized', 'in_progress']
        ).count()

class MukadamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new mukadams"""
    class Meta:
        model = Mukadam
        fields = [
            'name', 'phone', 'location', 'number_of_labourers', 'is_active'
        ]
    
    def validate_phone(self, value):
        """Validate phone number format"""
        import re
        if not re.match(r'^\+91-?\d{10}$', value):
            raise serializers.ValidationError(
                "Phone number must be in format: +91-XXXXXXXXXX"
            )
        return value
    
    def validate_number_of_labourers(self, value):
        """Validate number of labourers"""
        if value < 1:
            raise serializers.ValidationError(
                "Number of labourers must be at least 1"
            )
        if value > 100:
            raise serializers.ValidationError(
                "Number of labourers cannot exceed 100"
            )
        return value