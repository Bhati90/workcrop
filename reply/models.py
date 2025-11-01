from django.db import models

from django.db import models
from django.utils import timezone


class WhatsAppUser(models.Model):
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    profile_picture = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    is_blocked = models.BooleanField(default=False)
    blocked_until = models.DateTimeField(null=True, blank=True, default=None)
    class Meta:
        ordering = ['-last_message_at']
        db_table = 'whatsapp_whatsappuser'

    def __str__(self):
        return f"{self.name} ({self.phone_number})"
    

class Conversation(models.Model):
    whatsapp_user = models.OneToOneField(WhatsAppUser, on_delete=models.CASCADE, related_name='conversation')
    unread_count = models.IntegerField(default=0)
    last_message_preview = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        db_table = 'whatsapp_conversation'

    def __str__(self):
        return f"Conversation with {self.whatsapp_user.name}"
    

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('template', 'Template'),
    ]

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    whatsapp_message_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    
    text_content = models.TextField(blank=True, null=True)
    media_url = models.URLField(blank=True, null=True)
    media_id = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    
    template_name = models.CharField(max_length=255, blank=True, null=True)
    template_language = models.CharField(max_length=10, blank=True, null=True)
    template_params = models.JSONField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['timestamp']
        db_table = 'whatsapp_message'

    def __str__(self):
        return f"{self.direction} - {self.message_type} - {self.timestamp}"


class MediaFile(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='media_file')
    file = models.FileField(upload_to='whatsapp_media/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(null=True, blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_mediafile'
    def __str__(self):
        return f"Media for message {self.message.id}"


class WhatsAppTemplate(models.Model):
    STATUS_CHOICES = [
        ('approved', 'Approved'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    ]

    CATEGORY_CHOICES = [
        ('marketing', 'Marketing'),
        ('utility', 'Utility'),
        ('authentication', 'Authentication'),
    ]

    name = models.CharField(max_length=255, unique=True)
    language = models.CharField(max_length=10, default='en')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    header_type = models.CharField(max_length=20, blank=True, null=True)
    header_text = models.TextField(blank=True, null=True)
    body_text = models.TextField()
    footer_text = models.TextField(blank=True, null=True)
    
    buttons = models.JSONField(blank=True, null=True)
    header_params_count = models.IntegerField(default=0)
    body_params_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.language})"
    class Meta:
        db_table = 'whatsapp_whatsapptemplate'


class WebhookLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        db_table = 'whatsapp_webhooklog'

    def __str__(self):
        return f"Webhook Log - {self.timestamp}"
    


# Add to models.py

class ServiceInquiry(models.Model):
    """
    Universal inquiry tracker - handles ANY service in ANY language
    Even services we don't offer yet!
    """
    
    STATUS_CHOICES = [
        ('new', 'New Inquiry'),
        ('reviewing', 'Under Review'),
        ('serviceable', 'We Can Provide'),
        ('not_serviceable', 'Currently Not Available'),
        ('quoted', 'Price Quoted'),
        ('converted', 'Booking Confirmed'),
        ('lost', 'Customer Not Interested'),
    ]
    
    URGENCY_CHOICES = [
        ('low', 'Normal'),
        ('medium', 'Interested'),
        ('high', 'Urgent'),
        ('critical', 'Emergency'),
    ]
    
    # User Info
    whatsapp_user = models.ForeignKey(WhatsAppUser, on_delete=models.CASCADE, related_name='service_inquiries')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='service_inquiries')
    
    # Customer Details (as they told in chat - ANY language)
    customer_name_in_chat = models.CharField(max_length=255, blank=True, null=True, 
                                             help_text="Name they mentioned (कृष्णा, Kishan, etc.)")
    
    # Service Details - FLEXIBLE to handle unknown services
    service_type = models.CharField(max_length=200, 
                                   help_text="Labor/Spray/Equipment/Transport/Storage/Processing/ANY")
    service_description = models.TextField(
        help_text="Full description of what they asked for in their language"
    )
    service_language = models.CharField(max_length=20, default='mixed',
                                       choices=[
                                           ('english', 'English'),
                                           ('hindi', 'Hindi'),
                                           ('marathi', 'Marathi'),
                                           ('hinglish', 'Hinglish'),
                                           ('mixed', 'Mixed Languages'),
                                       ])
    
    # Specific Details (extracted from conversation)
    quantity_needed = models.CharField(max_length=100, blank=True, null=True,
                                      help_text="35 workers, 50 tons, 10 acres, etc.")
    
    # Location - FLEXIBLE for any area
    location_mentioned = models.TextField(blank=True, null=True,
                                         help_text="Satara, Mumbai, Pune, Village name, ANY location")
    is_serviceable_area = models.BooleanField(default=None, null=True,
                                              help_text="True if we operate here, False if not")
    
    # Farm Details
    farm_size = models.CharField(max_length=100, blank=True, null=True,
                                help_text="35 acre, 2 हेक्टर, etc.")
    crop_type = models.CharField(max_length=100, blank=True, null=True,
                                help_text="द्राक्ष, Grapes, Pomegranate, etc.")
    crop_variety = models.CharField(max_length=100, blank=True, null=True,
                                   help_text="ARD 35, Thompson, etc.")
    
    # Timing
    requested_date = models.CharField(max_length=100, blank=True, null=True,
                                     help_text="5 Dec, आज, कल, next week")
    duration = models.CharField(max_length=100, blank=True, null=True,
                               help_text="5 days, 1 week, 2 महिने")
    
    # Status & Priority
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='new')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    
    # Pricing
    requested_price_info = models.BooleanField(default=False)
    quoted_price = models.CharField(max_length=200, blank=True, null=True,
                                   help_text="Price or 'Will contact within 24hrs'")
    
    # Tracking
    original_query = models.TextField(help_text="Exact message from user")
    ai_response = models.TextField(blank=True, null=True, help_text="What bot replied")
    
    needs_human_review = models.BooleanField(default=False,
                                            help_text="True if unknown service/area")
    admin_notes = models.TextField(blank=True, null=True)
    
    # Conversion Tracking
    converted_to_booking = models.BooleanField(default=False)
    conversion_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    followup_scheduled = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'whatsapp_serviceinquiry'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'urgency']),
            models.Index(fields=['service_type']),
            models.Index(fields=['needs_human_review']),
        ]
    
    def __str__(self):
        return f"{self.whatsapp_user.name} - {self.service_type} ({self.status})"


class ChatSession(models.Model):
    """
    Track individual chat sessions for better analytics
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='sessions')
    
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(null=True, blank=True)
    
    # Session Metrics
    messages_exchanged = models.IntegerField(default=0)
    primary_language = models.CharField(max_length=20, default='mixed')
    
    # Intent Detection
    had_inquiry = models.BooleanField(default=False)
    inquiry_types = models.JSONField(default=list,
                                    help_text="['labor', 'spray', 'price', etc.]")
    
    # Outcome
    session_outcome = models.CharField(max_length=50, default='ongoing',
                                      choices=[
                                          ('ongoing', 'Still Active'),
                                          ('completed', 'Query Resolved'),
                                          ('escalated', 'Sent to Team'),
                                          ('abandoned', 'User Left'),
                                      ])
    
    # User left or responded?
    last_user_message_at = models.DateTimeField(null=True, blank=True)
    response_time_avg_seconds = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'whatsapp_chatsession'
        ordering = ['-session_start']


class UnknownQuery(models.Model):
    """
    Special table to capture queries we don't understand or can't serve
    For future service expansion planning
    """
    whatsapp_user = models.ForeignKey(WhatsAppUser, on_delete=models.CASCADE, related_name='unknown_queries')
    
    query_text = models.TextField()
    query_language = models.CharField(max_length=20)
    
    # AI couldn't classify or we don't offer this
    reason = models.CharField(max_length=100, choices=[
        ('unknown_service', 'Unknown Service Type'),
        ('unknown_area', 'Area Not Covered'),
        ('unclear_request', 'Could Not Understand'),
        ('language_issue', 'Translation Problem'),
    ])
    
    # For future expansion
    potential_service = models.CharField(max_length=200, blank=True, null=True,
                                        help_text="What service they might be asking for")
    
    reviewed_by_admin = models.BooleanField(default=False)
    admin_interpretation = models.TextField(blank=True, null=True)
    
    # Frequency tracking
    similar_queries_count = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_unknownquery'
        ordering = ['-created_at']