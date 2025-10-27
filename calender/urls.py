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
router.register(r'products-readonly', views.ProductReadOnlyViewSet, basename='product-readonly')

urlpatterns = [
    path('api/', include(router.urls)),
    path('edit',views.edit, name='edit'),
    path('', views.crop_management_dashboard, name='dashboard'),
    # path('api/varieties/', views.get_varieties_by_crop, name='get_varieties'),
    path('api/get-varieties/', views.get_varieties_by_crop, name='get_varieties'),
    path('api/get-activities/', views.get_activities_by_variety, name='get_activities'),
    path('api/get-products/', views.get_products_by_filters, name='get_products'),

]
