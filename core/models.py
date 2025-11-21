from django.db import models
from django.contrib.auth.models import User
import uuid
import os

def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    # This puts everything inside "products/" folder in your S3 bucket
    return f"products/mukkadams/documents/{filename}"
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
    daily_work_timing = models.CharField(max_length=100, blank=True)
    
    # Stores: [{"teamNumber": "...", "startDate": "...", "endDate": "..."}]
    team_availabilities = models.JSONField(default=list, blank=True)

    # --- 4. Rate Card (Nested Object) ---
    # Stores: { "failFoot": "...", "secondFail": "...", ... }
    rate_card = models.JSONField(default=dict, blank=True)

    # --- 5. Work Area Preference ---
    home_location = models.CharField(max_length=255, blank=True)
    preferred_work_locations = models.TextField(blank=True)
    max_travel_distance = models.CharField(max_length=50, blank=True)

    # --- 6. Transport Details ---
    transport_mode = models.CharField(max_length=50) # own_bike, own_pickup, no_vehicle
    transport_arranged_by = models.CharField(max_length=50, blank=True)
    # Stores: { "bikeChargePerBike": "...", "currentlyStationedAt": "..." }
    transport_charges = models.JSONField(default=dict, blank=True)

    # --- 7. Payment Details ---
    # Stores: { "modes": {...}, "upiId": "...", "accountNumber": "..." }
    payment_details = models.JSONField(default=dict, blank=True)

    # --- 8. Work Mode ---
    work_mode = models.CharField(max_length=50) # daily_up_down, move_in, both
    move_in_preferred_region = models.CharField(max_length=255, blank=True)

    # --- 9. Referral ---
    
    referral_source = models.CharField(max_length=255, blank=True)
    referred_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='referrals_made' # This lets us see who they referred
    )
    
    # Keep the old text field just in case they were referred by an outsider
    referral_source_text = models.CharField(max_length=255, blank=True)

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