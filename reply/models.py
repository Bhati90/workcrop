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

    class Meta:
        ordering = ['-last_message_at']

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

    def __str__(self):
        return f"{self.direction} - {self.message_type} - {self.timestamp}"


class MediaFile(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='media_file')
    file = models.FileField(upload_to='whatsapp_media/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(null=True, blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

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


class WebhookLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Webhook Log - {self.timestamp}"