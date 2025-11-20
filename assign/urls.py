from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'jobs', views.JobViewSet)
router.register(r'crops', views.CropViewSet, basename='crop')  # ✅ ADD
router.register(r'crop-varieties', views.CropVarietyViewSet, basename='cropvariety') 
router.register(r'bids', views.MukadamBidViewSet)
router.register(r'mukadams', views.MukadamViewSet)
router.register(r'mukadamprofile', views.MukadamProfileViewSet, basename='mukadamprofile')
router.register(r'whatsapp', views.WhatsAppNotificationViewSet)
router.register(r'activities', views.ActivityViewSet)
router.register(r'mukadam-activity-rates', views.MukadamActivityRateViewSet)
router.register(r'mukadam-jobs', views.MukadamJobViewSet, basename='mukadam-jobs')  # ADD this
router.register(r'farmers', views.FarmerViewSet, basename='farmer')


urlpatterns = [
    path('', include(router.urls)),
    path('job/confirm_and_price/', views.confirm_job_and_set_price, name='confirm_job_and_price'),  # ADD

    # path('api/bids/submit_bid/', views.submit_bid, name='submit_bid'),

    # Additional custom endpoints can be added here
]
