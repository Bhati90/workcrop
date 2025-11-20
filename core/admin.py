from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Mukkadam, ActivityLog

class ActivityLogInline(admin.TabularInline):
    model = ActivityLog
    readonly_fields = ('user', 'action_type', 'details', 'timestamp')
    extra = 0
    can_delete = False

@admin.register(Mukkadam)
class MukkadamAdmin(admin.ModelAdmin):
    list_display = ('mukkadam_name', 'village', 'mobile_numbers', 'created_by')
    # This adds the history table inside the Mukkadam's page
    inlines = [ActivityLogInline] 

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action_type', 'mukkadam', 'details')
    list_filter = ('action_type', 'user', 'timestamp')