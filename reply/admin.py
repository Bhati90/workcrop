from django.contrib import admin

from django.contrib import admin
from .models import WhatsAppUser, Conversation, Message, MediaFile, WhatsAppTemplate, WebhookLog


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
