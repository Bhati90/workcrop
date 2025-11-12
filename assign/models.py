from django.db import models
from django.contrib.auth.models import User
import uuid

class Farmer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    village = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

class Activity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    days_after_pruning = models.IntegerField(default=0)

class Mukadam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    location = models.CharField(max_length=100)
    number_of_labourers = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MukadamActivityRate(models.Model):
    """Track what activities each mukadam can do and their rates"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mukadam = models.ForeignKey(Mukadam, on_delete=models.CASCADE, related_name='activity_rates')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    rate_per_acre = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['mukadam', 'activity']
        ordering = ['activity__name']
    
    def __str__(self):
        return f"{self.mukadam.name} - {self.activity.name} - ₹{self.rate_per_acre}/acre"





class Job(models.Model):
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('assigned', 'Assigned to Mukadams'),
        ('bidding', 'Receiving Bids'),
        ('finalized', 'Mukadam Finalized'),
        ('in_progress', 'Work in Progress'),
        ('priced', 'Priced'),      # New status
        ('notified', 'Notified'),  # New status  
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),

    ]
    assigned_mukadam = models.ForeignKey(Mukadam, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs')
    assigned_at = models.DateTimeField(null=True, blank=True)
    your_price_per_acre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    
    # Job Details
    farm_size_acres = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=200)
    requested_date = models.DateField()
    requested_time = models.TimeField()
    farmer_price_per_acre = models.DecimalField(max_digits=10, decimal_places=2)
    workers_needed = models.IntegerField(default=5, help_text="Number of workers required for this job")  # ✅ ADD this
    
    # Status & Assignment
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    finalized_mukadam = models.ForeignKey(Mukadam, null=True, blank=True, on_delete=models.SET_NULL)
    finalized_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Timestamps
    confirmed_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-confirmed_at']


# In models.py - UPDATE MukadamInterest model
class MukadamInterest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='interests')
    mukadam = models.ForeignKey(Mukadam, on_delete=models.CASCADE)
    is_interested = models.BooleanField(default=False)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True) 

    # ✅ ADD this field
    RESPONSE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('interested', 'Interested'), 
        ('declined', 'Declined'),
        ('assigned', 'Assigned'),
    ]
    response_status = models.CharField(
        max_length=20, 
        choices=RESPONSE_STATUS_CHOICES, 
        default='pending'
    )
    
    class Meta:
        unique_together = ['job', 'mukadam']
        
    def save(self, *args, **kwargs):
        # ✅ Auto-update response_status based on is_interested
        if self.responded_at and self.response_status == 'pending':
            self.response_status = 'interested' if self.is_interested else 'declined'
        super().save(*args, **kwargs)


class JobAssignment(models.Model):
    """Track which mukadams were assigned to bid on a job"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='assignments')
    mukadam = models.ForeignKey(Mukadam, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

# Update your MukadamBid model in models.py:
class MukadamBid(models.Model):
    PENDING = 'pending'
    INTERESTED = 'interested' 
    DECLINED = 'declined'
    SELECTED = 'selected'      # ✅ Add this
    REJECTED = 'rejected'      # ✅ Add this too for rejected bids
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (INTERESTED, 'Interested'),
        (DECLINED, 'Declined'), 
        (SELECTED, 'Selected'),     # ✅ Add this
        (REJECTED, 'Rejected'),     # ✅ Add this
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='bids')
    mukadam = models.ForeignKey(Mukadam, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    bid_price_per_acre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_price_per_acre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # ✅ Add if missing
    estimated_duration_hours = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['job', 'mukadam']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.mukadam.name} - {self.job.farmer.name} ({self.status})"

# models.py
class JobStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # ✅ Allow null
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WhatsAppNotification(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='whatsapp_notifications')
    recipient_type = models.CharField(max_length=20)  # 'farmer', 'mukadam'
    recipient_phone = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)