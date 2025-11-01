from django.contrib import admin

from django.contrib import admin
from .models import WhatsAppUser, Conversation, Message, MediaFile, WhatsAppTemplate, WebhookLog
from .models import ServiceInquiry, UnknownQuery, ChatSession

@admin.register(ServiceInquiry)
class ServiceInquiryAdmin(admin.ModelAdmin):
    list_display = ['customer_name_display', 'service_type', 'urgency', 'status', 'location_mentioned', 'created_at']
    list_filter = ['status', 'urgency', 'service_language', 'needs_human_review', 'requested_price_info']
    search_fields = ['customer_name_in_chat', 'service_description', 'location_mentioned', 'original_query']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Customer Info', {
            'fields': ('whatsapp_user', 'customer_name_in_chat', 'conversation')
        }),
        ('Service Details', {
            'fields': ('service_type', 'service_description', 'service_language', 'quantity_needed')
        }),
        ('Location & Farm', {
            'fields': ('location_mentioned', 'is_serviceable_area', 'farm_size', 'crop_type', 'crop_variety')
        }),
        ('Timing', {
            'fields': ('requested_date', 'duration', 'urgency')
        }),
        ('Status & Pricing', {
            'fields': ('status', 'requested_price_info', 'quoted_price')
        }),
        ('Tracking', {
            'fields': ('original_query', 'ai_response', 'needs_human_review', 'admin_notes', 'converted_to_booking')
        }),
    )
    
    def customer_name_display(self, obj):
        return obj.customer_name_in_chat or obj.whatsapp_user.name
    customer_name_display.short_description = 'Customer'

@admin.register(UnknownQuery)
class UnknownQueryAdmin(admin.ModelAdmin):
    list_display = ['whatsapp_user', 'reason', 'query_language', 'similar_queries_count', 'reviewed_by_admin', 'created_at']
    list_filter = ['reason', 'query_language', 'reviewed_by_admin']
    search_fields = ['query_text', 'admin_interpretation']

@admin.register(WhatsAppUser)
class WhatsAppUserAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'last_message_at', 'created_at')
    search_fields = ('name', 'phone_number')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('whatsapp_user', 'unread_count', 'updated_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'message_type', 'direction', 'status', 'timestamp')
    list_filter = ('message_type', 'direction', 'status')


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ('message', 'file_name', 'file_size')


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'language', 'category', 'status')


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'processed')
