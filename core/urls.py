from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import MukkadamViewSet

router = DefaultRouter()
router.register(r'mukkadam', MukkadamViewSet, basename='mukkadam')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/login/', obtain_auth_token), # Logic for login
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)