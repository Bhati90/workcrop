from django.db import models
from django.contrib.auth.models import User
import uuid
import os

def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    # This puts everything inside "products/" folder in your S3 bucket
    return f"media/{filename}"
class Mukkadam(models.Model):
    # --- Tracking Information ---
    # Who created/updated this profile (The Agent)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_mukkadams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- 1. Basic Details ---
    mukkadam_name = models.CharField(max_length=255)
    mobile_numbers = models.CharField(max_length=255)
    village = models.CharField(max_length=255)
    has_smartphone = models.CharField(max_length=10) # 'yes' or 'no'

    # --- 2. Crew Details ---
    crew_size = models.CharField(max_length=50)
    max_crew_capacity = models.CharField(max_length=50, blank=True, null=True)
    splitting_logic = models.TextField(blank=True, null=True)
    deputy_mukkadam_name = models.CharField(max_length=255, blank=True, null=True)
    deputy_mukkadam_mobile = models.CharField(max_length=20, blank=True, null=True)

    # --- 2a. Team Members (Nested Array) ---
    # Stores: [{"name": "...", "mobile": "..."}]
    team_members = models.JSONField(default=list, blank=True)

    # --- 3. Availability ---
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    # Add null=True to optional CharField fields
    daily_work_timing = models.CharField(max_length=100, blank=True, null=True)
    # Stores: [{"teamNumber": "...", "startDate": "...", "endDate": "..."}]
    team_availabilities = models.JSONField(default=list, blank=True)

    # --- 4. Rate Card (Nested Object) ---
    # Stores: { "failFoot": "...", "secondFail": "...", ... }
    rate_card = models.JSONField(default=dict, blank=True)

    # --- 5. Work Area Preference ---
    home_location = models.CharField(max_length=255, blank=True)
    preferred_work_locations = models.TextField(blank=True)
    max_travel_distance = models.CharField(max_length=50, blank=True,null=True)

    # --- 6. Transport Details ---
    transport_mode = models.CharField(max_length=50) # own_bike, own_pickup, no_vehicle
    transport_arranged_by = models.CharField(max_length=50, blank=True,null=True) # self, company
    # Stores: { "bikeChargePerBike": "...", "currentlyStationedAt": "..." }
    transport_charges = models.JSONField(default=dict, blank=True)

    # --- 7. Payment Details ---
    # Stores: { "modes": {...}, "upiId": "...", "accountNumber": "..." }
    payment_details = models.JSONField(default=dict, blank=True)

    # --- 8. Work Mode ---
    work_mode = models.CharField(max_length=50) # daily_up_down, move_in, both
    move_in_preferred_region = models.CharField(max_length=255, blank=True, null=True)

    # --- 9. Referral ---
    
    referral_source = models.CharField(max_length=255, blank=True, null=True)
    referred_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='referrals_made' # This lets us see who they referred
    )
    
    # Keep the old text field just in case they were referred by an outsider
    referral_source_text = models.CharField(max_length=255, blank=True, null=True)

    # --- 10. Notification Preferences ---
    notification_preferences = models.JSONField(default=dict, blank=True)

    # --- 11. Other Info ---
    other_commitments = models.TextField(blank=True)

    # Add these two lines near the other document fields
    aadhar_number = models.CharField(max_length=50, blank=True, null=True)
    pan_number = models.CharField(max_length=50, blank=True, null=True)

    # --- 12. Documents (Images) ---
    profile_photo = models.ImageField(upload_to=get_file_path, null=True, blank=True)
    aadhar_card = models.ImageField(upload_to=get_file_path, null=True, blank=True)
    pan_card = models.ImageField(upload_to=get_file_path, null=True, blank=True)
    bank_proof = models.ImageField(upload_to=get_file_path, null=True, blank=True)
    def __str__(self):
        return f"{self.mukkadam_name} ({self.village})"
    


# ... existing Mukkadam model ...

class ActivityLog(models.Model):
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True) # The Agent
    action_type = models.CharField(max_length=50) # e.g., "Availability Update", "Profile Edit"
    details = models.TextField(blank=True) # What exactly changed
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action_type} - {self.timestamp}"
    

# Add these models to your existing models.py file

from django.db import models
from django.contrib.auth.models import User


class Job(models.Model):
    """
    Job posted by farmers that needs mukkadams/workers
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Job Details
    title = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    plot_name = models.CharField(max_length=255, blank=True, null=True)
    plot_area = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    plot_crop = models.CharField(max_length=100, blank=True, null=True)
    
    # Farmer Details
    farmer_name = models.CharField(max_length=255, blank=True, null=True)
    farmer_phone = models.CharField(max_length=20, blank=True, null=True)
    farmer_id = models.CharField(max_length=50, blank=True, null=True)
    
    # Location
    location = models.CharField(max_length=255, blank=True, null=True)
    village = models.CharField(max_length=255, blank=True, null=True)
    taluka = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=255, blank=True, null=True)
    
    # Job Requirements
    fir_id = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    class_name = models.CharField(max_length=100, blank=True, null=True)  # fir-2, etc.
    
    # Workers needed
    workers_required = models.IntegerField(default=0)
    
    # Job Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    all_day = models.BooleanField(default=False)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='jobs_created')

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.title} - {self.farmer_name} ({self.start_date.date()})"

    @property
    def total_assigned_workers(self):
        """Count total workers assigned across all assignments"""
        return sum(assignment.workers_count for assignment in self.assignments.all())

    @property
    def is_fully_assigned(self):
        """Check if required workers are assigned"""
        return self.total_assigned_workers >= self.workers_required


class JobAssignment(models.Model):
    """
    Assignment of Mukkadam and team members to a Job
    """
    ASSIGNMENT_STATUS = [
        ('assigned', 'Assigned'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Relations
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='assignments')
    mukkadam = models.ForeignKey('Mukkadam', on_delete=models.CASCADE, related_name='job_assignments')
    
    # Assignment Details
    workers_count = models.IntegerField(default=0, help_text="Number of workers assigned")
    team_members = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of team member names/IDs from mukkadam's team"
    )
    
    # Assignment Status
    status = models.CharField(max_length=20, choices=ASSIGNMENT_STATUS, default='assigned')
    
    # Payment & Rates
    agreed_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Agreed payment rate for this assignment"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('partial', 'Partial'),
            ('completed', 'Completed'),
        ],
        default='pending'
    )
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    # Tracking
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assignments_made')
    confirmed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-assigned_at']
        unique_together = ['job', 'mukkadam']  # One mukkadam per job

    def __str__(self):
        return f"{self.mukkadam.mukkadam_name} assigned to {self.job.title}"

    def save(self, *args, **kwargs):
        # Update job status when assignment is made
        if self.pk is None:  # New assignment
            if self.job.status == 'pending':
                self.job.status = 'assigned'
                self.job.save()
        super().save(*args, **kwargs)


class AssignmentLog(models.Model):
    """
    Track changes to assignments for audit trail
    """
    assignment = models.ForeignKey(JobAssignment, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)  # 'created', 'updated', 'status_changed', 'cancelled'
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.assignment} - {self.timestamp}"