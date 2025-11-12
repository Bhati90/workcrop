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

# class JobSerializer(serializers.ModelSerializer):
#     farmer = FarmerSerializer(read_only=True)
#     activity = ActivitySerializer(read_only=True)
#     finalized_mukadam = MukadamSerializer(read_only=True)
    
#     class Meta:
#         model = Job
#         fields = '__all__'
# In serializers.py - ADD this
class MukadamInterestSerializer(serializers.ModelSerializer):
    mukadam = MukadamSerializer(read_only=True)
    
    class Meta:
        model = MukadamInterest
        fields = ['id', 'mukadam', 'is_interested','response_status', 'responded_at']

# Update JobSerializer 
class JobSerializer(serializers.ModelSerializer):
    farmer = FarmerSerializer(read_only=True)
    activity = ActivitySerializer(read_only=True)
    interests = MukadamInterestSerializer(many=True, read_only=True)  # ADD this line
    finalized_mukadam = MukadamSerializer(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'finalized_mukadam', 
            'id', 'farmer', 'activity', 'farm_size_acres', 'location', 
            'requested_date', 'requested_time', 'farmer_price_per_acre',
            'your_price_per_acre', 'status', 'interests' ,'workers_needed' # ADD interests here
        ]



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
            'notes','workers_needed'
        ]
    
    def create(self, validated_data):
        # Get or create farmer
        farmer_data = {
            'name': validated_data.pop('farmer_name'),
            'phone': validated_data.pop('farmer_phone'),
            'village': validated_data.pop('farmer_village')
        }
        
        # Get or create farmer
        farmer, created = Farmer.objects.get_or_create(
            phone=farmer_data['phone'],
            defaults=farmer_data
        )
        
        # Get or create activity
        activity_name = validated_data.pop('activity_name')
        activity, created = Activity.objects.get_or_create(
            name=activity_name
        )
        
        # Create job with workers_needed
        job = Job.objects.create(
            farmer=farmer,
            activity=activity,
            **validated_data  # This now includes workers_needed
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
# Update serializers.py
class MukadamBidDetailSerializer(serializers.ModelSerializer):
    mukadam_name = serializers.CharField(source='mukadam.name', read_only=True)
    mukadam_phone = serializers.CharField(source='mukadam.phone', read_only=True)
    mukadam_location = serializers.CharField(source='mukadam.location', read_only=True)
    mukadam_labourers = serializers.IntegerField(source='mukadam.number_of_labourers', read_only=True)
    
    # Add performance data
    mukadam_total_bids = serializers.SerializerMethodField()
    mukadam_won_bids = serializers.SerializerMethodField()
    mukadam_avg_bid_price = serializers.SerializerMethodField()
    mukadam_success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = MukadamBid
        fields = [
            'id', 'status', 'bid_price_per_acre', 'final_price_per_acre',
            'estimated_duration_hours', 'comments', 'created_at', 'responded_at',
            'mukadam_name', 'mukadam_phone', 'mukadam_location', 'mukadam_labourers',
            'mukadam_total_bids', 'mukadam_won_bids', 'mukadam_avg_bid_price', 'mukadam_success_rate'
        ]
    
    def get_mukadam_total_bids(self, obj):
        return MukadamBid.objects.filter(mukadam=obj.mukadam, status__in=['interested', 'selected', 'rejected']).count()
    
    def get_mukadam_won_bids(self, obj):
        return MukadamBid.objects.filter(mukadam=obj.mukadam, status='selected').count()
    
    def get_mukadam_avg_bid_price(self, obj):
        from django.db.models import Avg
        avg = MukadamBid.objects.filter(
            mukadam=obj.mukadam, 
            status__in=['interested', 'selected', 'rejected'],
            bid_price_per_acre__isnull=False
        ).aggregate(avg_price=Avg('bid_price_per_acre'))['avg_price']
        return round(float(avg), 2) if avg else 0
    
    def get_mukadam_success_rate(self, obj):
        total = self.get_mukadam_total_bids(obj)
        won = self.get_mukadam_won_bids(obj)
        return round((won / total * 100), 1) if total > 0 else 0

class JobDetailSerializer(serializers.ModelSerializer):
    farmer = FarmerSerializer(read_only=True)
    activity = ActivitySerializer(read_only=True)
    finalized_mukadam = MukadamSerializer(read_only=True)
    all_bids = MukadamBidDetailSerializer(source='bids', many=True, read_only=True)  # ✅ All bids
    
    class Meta:
        model = Job
        fields = [
            'id', 'farmer', 'activity', 'farm_size_acres', 'location',
            'requested_date', 'requested_time', 'farmer_price_per_acre',
            'status', 'notes', 'finalized_mukadam', 'finalized_price',
            'confirmed_at', 'finalized_at', 'all_bids'  # ✅ Include all bids
        ]
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