

from django.db import models
from django.contrib import admin

from django.utils import timezone
class ChatContact(models.Model):
    """ Represents a single WhatsApp user you are communicating with. """
    wa_id = models.CharField(max_length=50, unique=True, help_text="The user's WhatsApp ID (their phone number).")
    name = models.CharField(max_length=100, blank=True, null=True, help_text="The user's WhatsApp profile name.")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # CHANGED: Use default instead of auto_now. auto_now updates every time you save the model.
    # This should only be updated when a new message comes in.
    last_contact_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name or self.wa_id


   
class Message(models.Model):
    """ Represents a single message, either incoming or outgoing. """
    
    class MessageDirection(models.TextChoices):
        INBOUND = 'inbound', 'Inbound'
        OUTBOUND = 'outbound', 'Outbound'

    class MessageType(models.TextChoices):
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'
        DOCUMENT = 'document', 'Document'
        STICKER = 'sticker', 'Sticker'
        CONTACT = 'contact', 'Contact' # Added for clarity
        REACTION = 'reaction', 'Reaction'
        UNKNOWN = 'unknown', 'Unknown'
        
    class MessageStatus(models.TextChoices):
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        READ = 'read', 'Read'
        FAILED = 'failed', 'Failed'
    
    contact = models.ForeignKey(ChatContact, on_delete=models.CASCADE, related_name='messages')
    wamid = models.CharField(max_length=255, unique=True, help_text="The unique WhatsApp Message ID from Meta.")
    direction = models.CharField(max_length=10, choices=MessageDirection.choices)
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.UNKNOWN)
    is_view_once = models.BooleanField(
    default=False,
    help_text="True if this message is a one-time view media."
    )

    # --- Content fields ---
    text_content = models.TextField(blank=True, null=True, help_text="Content for text messages or placeholders for media.")
    caption = models.TextField(blank=True, null=True, help_text="Caption for media messages.")
    media_file = models.FileField(upload_to='whatsapp_media/', blank=True, null=True,max_length=500, help_text="Locally saved media file.")
    
    # --- New field to handle replies ---
    replied_to = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='replies',
        help_text="The message this message is a reply to."
    )

    reaction = models.CharField(
    max_length=50,
    blank=True,
    null=True,
    help_text="Reaction emoji (e.g. 👍, ❤️)."
   )
    delivery_status = models.CharField(max_length=50, null=True, blank=True, help_text="e.g., sent, delivered, read")
    source_node_id = models.CharField(max_length=255, null=True, blank=True, help_text="The ID of the flow node that sent this message.")
    
    
    timestamp = models.DateTimeField(help_text="Timestamp from the WhatsApp message.")
    media_id = models.CharField(max_length=255, blank=True, null=True)
    # CHANGED: Increased max_length to store reactions like "Reacted with 👍"
    status = models.CharField(max_length=50, choices=MessageStatus.choices, blank=True, null=True)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)
    
    raw_data = models.JSONField(help_text="The raw, complete webhook payload from Meta for debugging.",null=True, 
        blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.direction.capitalize()} message {self.id} to/from {self.contact.wa_id}"
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
class WhatsAppCall(models.Model):
    """Logs every inbound and outbound WhatsApp call."""
    CALL_DIRECTIONS = (('inbound', 'Inbound'), ('outbound', 'Outbound'))
    
    call_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="The unique ID from Meta for this call")
    contact = models.ForeignKey(ChatContact, on_delete=models.SET_NULL, null=True, related_name="calls")
    direction = models.CharField(max_length=10, choices=CALL_DIRECTIONS)
    status = models.CharField(max_length=20, default='initiated', help_text="e.g., ringing, answered, ended, missed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the call was ended or missed")

    def __str__(self):
        return f"{self.direction.capitalize()} call with {self.contact.wa_id} - {self.status}"

class Flows(models.Model):
    """Stores the JSON definition of a flow created in React Flow."""
    name = models.CharField(max_length=255, unique=True, default="Untitled Flow")
    is_active = models.BooleanField(default=True, help_text="Indicates if the flow is currently active and can be triggered.")

    template_name = models.CharField(max_length=250, unique=False, help_text="The template that triggers this flow. Other templates can be used inside.")
    flow_data = models.JSONField(help_text="The entire JSON object from React Flow (nodes and edges).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Flows"
        ordering = ['-updated_at']

    def __str__(self):
        return f"Flow '{self.name}' (Active: {self.is_active})"

class Attribute(models.Model):
    """Represents a custom field, e.g., 'city', 'email', 'order_value'."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
 
class UserFlowSessions(models.Model):
    """Tracks the current position of a contact within a flow."""
    contact = models.OneToOneField(ChatContact, on_delete=models.CASCADE, primary_key=True)
    flow = models.ForeignKey(Flows, on_delete=models.CASCADE)
    current_node_id = models.CharField(max_length=255, help_text="The ID of the user's current node in the flow.")
    updated_at = models.DateTimeField(auto_now=True)

    waiting_for_attribute = models.ForeignKey(
        'Attribute', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    # For waiting for a location reply
    is_waiting_for_location = models.BooleanField(default=False)
    longitude_attribute = models.ForeignKey(
        'Attribute', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='longitude_sessions'
    )
    latitude_attribute = models.ForeignKey(
        'Attribute', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='latitude_sessions'
    )

    # For waiting for an image reply
    waiting_for_image_attribute = models.ForeignKey(
        'Attribute', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='image_sessions'
    )
    waiting_for_flow_completion = models.BooleanField(default=False)
    flow_form_id = models.CharField(max_length=255, null=True, blank=True)
    
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name_plural = "User Flow Sessions"

    def __str__(self):
        return f"{self.contact.wa_id} is at {self.current_node_id} in {self.flow.name}"

class WhatsAppFlowForm(models.Model):
    """
    Model to store WhatsApp Flow Forms created via the form builder.
    """
    name = models.CharField(max_length=255, unique=True)
    meta_flow_id = models.CharField(max_length=255, null=True, blank=True)  # Meta's Flow ID
    template_category = models.CharField(max_length=50, default='UTILITY')
    template_body = models.TextField()
    template_button_text = models.CharField(max_length=20, default='Open Form')
    screens_data = models.JSONField()  # Store the screen configuration
    
    # Meta API response data
    flow_status = models.CharField(max_length=50, null=True, blank=True)
    template_name = models.CharField(max_length=255, null=True, blank=True)
    template_status = models.CharField(max_length=50, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "WhatsApp Flow Form"
        verbose_name_plural = "WhatsApp Flow Forms"


class ContactAttributeValue(models.Model):
    """Stores the actual value of an attribute for a specific contact."""
    contact = models.ForeignKey(ChatContact, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='contact_values')
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('contact', 'attribute')

    def __str__(self):
        return f"{self.contact.wa_id} -> {self.attribute.name}: {self.value}" # Optional: Add security
    
class Flowss(models.Model):
    """Stores the JSON definition of a flow created in React Flow."""
    template_name = models.CharField(max_length=250, unique=False, help_text="The template that triggers this flow. Other templates can be used inside.")
    flow_data = models.JSONField(help_text="The entire JSON object from React Flow (nodes and edges).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Flow for template: {self.template_name}"

class UserFlowSessionss(models.Model):
    """Tracks the current position of a contact within a flow."""
    contact = models.OneToOneField(ChatContact, on_delete=models.CASCADE, primary_key=True)
    flow = models.ForeignKey(Flowss, on_delete=models.CASCADE)
    current_node_id = models.CharField(max_length=255, help_text="The ID of the user's current node in the flow.")
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"{self.contact.wa_id} is at {self.current_node_id} in {self.flow.template_name}"

