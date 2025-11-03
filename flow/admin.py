
from django.contrib import admin
from .models import WhatsAppFlowForm

@admin.register(WhatsAppFlowForm)
class WhatsAppFlowFormAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_category', 'flow_status', 'template_status', 'created_at', 'updated_at')
    list_filter = ('template_category', 'flow_status', 'template_status', 'created_at')
    search_fields = ('name', 'template_body', 'meta_flow_id')
    readonly_fields = ('meta_flow_id', 'flow_status', 'template_name', 'template_status', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_category', 'template_body', 'template_button_text')
        }),
        ('Form Configuration', {
            'fields': ('screens_data',),
            'classes': ('wide',)
        }),
        ('Meta API Status', {
            'fields': ('meta_flow_id', 'flow_status', 'template_name', 'template_status'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        # Make screens_data readonly for existing objects to prevent corruption
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly.append('screens_data')
        return readonly
    
    def has_delete_permission(self, request, obj=None):
        # Only allow deletion if the form hasn't been submitted to Meta
        if obj and obj.meta_flow_id:
            return False
        return super().has_delete_permission(request, obj)

# Register your models here.
