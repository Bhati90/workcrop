from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'jobs', views.JobViewSet)
router.register(r'bids', views.MukadamBidViewSet)
router.register(r'mukadams', views.MukadamViewSet)
router.register(r'whatsapp', views.WhatsAppNotificationViewSet)
router.register(r'activities', views.ActivityViewSet)
router.register(r'mukadam-activity-rates', views.MukadamActivityRateViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api/bids/submit_bid/', views.submit_bid, name='submit_bid'),

    # Additional custom endpoints can be added here
]
