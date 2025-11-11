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
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    
    # Job Details
    farm_size_acres = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=200)
    requested_date = models.DateField()
    requested_time = models.TimeField()
    farmer_price_per_acre = models.DecimalField(max_digits=10, decimal_places=2)
    
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

class JobAssignment(models.Model):
    """Track which mukadams were assigned to bid on a job"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='assignments')
    mukadam = models.ForeignKey(Mukadam, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

class MukadamBid(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Response'),
        ('interested', 'Interested - Price Submitted'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled by Mukadam'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='bids')
    mukadam = models.ForeignKey(Mukadam, on_delete=models.CASCADE)
    
    # Bid Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    bid_price_per_acre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_duration_hours = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['job', 'mukadam']
        ordering = ['bid_price_per_acre']

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