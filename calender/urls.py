from django.urls import path
from . import views



urlpatterns = [
    path('', views.crop_management_dashboard, name='dashboard'),
    path('api/varieties/', views.get_varieties_by_crop, name='get_varieties'),
]
