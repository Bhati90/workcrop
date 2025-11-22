from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import MukkadamViewSet, JobViewSet, JobAssignmentViewSet

router = DefaultRouter()
router.register(r'mukkadam', MukkadamViewSet, basename='mukkadam')
router.register(r'mukkadams', MukkadamViewSet, basename='mukkadams')
router.register(r'jobs', JobViewSet, basename='jobs')
router.register(r'assignments', JobAssignmentViewSet, basename='assignments')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', obtain_auth_token),

    # 🔥 Custom assign endpoint — FIXED
    path(
        'api/jobs/<int:job_id>/assign/',
        JobAssignmentViewSet.as_view({'post': 'create'}),
        name='job-assign'
    ),
]
