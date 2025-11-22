from django.urls import path
from . import views
from .views import auto_analyze_farmers_view, get_segment_details_view, get_segment_farmers_view, get_calendar_view, check_existing_templates_view

urlpatterns = [
    # Converts English to SQL
     path('generate-query/', views.generate_query_view, name='generate-query'),
    path('auto-analyze-farmers/', auto_analyze_farmers_view,name='auto_analyze_farmers'),
    path('segment-details/', get_segment_details_view,name='segment_details'),
    path('template-check/', check_existing_templates_view, name='template_check'),

    # Executes the generated SQL
    path('segment-farmers/', get_segment_farmers_view, name='segment_farmers'),
    path('calendar/', get_calendar_view, name='calendar_view'),
    path('refresh-cache/', views.refresh_analysis_cache_view, name='refresh_cache'),
path('cache-status/', views.get_cache_status_view, name='cache_status'),
    path('execute-query/', views.execute_query_view, name='execute-query'),
]

