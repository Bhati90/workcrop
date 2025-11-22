from rest_framework import serializers
from .models import Mukkadam

class MukkadamFullSerializer(serializers.ModelSerializer):
    # Read-only fields to show names instead of just IDs
    referred_by_name = serializers.CharField(source='referred_by.mukkadam_name', read_only=True)
    
    # Get list of people this person has referred
    referrals_list = serializers.SerializerMethodField()

    class Meta:
        model = Mukkadam
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'referrals_list', 'referred_by_name']

    def get_referrals_list(self, obj):
        # Return a list of names and IDs of people this person referred
        return obj.referrals_made.values('id', 'mukkadam_name', 'village')

# Helper serializer for the Dropdown in the Form
class MukkadamDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mukkadam
        fields = ['id', 'mukkadam_name', 'mobile_numbers', 'village']

class MukkadamListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mukkadam
        # Exclude sensitive fields for the general list
        exclude = [
            'mobile_numbers', 
            'deputy_mukkadam_mobile', 
            'payment_details', 
            'team_members',
            'aadhar_card',
            'pan_card',
            'bank_proof'
        ]

from rest_framework import serializers
from .models import Job, JobAssignment, Mukkadam, AssignmentLog


class MukkadamBasicSerializer(serializers.ModelSerializer):
    """Basic mukkadam info for dropdowns and lists"""
    class Meta:
        model = Mukkadam
        fields = [
            'id', 
            'mukkadam_name', 
            'mobile_numbers', 
            'village',
            'crew_size',
            'max_crew_capacity',
            'has_smartphone',
            'team_members',
        ]


class JobAssignmentSerializer(serializers.ModelSerializer):
    mukkadam_details = MukkadamBasicSerializer(source='mukkadam', read_only=True)
    mukkadam_id = serializers.IntegerField(write_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.username', read_only=True)
    workers_count = serializers.IntegerField(required=False)
    team_members = serializers.ListField(child=serializers.CharField(), required=False)
    agreed_rate = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = JobAssignment
        fields = [
            'id',
            'job',
            'mukkadam_id',
            'mukkadam_details',
            'workers_count',
            'team_members',
            'status',
            'agreed_rate',
            'payment_status',
            'notes',
            'assigned_at',
            'assigned_by',
            'assigned_by_name',
            'confirmed_at',
            'completed_at',
        ]
        read_only_fields = ['assigned_at', 'assigned_by']

    def create(self, validated_data):
        mukkadam_id = validated_data.pop('mukkadam_id')
        validated_data['mukkadam_id'] = mukkadam_id
        validated_data['assigned_by'] = self.context['request'].user
        
        assignment = super().create(validated_data)
        
        # Create log entry
        AssignmentLog.objects.create(
            assignment=assignment,
            user=self.context['request'].user,
            action='created',
            details={
                'mukkadam_name': assignment.mukkadam.mukkadam_name,
                'workers_count': assignment.workers_count,
            }
        )
        
        return assignment

    def update(self, instance, validated_data):
        # Log the update
        old_status = instance.status
        old_workers = instance.workers_count
        
        if 'mukkadam_id' in validated_data:
            mukkadam_id = validated_data.pop('mukkadam_id')
            validated_data['mukkadam_id'] = mukkadam_id
        
        assignment = super().update(instance, validated_data)
        
        # Create log entry
        changes = {}
        if old_status != assignment.status:
            changes['status'] = {'from': old_status, 'to': assignment.status}
        if old_workers != assignment.workers_count:
            changes['workers_count'] = {'from': old_workers, 'to': assignment.workers_count}
        
        if changes:
            AssignmentLog.objects.create(
                assignment=assignment,
                user=self.context['request'].user,
                action='updated',
                details=changes
            )
        
        return assignment


class JobSerializer(serializers.ModelSerializer):
    assignments = JobAssignmentSerializer(many=True, read_only=True)
    total_assigned_workers = serializers.IntegerField(read_only=True)
    is_fully_assigned = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Job
        fields = [
            'id',
            'title',
            'start_date',
            'plot_name',
            'plot_area',
            'plot_crop',
            'farmer_name',
            'farmer_phone',
            'farmer_id',
            'location',
            'village',
            'taluka',
            'district',
            'fir_id',
            'notes',
            'class_name',
            'workers_required',
            'status',
            'all_day',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'assignments',
            'total_assigned_workers',
            'is_fully_assigned',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class JobListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views"""
    total_assigned_workers = serializers.IntegerField(read_only=True)
    is_fully_assigned = serializers.BooleanField(read_only=True)
    assignments_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id',
            'title',
            'start_date',
            'farmer_name',
            'village',
            'workers_required',
            'total_assigned_workers',
            'status',
            'is_fully_assigned',
            'assignments_count',
            'created_at',
        ]

    def get_assignments_count(self, obj):
        return obj.assignments.count()


class AssignmentLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AssignmentLog
        fields = ['id', 'action', 'details', 'timestamp', 'user', 'user_name']