from rest_framework import viewsets, parsers, status, permissions
from rest_framework.response import Response
from .models import Mukkadam,ActivityLog
from .serializers import MukkadamFullSerializer, MukkadamListSerializer,MukkadamDropdownSerializer
from rest_framework.decorators import action
import json

class MukkadamViewSet(viewsets.ModelViewSet):
    queryset = Mukkadam.objects.all().order_by('-updated_at')
    permission_classes = [permissions.IsAuthenticated]
    
    # Essential for handling Files + JSON data together
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get_serializer_class(self):
        # Use ListSerializer for list view, Full for everything else
        if self.action == 'list':
            return MukkadamListSerializer
        return MukkadamFullSerializer

    def create(self, request, *args, **kwargs):
        return self.save_mukkadam(request, is_update=False)

    def update(self, request, *args, **kwargs):
        return self.save_mukkadam(request, is_update=True)

    def save_mukkadam(self, request, is_update=False):
        try:
            data_str = request.data.get('data')
            if not data_str:
                return Response({"error": "No 'data' field provided"}, status=400)

            data = json.loads(data_str)

            # Handle Files
            file_fields = ['profile_photo', 'aadhar_card', 'pan_card', 'bank_proof']
            for field in file_fields:
                if field in request.FILES:
                    data[field] = request.FILES[field]

            if is_update:
                instance = self.get_object()
                serializer = MukkadamFullSerializer(instance, data=data, partial=True)
            else:
                serializer = MukkadamFullSerializer(data=data)

            if serializer.is_valid():
                if is_update:
                    mukkadam = serializer.save()
                    
                    # --- TRACKING LOGIC STARTS HERE ---
                    # Check if availability specifically was changed
                    if 'team_availabilities' in data:
                        ActivityLog.objects.create(
                            mukkadam=mukkadam,
                            user=request.user,
                            action_type="Availability Update",
                            details=f"Updated availability slots. Total slots: {len(data['team_availabilities'])}"
                        )
                    else:
                        # Generic Profile Update
                        ActivityLog.objects.create(
                            mukkadam=mukkadam,
                            user=request.user,
                            action_type="Profile Update",
                            details="Updated general profile details"
                        )
                    # --- TRACKING LOGIC ENDS HERE ---
                    
                else:
                    # New Registration
                    mukkadam = serializer.save(created_by=request.user)
                    ActivityLog.objects.create(
                        mukkadam=mukkadam,
                        user=request.user,
                        action_type="Registration",
                        details="Created new Mukkadam profile"
                    )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED if not is_update else status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

    @action(detail=False, methods=['get'])
    def dropdown_list(self, request):
        mukkadams = Mukkadam.objects.all().only('id', 'mukkadam_name', 'mobile_numbers', 'village')
        serializer = MukkadamDropdownSerializer(mukkadams, many=True)
        return Response(serializer.data)
    

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum
from django_filters.rest_framework import DjangoFilterBackend

from .models import Job, JobAssignment, Mukkadam, AssignmentLog
from .serializers import (
    JobSerializer, 
    JobListSerializer,
    JobAssignmentSerializer,
    MukkadamBasicSerializer,
    AssignmentLogSerializer
)


class JobViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing jobs
    """
    permission_classes = [IsAuthenticated]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'village', 'taluka', 'district', 'start_date']
    search_fields = ['title', 'farmer_name', 'village', 'plot_name']
    ordering_fields = ['start_date', 'created_at', 'workers_required']
    ordering = ['-start_date']

    def get_queryset(self):
        queryset = Job.objects.all().prefetch_related('assignments__mukkadam')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date_from')
        end_date = self.request.query_params.get('start_date_to')
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_date__lte=end_date)
        
        # Filter by assignment status
        assignment_status = self.request.query_params.get('assignment_status')
        if assignment_status == 'unassigned':
            queryset = queryset.filter(assignments__isnull=True)
        elif assignment_status == 'partially_assigned':
            queryset = queryset.annotate(
                assigned_count=Count('assignments')
            ).filter(assigned_count__gt=0, is_fully_assigned=False)
        elif assignment_status == 'fully_assigned':
            queryset = queryset.filter(is_fully_assigned=True)
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return JobListSerializer
        return JobSerializer

    @action(detail=True, methods=['post'])
    def assign_mukkadam(self, request, pk=None):
        """
        Assign a mukkadam to a job
        POST /api/jobs/{id}/assign_mukkadam/
        Body: {
            "mukkadam_id": 1,
            "workers_count": 10,
            "team_members": ["name1", "name2"],
            "agreed_rate": 500,
            "notes": "..."
        }
        """
        job = self.get_object()
        
        serializer = JobAssignmentSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save(job=job)
            
            # Refresh job data
            job.refresh_from_db()
            job_serializer = JobSerializer(job)
            
            return Response({
                'message': 'Mukkadam assigned successfully',
                'job': job_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def available_mukkadams(self, request, pk=None):
        """
        Get available mukkadams for this job based on:
        - Location proximity
        - Crew size
        - Current availability
        """
        job = self.get_object()
        
        # Get mukkadams from same village/area or nearby
        queryset = Mukkadam.objects.all()
        
        # Filter by location if specified
        if job.village:
            queryset = queryset.filter(
                Q(village__icontains=job.village) |
                Q(preferred_work_locations__icontains=job.village)
            )
        
        # Exclude already assigned mukkadams
        assigned_mukkadam_ids = job.assignments.values_list('mukkadam_id', flat=True)
        queryset = queryset.exclude(id__in=assigned_mukkadam_ids)
        
        # Filter by crew size if workers required
        if job.workers_required:
            queryset = queryset.filter(
                crew_size__gte=job.workers_required
            )
        
        serializer = MukkadamBasicSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """
        Update job status
        PATCH /api/jobs/{id}/update_status/
        Body: {"status": "in_progress"}
        """
        job = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(Job.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        job.status = new_status
        job.save()
        
        serializer = JobSerializer(job)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """
        Get dashboard statistics
        GET /api/jobs/dashboard_stats/
        """
        total_jobs = Job.objects.count()
        pending_jobs = Job.objects.filter(status='pending').count()
        assigned_jobs = Job.objects.filter(status='assigned').count()
        in_progress_jobs = Job.objects.filter(status='in_progress').count()
        completed_jobs = Job.objects.filter(status='completed').count()
        
        total_workers_needed = Job.objects.filter(
            status__in=['pending', 'assigned']
        ).aggregate(Sum('workers_required'))['workers_required__sum'] or 0
        
        total_workers_assigned = JobAssignment.objects.aggregate(
            Sum('workers_count')
        )['workers_count__sum'] or 0
        
        return Response({
            'total_jobs': total_jobs,
            'pending_jobs': pending_jobs,
            'assigned_jobs': assigned_jobs,
            'in_progress_jobs': in_progress_jobs,
            'completed_jobs': completed_jobs,
            'total_workers_needed': total_workers_needed,
            'total_workers_assigned': total_workers_assigned,
        })


class JobAssignmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing job assignments
    """
    permission_classes = [IsAuthenticated]
    serializer_class = JobAssignmentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['job', 'mukkadam', 'status', 'payment_status']
    ordering_fields = ['assigned_at', 'workers_count']
    ordering = ['-assigned_at']
    def create(self, request, *args, **kwargs):
        job_id = kwargs.get('job_id')   # take job id from URL
        data = request.data.copy()
        data['job'] = job_id            # inject job into serializer

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(assigned_by=request.user)

        return Response(serializer.data, status=201)
    def get_queryset(self):
        return JobAssignment.objects.all().select_related('job', 'mukkadam', 'assigned_by')

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """
        Update assignment status
        PATCH /api/assignments/{id}/update_status/
        Body: {"status": "confirmed"}
        """
        assignment = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(JobAssignment.ASSIGNMENT_STATUS):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        assignment.status = new_status
        
        # Update timestamps based on status
        if new_status == 'confirmed':
            from django.utils import timezone
            assignment.confirmed_at = timezone.now()
        elif new_status == 'completed':
            from django.utils import timezone
            assignment.completed_at = timezone.now()
        
        assignment.save()
        
        serializer = JobAssignmentSerializer(assignment)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """
        Get assignment logs
        GET /api/assignments/{id}/logs/
        """
        assignment = self.get_object()
        logs = assignment.logs.all()
        serializer = AssignmentLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_mukkadam(self, request):
        """
        Get assignments grouped by mukkadam
        GET /api/assignments/by_mukkadam/?mukkadam_id=1
        """
        mukkadam_id = request.query_params.get('mukkadam_id')
        
        if not mukkadam_id:
            return Response(
                {'error': 'mukkadam_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        assignments = self.get_queryset().filter(mukkadam_id=mukkadam_id)
        serializer = JobAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)


class MukkadamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing mukkadams (for assignment purposes)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MukkadamBasicSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['mukkadam_name', 'village', 'mobile_numbers']
    ordering_fields = ['mukkadam_name', 'crew_size']
    ordering = ['mukkadam_name']

    def get_queryset(self):
        return Mukkadam.objects.all()

    @action(detail=True, methods=['get'])
    def assignments(self, request, pk=None):
        """
        Get all assignments for a mukkadam
        GET /api/mukkadams/{id}/assignments/
        """
        mukkadam = self.get_object()
        assignments = mukkadam.job_assignments.all().select_related('job')
        serializer = JobAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def availability_check(self, request, pk=None):
        """
        Check mukkadam availability for a specific date range
        GET /api/mukkadams/{id}/availability_check/?start_date=2025-11-20&end_date=2025-11-25
        """
        mukkadam = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date:
            return Response(
                {'error': 'start_date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get assignments in date range
        conflicting_assignments = JobAssignment.objects.filter(
            mukkadam=mukkadam,
            job__start_date__gte=start_date,
            status__in=['assigned', 'confirmed', 'in_progress']
        )
        
        if end_date:
            conflicting_assignments = conflicting_assignments.filter(
                job__start_date__lte=end_date
            )
        
        is_available = not conflicting_assignments.exists()
        
        return Response({
            'mukkadam_id': mukkadam.id,
            'mukkadam_name': mukkadam.mukkadam_name,
            'is_available': is_available,
            'conflicting_assignments': JobAssignmentSerializer(
                conflicting_assignments, many=True
            ).data if not is_available else []
        })