# from rest_framework import serializers
# from django.utils import timezone
# from .models import *

# class FarmerSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Farmer
#         fields = '__all__'

# class ActivitySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Activity
#         fields = ['id', 'name', 'description']
# # Update serializers.py
# class MukadamActivityRateSerializer(serializers.ModelSerializer):
#     activity_name = serializers.CharField(source='activity.name', read_only=True)
    
#     class Meta:
#         model = MukadamActivityRate
#         fields = ['id', 'activity', 'activity_name', 'rate_per_acre', 'is_available', 'created_at']

# class MukadamDetailSerializer(serializers.ModelSerializer):
#     activity_rates = MukadamActivityRateSerializer(many=True, read_only=True)
#     total_jobs = serializers.SerializerMethodField()
#     completed_jobs = serializers.SerializerMethodField()
#     won_bids = serializers.SerializerMethodField()
#     avg_bid_price = serializers.SerializerMethodField()
#     interested_jobs = serializers.SerializerMethodField()  # ✅ NEW
#     pending_responses = serializers.SerializerMethodField()  # ✅ NEW
    
#     class Meta:
#         model = Mukadam
#         fields = [
#             'id', 'name', 'phone', 'location', 'number_of_labourers',
#             'is_active', 'created_at', 'activity_rates', 
#             'total_jobs', 'completed_jobs', 'won_bids', 'avg_bid_price',
#             'interested_jobs', 'pending_responses'  # ✅ ADD these
#         ]
    
#     def get_total_jobs(self, obj):
#         """Count ALL jobs this mukadam was notified about (has interest record for)"""
#         return MukadamInterest.objects.filter(mukadam=obj).count()
    
#     def get_completed_jobs(self, obj):
#         """Count jobs actually completed by this mukadam"""
#         return Job.objects.filter(
#             finalized_mukadam=obj,
#             status='completed'
#         ).count()
    
#     def get_won_bids(self, obj):
#         """Count jobs where this mukadam was actually assigned/finalized"""
#         return Job.objects.filter(
#             finalized_mukadam=obj,
#             status__in=['finalized', 'assigned', 'in_progress', 'completed']
#         ).count()
    
#     def get_avg_bid_price(self, obj):
#         """Average bid price from completed jobs"""
#         completed = Job.objects.filter(
#             finalized_mukadam=obj,
#             status='completed'
#         ).aggregate(avg=models.Avg('finalized_price'))
#         return float(completed['avg'] or 0)
    
#     def get_interested_jobs(self, obj):
#         """Count jobs where mukadam showed interest"""
#         return MukadamInterest.objects.filter(
#             mukadam=obj,
#             is_interested=True,
#             response_status='interested'
#         ).count()
    
#     def get_pending_responses(self, obj):
#         """Count jobs waiting for mukadam's response"""
#         return MukadamInterest.objects.filter(
#             mukadam=obj,
#             response_status='pending'
#         ).count()
# class MukadamSerializer(serializers.ModelSerializer):
#     activity_rates = MukadamActivityRateSerializer(many=True, read_only=True)
    
#     class Meta:
#         model = Mukadam
#         fields = [
#             'id', 'name', 'phone', 'location', 'number_of_labourers', 
#             'is_active', 'created_at', 'activity_rates'
#         ]

# class MukadamInterestSerializer(serializers.ModelSerializer):
#     mukadam = MukadamSerializer(read_only=True)
    
#     class Meta:
#         model = MukadamInterest
#         fields = ['id', 'mukadam', 'is_interested','response_status', 'responded_at']

# # Update JobSerializer 
# class JobSerializer(serializers.ModelSerializer):
#     farmer = FarmerSerializer(read_only=True)
#     activity = ActivitySerializer(read_only=True)
#     interests = MukadamInterestSerializer(many=True, read_only=True)  # ADD this line
#     finalized_mukadam = MukadamSerializer(read_only=True)
    
#     class Meta:
#         model = Job
#         fields = [
#             'finalized_mukadam', 
#             'id', 'farmer', 'activity', 'farm_size_acres', 'location', 
#             'requested_date', 'requested_time', 'farmer_price_per_acre',
#             'your_price_per_acre', 'status', 'interests' ,'workers_needed' # ADD interests here
#         ]

#     def update(self, instance, validated_data):
#         """Override update to track changes"""
#         changed_by = self.context.get('request').user.username if self.context.get('request') and self.context.get('request').user.is_authenticated else 'System'
#         edit_reason = validated_data.pop('edit_reason', '')
        
#         for field, new_value in validated_data.items():
#             old_value = getattr(instance, field)
#             if old_value != new_value:
#                 JobEditHistory.objects.create(
#                     assign_job=instance,
#                     field_changed=field.replace('_', ' ').title(),
#                     old_value=str(old_value),
#                     new_value=str(new_value),
#                     changed_by=changed_by,
#                     reason=edit_reason
#                 )
        
#         return super().update(instance, validated_data)

# class ActivityBriefSerializer(serializers.Serializer):
#     """Serializer for individual activity briefs"""
#     activity_name = serializers.CharField()
#     acres = serializers.DecimalField(max_digits=10, decimal_places=2)
#     date_needed = serializers.DateField(required=False, allow_null=True)


# class JobCreateSerializer(serializers.Serializer):
#     """
#     Serializer for creating a job from labour need data
#     Handles the payload from the chatbot API with activity_briefs
#     """
#     # Labour need fields
#     farmer_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
#     phone_number = serializers.CharField()
#     date_needed = serializers.DateField(required=False, allow_null=True)
#     special_requirements = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
#     # Activity briefs (list of activities)
#     activity_briefs = serializers.ListField(
#         child=ActivityBriefSerializer(),
#         required=False,
#         allow_empty=True
#     )
    
#     # Job-specific fields
#     location = serializers.CharField(required=False, allow_blank=True, default='')
#     farmer_village = serializers.CharField(required=False, allow_blank=True, default='')
#     requested_time = serializers.TimeField(required=False, allow_null=True)
#     farmer_price_per_acre = serializers.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         required=False, 
#         allow_null=True,
#         default=0
#     )
#     notes = serializers.CharField(required=False, allow_blank=True, default='')
#     workers_needed = serializers.IntegerField(required=False, default=5)
    
#     def validate(self, data):
#         """Validate the incoming data"""
#         # Check if we have activity briefs
#         if not data.get('activity_briefs'):
#             raise serializers.ValidationError({
#                 'activity_briefs': 'At least one activity brief is required'
#             })
        
#         # Validate phone number
#         if not data.get('phone_number'):
#             raise serializers.ValidationError({
#                 'phone_number': 'Phone number is required'
#             })
        
#         return data
    
#     def create(self, validated_data):
#         """
#         Create job(s) from the activity briefs
#         If multiple activity briefs exist, create a job for the first one
#         or combine them based on your business logic
#         """
#         # Extract data
#         phone_number = validated_data['phone_number']
#         farmer_name = validated_data.get('farmer_name', 'Unknown Farmer')
#         farmer_village = validated_data.get('farmer_village', validated_data.get('location', ''))
#         activity_briefs = validated_data.pop('activity_briefs', [])
#         special_requirements = validated_data.get('special_requirements', '')
        
#         # Get or create farmer
#         farmer, created = Farmer.objects.get_or_create(
#             phone=phone_number,
#             defaults={
#                 'name': farmer_name or f"Farmer {phone_number}",
#                 'village': farmer_village
#             }
#         )
        
#         # If farmer exists but name was missing, update it
#         if not created and farmer_name and farmer_name != 'Unknown Farmer':
#             farmer.name = farmer_name
#             farmer.save(update_fields=['name'])
        
#         jobs_created = []
        
#         # Create a job for each activity brief
#         for brief in activity_briefs:
#             activity_name = brief['activity_name']
#             acres = brief['acres']
#             brief_date = brief.get('date_needed') or validated_data.get('date_needed')
            
#             # Get or create activity
#             activity, _ = Activity.objects.get_or_create(
#                 name=activity_name,
#                 defaults={'name': activity_name}
#             )
            
#             # Prepare job data
#             job_data = {
#                 'farmer': farmer,
#                 'activity': activity,
#                 'farm_size_acres': acres,
#                 'location': validated_data.get('location', farmer_village),
#                 'requested_date': brief_date or timezone.now().date(),
#                 'requested_time': validated_data.get('requested_time') or timezone.now().time(),
#                 'farmer_price_per_acre': validated_data.get('farmer_price_per_acre', 0),
#                 'notes': f"{special_requirements}\n{validated_data.get('notes', '')}".strip(),
#                 'workers_needed': validated_data.get('workers_needed', 5),
#                 'status': 'confirmed'
#             }
            
#             # Create job
#             job = Job.objects.create(**job_data)
#             jobs_created.append(job)
        
#         # Return the first job (or you could return all jobs)
#         return jobs_created[0] if jobs_created else None
    

# class MukadamBidSerializer(serializers.ModelSerializer):
#     mukadam = MukadamSerializer(read_only=True)
    
#     class Meta:
#         model = MukadamBid
#         fields = '__all__'

# class MukadamBidCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = MukadamBid
#         fields = [
#             'job', 'mukadam', 'bid_price_per_acre', 
#             'estimated_duration_hours', 'comments'
#         ]
    
#     def create(self, validated_data):
#         # Update existing bid or create new one
#         job = validated_data['job']
#         mukadam = validated_data['mukadam']
        
#         bid, created = MukadamBid.objects.update_or_create(
#             job=job,
#             mukadam=mukadam,
#             defaults={
#                 'status': 'interested',
#                 'bid_price_per_acre': validated_data['bid_price_per_acre'],
#                 'estimated_duration_hours': validated_data.get('estimated_duration_hours'),
#                 'comments': validated_data.get('comments', ''),
#                 'responded_at': timezone.now()
#             }
#         )
        
#         return bid

# class WhatsAppNotificationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = WhatsAppNotification
#         fields = '__all__'

# class JobStatusHistorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = JobStatusHistory
#         fields = '__all__'
# # Update serializers.py
# class MukadamBidDetailSerializer(serializers.ModelSerializer):
#     mukadam_name = serializers.CharField(source='mukadam.name', read_only=True)
#     mukadam_phone = serializers.CharField(source='mukadam.phone', read_only=True)
#     mukadam_location = serializers.CharField(source='mukadam.location', read_only=True)
#     mukadam_labourers = serializers.IntegerField(source='mukadam.number_of_labourers', read_only=True)
    
#     # Add performance data
#     mukadam_total_bids = serializers.SerializerMethodField()
#     mukadam_won_bids = serializers.SerializerMethodField()
#     mukadam_avg_bid_price = serializers.SerializerMethodField()
#     mukadam_success_rate = serializers.SerializerMethodField()
    
#     class Meta:
#         model = MukadamBid
#         fields = [
#             'id', 'status', 'bid_price_per_acre', 'final_price_per_acre',
#             'estimated_duration_hours', 'comments', 'created_at', 'responded_at',
#             'mukadam_name', 'mukadam_phone', 'mukadam_location', 'mukadam_labourers',
#             'mukadam_total_bids', 'mukadam_won_bids', 'mukadam_avg_bid_price', 'mukadam_success_rate'
#         ]
    
#     def get_mukadam_total_bids(self, obj):
#         return MukadamBid.objects.filter(mukadam=obj.mukadam, status__in=['interested', 'selected', 'rejected']).count()
    
#     def get_mukadam_won_bids(self, obj):
#         return MukadamBid.objects.filter(mukadam=obj.mukadam, status='selected').count()
    
#     def get_mukadam_avg_bid_price(self, obj):
#         from django.db.models import Avg
#         avg = MukadamBid.objects.filter(
#             mukadam=obj.mukadam, 
#             status__in=['interested', 'selected', 'rejected'],
#             bid_price_per_acre__isnull=False
#         ).aggregate(avg_price=Avg('bid_price_per_acre'))['avg_price']
#         return round(float(avg), 2) if avg else 0
    
#     def get_mukadam_success_rate(self, obj):
#         total = self.get_mukadam_total_bids(obj)
#         won = self.get_mukadam_won_bids(obj)
#         return round((won / total * 100), 1) if total > 0 else 0

# class JobDetailSerializer(serializers.ModelSerializer):
#     farmer = FarmerSerializer(read_only=True)
#     activity = ActivitySerializer(read_only=True)
#     finalized_mukadam = MukadamSerializer(read_only=True)
#     all_bids = MukadamBidDetailSerializer(source='bids', many=True, read_only=True)  # ✅ All bids
    
#     class Meta:
#         model = Job
#         fields = [
#             'id', 'farmer', 'activity', 'farm_size_acres', 'location',
#             'requested_date', 'requested_time', 'farmer_price_per_acre',
#             'status', 'notes', 'finalized_mukadam', 'finalized_price',
#             'confirmed_at', 'finalized_at', 'all_bids'  # ✅ Include all bids
#         ]
# # Add this to your serializers.py

# class SaveFCMTokenSerializer(serializers.Serializer):
#     fcm_token = serializers.CharField(required=True, max_length=255)
#     platform = serializers.CharField(required=False, default='android')
    
#     def validate_fcm_token(self, value):
#         if not value or len(value) < 10:
#             raise serializers.ValidationError("Invalid FCM token")
#         return value

# from rest_framework import serializers
# from .models import Farmer, FarmerPlot, FarmerEditHistory


# class FarmerPlotSerializer(serializers.ModelSerializer):
#     """Enhanced plot serializer with job information"""
#     related_jobs = serializers.SerializerMethodField()
    
#     class Meta:
#         model = FarmerPlot
#         fields = ['id', 'acres', 'location', 'activity_name', 'pruning_date', 
#                   'notes', 'related_jobs', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'created_at', 'updated_at']
    
#     def get_related_jobs(self, obj):
#         """Get all jobs related to this plot's activity"""
#         jobs = Job.objects.filter(
#             farmer=obj.farmer,
#             activity__name=obj.activity_name
#         ).values('id', 'status', 'requested_date', 'farm_size_acres')
#         return list(jobs)


# class FarmerEditHistorySerializer(serializers.ModelSerializer):
#     """Enhanced history showing job-related changes"""
#     class Meta:
#         model = FarmerEditHistory
#         fields = ['id', 'field_changed', 'old_value', 'new_value', 'changed_by', 
#                   'changed_at', 'reason', 'model_name', 'object_id']


# class FarmerSerializer(serializers.ModelSerializer):
#     """Enhanced farmer serializer with plots and jobs"""
#     plots = FarmerPlotSerializer(many=True, read_only=True)
#     total_acres = serializers.SerializerMethodField()
#     jobs_count = serializers.ReadOnlyField()
#     recent_jobs = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Farmer
#         fields = ['id', 'name', 'phone', 'village', 'plots', 'total_acres', 
#                   'jobs_count', 'recent_jobs', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'created_at', 'updated_at']
    
#     def get_total_acres(self, obj):
#         """Calculate total unique acres from plots"""
#         total = obj.plots.aggregate(total=models.Sum('acres'))['total']
#         return float(total) if total else 0.0
    
#     def get_recent_jobs(self, obj):
#         """Get recent jobs for this farmer"""
#         jobs = Job.objects.filter(farmer=obj).select_related('activity').order_by('-requested_date')[:5]
#         return [{
#             'id': str(job.id),
#             'activity': job.activity.name,
#             'acres': float(job.farm_size_acres),
#             'status': job.status,
#             'date': str(job.requested_date)
#         } for job in jobs]

# class JobEditHistorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = JobEditHistory
#         fields = ['id', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at', 'reason']


# class MukadamSerializer(serializers.ModelSerializer):
#     # Add calculated fields
#     total_jobs = serializers.SerializerMethodField()
#     completed_jobs = serializers.SerializerMethodField()
#     current_jobs = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Mukadam
#         fields = [
#             'id', 'name', 'phone', 'location', 'number_of_labourers', 
#             'is_active', 'created_at', 'total_jobs', 'completed_jobs', 'current_jobs'
#         ]
    
#     def get_total_jobs(self, obj):
#         """Get total number of jobs assigned to this mukadam"""
#         return Job.objects.filter(finalized_mukadam=obj).count()
    
#     def get_completed_jobs(self, obj):
#         """Get number of completed jobs"""
#         return Job.objects.filter(finalized_mukadam=obj, status='completed').count()
    
#     def get_current_jobs(self, obj):
#         """Get number of current active jobs"""
#         return Job.objects.filter(
#             finalized_mukadam=obj,
#             status__in=['finalized', 'in_progress']
#         ).count()

# class MukadamCreateSerializer(serializers.ModelSerializer):



#     """Serializer for creating new mukadams"""
#     class Meta:
#         model = Mukadam
#         fields = [
#             'name', 'phone', 'location', 'number_of_labourers', 'is_active'
#         ]
    
#     def validate_phone(self, value):
#         """Validate phone number format"""
#         import re
#         if not re.match(r'^\+91-?\d{10}$', value):
#             raise serializers.ValidationError(
#                 "Phone number must be in format: +91-XXXXXXXXXX"
#             )
#         return value
    
#     def validate_number_of_labourers(self, value):
#         """Validate number of labourers"""
#         if value < 1:
#             raise serializers.ValidationError(
#                 "Number of labourers must be at least 1"
#             )
#         if value > 100:
#             raise serializers.ValidationError(
#                 "Number of labourers cannot exceed 100"
#             )
#         return value
from rest_framework import serializers
from django.utils import timezone
from .models import *


# serializers.py
class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = ['id', 'name', 'description', 'created_at']

class CropVarietySerializer(serializers.ModelSerializer):
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    
    class Meta:
        model = CropVariety
        fields = ['id', 'crop', 'crop_name', 'name', 'description', 'created_at']

class CropWithVarietiesSerializer(serializers.ModelSerializer):
    varieties = CropVarietySerializer(many=True, read_only=True)
    
    class Meta:
        model = Crop
        fields = ['id', 'name', 'description', 'varieties', 'created_at']


class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = '__all__'
class ActivitySerializer(serializers.ModelSerializer):
    crop_name = serializers.CharField(source='crop.name', read_only=True, allow_null=True)  # ✅ ADD allow_null
    
    class Meta:
        model = Activity
        fields = ['id', 'name', 'description', 'days_after_pruning', 'crop', 'crop_name']  # ✅ REMOVE created_at if not in model
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
    interested_jobs = serializers.SerializerMethodField()  # ✅ NEW
    pending_responses = serializers.SerializerMethodField()  # ✅ NEW
    
    class Meta:
        model = Mukadam
        fields = [
            'id', 'name', 'phone', 'location', 'number_of_labourers',
            'is_active', 'created_at', 'activity_rates', 
            'total_jobs', 'completed_jobs', 'won_bids', 'avg_bid_price',
            'interested_jobs', 'pending_responses'  # ✅ ADD these
        ]
    
    def get_total_jobs(self, obj):
        """Count ALL jobs this mukadam was notified about (has interest record for)"""
        return MukadamInterest.objects.filter(mukadam=obj).count()
    
    def get_completed_jobs(self, obj):
        """Count jobs actually completed by this mukadam"""
        return Job.objects.filter(
            finalized_mukadam=obj,
            status='completed'
        ).count()
    
    def get_won_bids(self, obj):
        """Count jobs where this mukadam was actually assigned/finalized"""
        return Job.objects.filter(
            finalized_mukadam=obj,
            status__in=['finalized', 'assigned', 'in_progress', 'completed']
        ).count()
    
    def get_avg_bid_price(self, obj):
        """Average bid price from completed jobs"""
        completed = Job.objects.filter(
            finalized_mukadam=obj,
            status='completed'
        ).aggregate(avg=models.Avg('finalized_price'))
        return float(completed['avg'] or 0)
    
    def get_interested_jobs(self, obj):
        """Count jobs where mukadam showed interest"""
        return MukadamInterest.objects.filter(
            mukadam=obj,
            is_interested=True,
            response_status='interested'
        ).count()
    
    def get_pending_responses(self, obj):
        """Count jobs waiting for mukadam's response"""
        return MukadamInterest.objects.filter(
            mukadam=obj,
            response_status='pending'
        ).count()
class MukadamSerializer(serializers.ModelSerializer):
    activity_rates = MukadamActivityRateSerializer(many=True, read_only=True)
    
    class Meta:
        model = Mukadam
        fields = [
            'id', 'name', 'phone', 'location', 'number_of_labourers', 
            'is_active', 'created_at', 'activity_rates'
        ]

class MukadamInterestSerializer(serializers.ModelSerializer):
    mukadam = MukadamSerializer(read_only=True)
    
    class Meta:
        model = MukadamInterest
        fields = ['id', 'mukadam', 'is_interested','response_status', 'responded_at']

# Update JobSerializer 
class JobSerializer(serializers.ModelSerializer):
    farmer = FarmerSerializer(read_only=True)
    activity = ActivitySerializer(read_only=True)
    crop_name = serializers.CharField(source='crop.name', read_only=True, allow_null=True)  # ✅ ADD
    crop_variety_name = serializers.CharField(source='crop_variety.name', read_only=True, allow_null=True)  # ✅ ADD
    interests = MukadamInterestSerializer(many=True, read_only=True)
    finalized_mukadam = MukadamSerializer(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'farmer', 'activity', 
            'crop', 'crop_name', 'crop_variety', 'crop_variety_name',  # ✅ ADD THESE
            'farm_size_acres', 'location', 
            'requested_date', 'requested_time', 'farmer_price_per_acre',
            'your_price_per_acre', 'status', 'interests', 'workers_needed',
            'finalized_mukadam'
        ]

    def update(self, instance, validated_data):
        """Override update to track changes"""
        changed_by = self.context.get('request').user.username if self.context.get('request') and self.context.get('request').user.is_authenticated else 'System'
        edit_reason = validated_data.pop('edit_reason', '')
        
        for field, new_value in validated_data.items():
            old_value = getattr(instance, field)
            if old_value != new_value:
                JobEditHistory.objects.create(
                    assign_job=instance,
                    field_changed=field.replace('_', ' ').title(),
                    old_value=str(old_value),
                    new_value=str(new_value),
                    changed_by=changed_by,
                    reason=edit_reason
                )
        
        return super().update(instance, validated_data)

class ActivityBriefSerializer(serializers.Serializer):
    """Serializer for individual activity briefs"""
    activity_id = serializers.UUIDField(required=False, allow_null=True)  # ✅ NEW
    activity_name = serializers.CharField(required=False, allow_blank=True)  # ✅ Make optional
    acres = serializers.DecimalField(max_digits=10, decimal_places=2)
    date_needed = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Ensure either activity_id or activity_name is provided"""
        if not data.get('activity_id') and not data.get('activity_name'):
            raise serializers.ValidationError(
                "Either activity_id or activity_name must be provided"
            )
        return data

class JobCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a job from labour need data
    Handles the payload from the chatbot API with activity_briefs
    """
    # Labour need fields
    farmer_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField()
    date_needed = serializers.DateField(required=False, allow_null=True)
    special_requirements = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    # ✅ Crop fields - ADD these at the top level
    crop_id = serializers.UUIDField(required=False, allow_null=True)
    crop_variety_id = serializers.UUIDField(required=False, allow_null=True)
    
    # Activity briefs (list of activities)
    activity_briefs = serializers.ListField(
        child=ActivityBriefSerializer(),
        required=False,
        allow_empty=True
    )
    
    # Job-specific fields
    location = serializers.CharField(required=False, allow_blank=True, default='')
    farmer_village = serializers.CharField(required=False, allow_blank=True, default='')
    requested_time = serializers.TimeField(required=False, allow_null=True)
    farmer_price_per_acre = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        allow_null=True,
        default=0
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    workers_needed = serializers.IntegerField(required=False, default=5)
    
    def validate(self, data):
        """Validate the incoming data"""
        # Check if we have activity briefs
        if not data.get('activity_briefs'):
            raise serializers.ValidationError({
                'activity_briefs': 'At least one activity brief is required'
            })
        
        # Validate phone number
        if not data.get('phone_number'):
            raise serializers.ValidationError({
                'phone_number': 'Phone number is required'
            })
        
        # ✅ ADD: Validate crop_id if provided
        if data.get('crop_id'):
            try:
                Crop.objects.get(id=data['crop_id'])
            except Crop.DoesNotExist:
                raise serializers.ValidationError({
                    'crop_id': 'Invalid crop ID'
                })
        
        # ✅ ADD: Validate crop_variety_id if provided
        if data.get('crop_variety_id'):
            try:
                CropVariety.objects.get(id=data['crop_variety_id'])
            except CropVariety.DoesNotExist:
                raise serializers.ValidationError({
                    'crop_variety_id': 'Invalid crop variety ID'
                })
        
        return data
    
    def create(self, validated_data):
        """Create job(s) from the activity briefs - WITH AUTO-PRICING"""
        phone_number = validated_data['phone_number']
        farmer_name = validated_data.get('farmer_name', 'Unknown Farmer')
        farmer_village = validated_data.get('farmer_village', validated_data.get('location', ''))
        activity_briefs = validated_data.pop('activity_briefs', [])
        special_requirements = validated_data.get('special_requirements', '')
        
        crop_id = validated_data.get('crop_id')
        crop_variety_id = validated_data.get('crop_variety_id')
        
        crop = None
        crop_variety = None
        
        if crop_id:
            try:
                crop = Crop.objects.get(id=crop_id)
            except Crop.DoesNotExist:
                pass
        
        if crop_variety_id:
            try:
                crop_variety = CropVariety.objects.get(id=crop_variety_id)
            except CropVariety.DoesNotExist:
                pass
        
        # Get or create farmer
        farmer, created = Farmer.objects.get_or_create(
            phone=phone_number,
            defaults={
                'name': farmer_name or f"Farmer {phone_number}",
                'village': farmer_village
            }
        )
        
        if not created and farmer_name and farmer_name != 'Unknown Farmer':
            farmer.name = farmer_name
            farmer.save(update_fields=['name'])
        
        jobs_created = []
        
        for brief in activity_briefs:
            activity_id = brief.get('activity_id')
            activity_name = brief.get('activity_name')
            acres = brief['acres']
            brief_date = brief.get('date_needed') or validated_data.get('date_needed')
            
            # Get activity
            if activity_id:
                try:
                    activity = Activity.objects.get(id=activity_id)
                except Activity.DoesNotExist:
                    if activity_name:
                        activity, _ = Activity.objects.get_or_create(
                            name=activity_name,
                            defaults={'name': activity_name}
                        )
                    else:
                        raise serializers.ValidationError(
                            f"Activity with ID {activity_id} not found"
                        )
            elif activity_name:
                activity, _ = Activity.objects.get_or_create(
                    name=activity_name,
                    defaults={'name': activity_name}
                )
            else:
                raise serializers.ValidationError(
                    "Either activity_id or activity_name must be provided"
                )
            
            job_crop = crop if crop else (activity.crop if hasattr(activity, 'crop') else None)
            job_crop_variety = crop_variety
            
            # ✅ AUTO-PRICE: Get company rate for this activity
            your_price_per_acre = None
            job_status = 'confirmed'  # Default status
            
            try:
                company_rate = CompanyActivityRate.objects.get(
                    activity=activity,
                    is_active=True
                )
                your_price_per_acre = company_rate.rate_per_acre
                
                # Check if company rate is within farmer's budget
                farmer_budget = validated_data.get('farmer_price_per_acre', 0)
                if your_price_per_acre <= farmer_budget:
                    job_status = 'priced'  # Auto-price successful
                else:
                    # Company rate too high, keep as confirmed for manual pricing
                    your_price_per_acre = None
                    job_status = 'confirmed'
                    
            except CompanyActivityRate.DoesNotExist:
                # No company rate configured, keep as confirmed
                your_price_per_acre = None
                job_status = 'confirmed'
            
            job_data = {
                'farmer': farmer,
                'activity': activity,
                'crop': job_crop,
                'crop_variety': job_crop_variety,
                'farm_size_acres': acres,
                'location': validated_data.get('location', farmer_village),
                'requested_date': brief_date or timezone.now().date(),
                'requested_time': validated_data.get('requested_time') or timezone.now().time(),
                'farmer_price_per_acre': validated_data.get('farmer_price_per_acre', 0),
                'your_price_per_acre': your_price_per_acre,  # ✅ AUTO-SET
                'notes': f"{special_requirements}\n{validated_data.get('notes', '')}".strip(),
                'workers_needed': validated_data.get('workers_needed', 5),
                'status': job_status  # ✅ AUTO-SET TO 'priced' if rate found
            }
            
            job = Job.objects.create(**job_data)
            jobs_created.append(job)
        
        return jobs_created[0] if jobs_created else None
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
    crop_name = serializers.CharField(source='crop.name', read_only=True, allow_null=True)  # ✅ ADD
    crop_variety_name = serializers.CharField(source='crop_variety.name', read_only=True, allow_null=True)  # ✅ ADD
    finalized_mukadam = MukadamSerializer(read_only=True)
    all_bids = MukadamBidDetailSerializer(source='bids', many=True, read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'farmer', 'activity', 
            'crop', 'crop_name', 'crop_variety', 'crop_variety_name',  # ✅ ADD
            'farm_size_acres', 'location',
            'requested_date', 'requested_time', 'farmer_price_per_acre',
            'status', 'notes', 'finalized_mukadam', 'finalized_price',
            'confirmed_at', 'finalized_at', 'all_bids'
        ]
# Add this to your serializers.py

class SaveFCMTokenSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(required=True, max_length=255)
    platform = serializers.CharField(required=False, default='android')
    
    def validate_fcm_token(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError("Invalid FCM token")
        return value

from rest_framework import serializers
from .models import Farmer, FarmerPlot, FarmerEditHistory


class FarmerPlotSerializer(serializers.ModelSerializer):
    related_jobs = serializers.SerializerMethodField()
    calculated_activity_date = serializers.ReadOnlyField()
    days_until_activity = serializers.ReadOnlyField()
    activity_details = serializers.SerializerMethodField()
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    crop_variety_name = serializers.CharField(source='crop_variety.name', read_only=True)
    
    class Meta:
        model = FarmerPlot
        fields = [
            'id', 'acres', 'location', 
            'crop', 'crop_name', 'crop_variety', 'crop_variety_name',  # ✅ ADD
            'activity_name', 'activity', 'activity_details',
            'pruning_date', 'calculated_activity_date', 'days_until_activity',
            'notes', 'related_jobs',
            'created_at', 'updated_at'
        ]
    
    def get_activity_details(self, obj):
        if obj.activity:
            return {
                'id': str(obj.activity.id),
                'name': obj.activity.name,
                'days_after_pruning': obj.activity.days_after_pruning,
                'description': obj.activity.description
            }
        return None
    
    def get_related_jobs(self, obj):
        jobs = Job.objects.filter(
        farmer=obj.farmer,
        activity=obj.activity
    )
    
    # Only filter by crop/variety if they exist
        if obj.crop:
            jobs = jobs.filter(crop=obj.crop)
        if obj.crop_variety:
            jobs = jobs.filter(crop_variety=obj.crop_variety)
        
        jobs = jobs.order_by('-requested_date')[:5]
        
        return [{
            'id': str(job.id),
            'status': job.status,
            'requested_date': job.requested_date,
            'farm_size_acres': float(job.farm_size_acres)
        } for job in jobs]


class FarmerEditHistorySerializer(serializers.ModelSerializer):
    """Enhanced history showing job-related changes"""
    class Meta:
        model = FarmerEditHistory
        fields = ['id', 'field_changed', 'old_value', 'new_value', 'changed_by', 
                  'changed_at', 'reason', 'model_name', 'object_id']


class FarmerSerializer(serializers.ModelSerializer):
    plots = FarmerPlotSerializer(many=True, read_only=True)
    total_acres = serializers.ReadOnlyField()
    jobs_count = serializers.ReadOnlyField()
    recent_jobs = serializers.SerializerMethodField()
    
    class Meta:
        model = Farmer
        fields = [
            'id', 'name', 'phone', 'village',
            'plots', 'total_acres', 'jobs_count', 'recent_jobs',
            'created_at', 'updated_at'
        ]
    
    def get_recent_jobs(self, obj):
        jobs = Job.objects.filter(farmer=obj).order_by('-requested_date')[:5]
        return [{
            'id': str(job.id),
            'activity': job.activity.name if job.activity else None,  # ✅ Already correct
            'crop': job.crop.name if job.crop else None,  # ✅ Already correct
            'variety': job.crop_variety.name if job.crop_variety else None,  # ✅ Already correct
            'acres': float(job.farm_size_acres),
            'status': job.status,
            'date': job.requested_date
        } for job in jobs]
    def get_total_acres(self, obj):
        """Calculate total unique acres from plots"""
        total = obj.plots.aggregate(total=models.Sum('acres'))['total']
        return float(total) if total else 0.0
    
    

class JobEditHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobEditHistory
        fields = ['id', 'field_changed', 'old_value', 'new_value', 'changed_by', 'changed_at', 'reason']


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