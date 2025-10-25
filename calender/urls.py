from django.urls import path
from . import views

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'crops', views.CropViewSet, basename='crop')
router.register(r'varieties', views.CropVarietyViewSet, basename='variety')
router.register(r'activities', views.ActivityViewSet, basename='activity')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'day-ranges', views.DayRangeViewSet, basename='dayrange')


urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.crop_management_dashboard, name='dashboard'),
    path('api/varieties/', views.get_varieties_by_crop, name='get_varieties'),
]
