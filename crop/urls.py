from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from core.views import MukkadamViewSet

# Setup Router
router = DefaultRouter()
router.register(r'mukkadam', MukkadamViewSet, basename='mukkadam')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Endpoints
    path('api/', include(router.urls)),
    
    # Login Endpoint (returns Token)
    path('api/login/', obtain_auth_token, name='api_token_auth'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)