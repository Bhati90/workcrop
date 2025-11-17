from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta, datetime
from .models import *
from .serializers import *
import requests
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from .utils.fcm_helper import send_push_notification
from .serializers import SaveFCMTokenSerializer



import firebase_admin
from firebase_admin import credentials
import os

# # Initialize Firebase if not already done
# if not firebase_admin._apps:
#     try:
#         cred_path = 'firebase-service-account.json'
#         cred = credentials.Certificate(cred_path)
#         firebase_admin.initialize_app(cred)
#         print("✅ Firebase initialized in views.py")
#     except Exception as e:
#         print(f"❌ Firebase init failed: {e}")


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """API for activities (read-only for now)"""
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    pagination_class = None

class MukadamActivityRateViewSet(viewsets.ModelViewSet):
    """API for mukadam activity rates"""
    queryset = MukadamActivityRate.objects.all()
    serializer_class = MukadamActivityRateSerializer
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple activity rates at once"""
        rates_data = request.data.get('rates', [])
        
        created_rates = []
        for rate_data in rates_data:
            rate, created = MukadamActivityRate.objects.update_or_create(
                mukadam_id=rate_data['mukadam'],
                activity_id=rate_data['activity'],
                defaults={
                    'rate_per_acre': rate_data['rate_per_acre'],
                    'is_available': rate_data.get('is_available', True)
                }
            )
            created_rates.append(rate)
        
        return Response({
            "message": f"Created/updated {len(created_rates)} activity rates",
            "count": len(created_rates)
        })
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404


from .models import Farmer, FarmerPlot, FarmerEditHistory
from .serializers import FarmerSerializer, FarmerPlotSerializer, FarmerEditHistorySerializer


class FarmerViewSet(viewsets.ModelViewSet):
    queryset = Farmer.objects.all().prefetch_related('plots', 'job_set')
    serializer_class = FarmerSerializer
    
    def list(self, request, *args, **kwargs):
        """Enhanced list with plot auto-creation check"""
        # ✅ Auto-create missing plots for existing jobs
        self._sync_plots_from_jobs()
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Enhanced retrieve with plot sync"""
        # ✅ Auto-create missing plots for this farmer
        farmer = self.get_object()
        self._sync_farmer_plots(farmer)
        return super().retrieve(request, *args, **kwargs)
    
    def _sync_plots_from_jobs(self):
        """Create missing plots from jobs for all farmers"""
        jobs = Job.objects.select_related('farmer', 'activity').all()
        
        for job in jobs:
            if not job.farmer or not job.activity:
                continue
            
            # ✅ NEW: Check if plot already exists (using filter instead of get_or_create)
            existing_plot = FarmerPlot.objects.filter(
                farmer=job.farmer,
                activity_name=job.activity.name
            ).first()
            
            if existing_plot:
                # Update if this job has more acres
                if job.farm_size_acres > existing_plot.acres:
                    existing_plot.acres = job.farm_size_acres
                    existing_plot.location = job.location or existing_plot.location
                    existing_plot.save()
            else:
                # Create new plot
                FarmerPlot.objects.create(
                    farmer=job.farmer,
                    activity_name=job.activity.name,
                    acres=job.farm_size_acres,
                    location=job.location or job.farmer.village,
                    pruning_date=job.requested_date,
                    notes=f"Auto-synced from jobs"
                )
    def _sync_farmer_plots(self, farmer):
        """Create missing plots for specific farmer from their jobs"""
        jobs = Job.objects.filter(farmer=farmer).select_related('activity')
        
        for job in jobs:
            if not job.activity:
                continue
            
            # ✅ NEW: Check if plot already exists
            existing_plot = FarmerPlot.objects.filter(
                farmer=farmer,
                activity_name=job.activity.name
            ).first()
            
            if existing_plot:
                # Update if this job has more acres
                if job.farm_size_acres > existing_plot.acres:
                    existing_plot.acres = job.farm_size_acres
                    existing_plot.save()
            else:
                # Create new plot
                FarmerPlot.objects.create(
                    farmer=farmer,
                    activity_name=job.activity.name,
                    acres=job.farm_size_acres,
                    location=job.location or farmer.village,
                    pruning_date=job.requested_date,
                    notes=f"From job: {job.activity.name}"
                )
    
    @action(detail=True, methods=['get'])
    def edit_history(self, request, pk=None):
        """Get edit history including job-related changes"""
        farmer = self.get_object()
        
        # Get farmer edit history
        farmer_history = farmer.edit_history.all()
        
        # Get job history for this farmer
        jobs = Job.objects.filter(farmer=farmer).select_related('activity')
        job_history = []
        
        for job in jobs:
            job_history.append({
                'id': str(job.id),
                'field_changed': 'Job Created',
                'old_value': '',
                'new_value': f"{job.activity.name} - {job.farm_size_acres} acres",
                'changed_by': 'System',
                'changed_at': job.confirmed_at.isoformat() if job.confirmed_at else job.created_at.isoformat(),
                'reason': f'Job for {job.activity.name}'
            })
        
        # Combine both histories
        serializer = FarmerEditHistorySerializer(farmer_history, many=True)
        combined_history = list(serializer.data) + job_history
        
        # Sort by date
        combined_history.sort(key=lambda x: x['changed_at'], reverse=True)
        
        return Response(combined_history)
    
    @action(detail=True, methods=['post'])
    def sync_plots(self, request, pk=None):
        """Manually trigger plot sync from jobs"""
        farmer = self.get_object()
        self._sync_farmer_plots(farmer)
        
        return Response({
            'message': 'Plots synced successfully',
            'total_plots': farmer.plots.count(),
            'total_acres': farmer.total_acres
        })
    
    @action(detail=True, methods=['get', 'post'], url_path='plots')
    def plots(self, request, pk=None):
        """List or add plots for a farmer"""
        farmer = self.get_object()
        
        if request.method == 'GET':
            # Auto-sync plots from jobs
            self._sync_farmer_plots(farmer)
            
            plots = farmer.plots.all()
            serializer = FarmerPlotSerializer(plots, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Add new plot
            serializer = FarmerPlotSerializer(data=request.data)
            if serializer.is_valid():
                plot = serializer.save(farmer=farmer)
                
                # Log the creation
                changed_by = request.user.username if request.user.is_authenticated else 'System'
                FarmerEditHistory.objects.create(
                    farmer=farmer,
                    field_changed='Plot Added (Manual)',
                    old_value='',
                    new_value=f"{plot.acres} acres - {plot.activity_name or 'No activity'}",
                    changed_by=changed_by,
                    model_name='FarmerPlot',
                    object_id=plot.id
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch', 'delete'], url_path='plots/(?P<plot_id>[^/.]+)')
    def plot_detail(self, request, pk=None, plot_id=None):
        """Update or delete a specific plot"""
        farmer = self.get_object()
        
        try:
            plot = farmer.plots.get(id=plot_id)
        except FarmerPlot.DoesNotExist:
            return Response({'error': 'Plot not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'PATCH':
            old_data = {
                'acres': plot.acres,
                'location': plot.location,
                'activity_name': plot.activity_name,
                'pruning_date': plot.pruning_date
            }
            
            serializer = FarmerPlotSerializer(plot, data=request.data, partial=True)
            if serializer.is_valid():
                plot = serializer.save()
                
                # Log changes
                changed_by = request.user.username if request.user.is_authenticated else 'System'
                for field, new_value in request.data.items():
                    old_value = old_data.get(field)
                    if str(old_value) != str(new_value):
                        FarmerEditHistory.objects.create(
                            farmer=farmer,
                            field_changed=f"Plot {field.replace('_', ' ').title()}",
                            old_value=str(old_value),
                            new_value=str(new_value),
                            changed_by=changed_by,
                            model_name='FarmerPlot',
                            object_id=plot.id
                        )
                
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            changed_by = request.user.username if request.user.is_authenticated else 'System'
            
            # Log deletion
            FarmerEditHistory.objects.create(
                farmer=farmer,
                field_changed='Plot Deleted',
                old_value=f"{plot.acres} acres - {plot.activity_name or 'No activity'}",
                new_value='',
                changed_by=changed_by,
                model_name='FarmerPlot',
                object_id=plot.id
            )
            
            plot.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
def confirm_job_and_set_price(request):
    """Confirm job from team and set your price for mukadams"""
    try:
        job_id = request.data.get('job_id')
        your_price = request.data.get('your_price_per_acre')
        
        if not job_id or not your_price:
            return Response(
                {"error": "job_id and your_price_per_acre are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        job = get_object_or_404(Job, id=job_id)
        
        # Update job with your price
        job.your_price_per_acre = your_price
        job.status = 'priced'
        job.confirmed_at = timezone.now()
        job.save()
        
        print(f"✅ Job confirmed with price: {job.farmer.name} - ₹{your_price}/acre")
        
        return Response({
            "message": "Job confirmed and priced successfully",
            "job_id": str(job.id),
            "farmer_name": job.farmer.name,
            "your_price": float(your_price),
            "farmer_original_price": float(job.farmer_price_per_acre),
            "margin_per_acre": float(job.farmer_price_per_acre) - float(your_price),
            "status": job.status
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    
    # def _send_websocket_update(self, update_type, data):
    #     """Send real-time update via WebSocket"""
    #     try :
    #         channel_layer = get_channel_layer()
    #         if channel_layer:
    #             async_to_sync(channel_layer.group_send)(
    #                 'job_updates',
    #                 {
    #                     'type': update_type,
    #                     'data': data
    #                 }
    #             )
    #     except Exception as e:
    #     # Log the error but don't crash the request
    #         print(f"WebSocket update failed: {e}")
    #         pass 

    # @action(detail=False, methods=['post'])
    # def confirm_job(self, request):
    #     """
    #     Endpoint for team members to confirm a job
    #     POST /api/jobs/confirm_job/
    #     """
    #     serializer = JobCreateSerializer(data=request.data)
    #     if serializer.is_valid():
    #         job = serializer.save()
            
    #         changed_by_user = None
    #         if request.user.is_authenticated:
    #             changed_by_user = request.user
    #         # Log status change
    #         JobStatusHistory.objects.create(
    #             job=job,
    #             from_status='',
    #             to_status='confirmed',
    #             changed_by=changed_by_user,
    #             notes='Job confirmed by team member'
    #         )
    #         # self._send_websocket_update('job_status_changed', {
    #         #     'job_id': str(job.id),
    #         #     'message': 'New job confirmed',
    #         #     'status': job.status
    #         # })
            
    #         return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def confirm_job(self, request):
        """
        Endpoint for team members to confirm a job from labour need data
        POST /api/jobs/confirm_job/
        
        Expected payload:
        {
            "farmer_name": "Ramesh Kumar",
            "phone_number": "9876543210",
            "date_needed": "2025-11-15",
            "special_requirements": "Need experienced workers",
            "activity_briefs": [
                {
                    "activity_name": "Pruning",
                    "acres": 5.5,
                    "date_needed": "2025-11-15"
                },
                {
                    "activity_name": "Harvesting", 
                    "acres": 3.0,
                    "date_needed": "2025-11-16"
                }
            ],
            "location": "Nashik",
            "farmer_village": "Pimpalgaon",
            "requested_time": "08:00:00",
            "farmer_price_per_acre": 1500,
            "notes": "Additional notes here",
            "workers_needed": 10
        }
        """
        serializer = JobCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            job = serializer.save()
            
            # Get user for logging
            changed_by_user = request.user if request.user.is_authenticated else None
            
            # Log status change
            JobStatusHistory.objects.create(
                job=job,
                from_status='',
                to_status='confirmed',
                changed_by=changed_by_user,
                notes='Job confirmed by team member from labour need'
            )
            
            # Return the created job
            return Response({
                'success': True,
                'message': 'Job confirmed successfully',
                'job': JobSerializer(job).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def confirm_multiple_jobs(self, request):
        """
        Endpoint to create multiple jobs from activity briefs
        Returns all created jobs
        POST /api/jobs/confirm_multiple_jobs/
        """
        serializer = JobCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            # Get validated data
            validated_data = serializer.validated_data
            phone_number = validated_data['phone_number']
            farmer_name = validated_data.get('farmer_name', 'Unknown Farmer')
            farmer_village = validated_data.get('farmer_village', validated_data.get('location', ''))
            activity_briefs = validated_data.get('activity_briefs', [])
            
            # Get or create farmer
            farmer, _ = Farmer.objects.get_or_create(
                phone=phone_number,
                defaults={
                    'name': farmer_name or f"Farmer {phone_number}",
                    'village': farmer_village
                }
            )
            
            jobs_created = []
            changed_by_user = request.user if request.user.is_authenticated else None
            
            # Create a job for each activity brief
            for brief in activity_briefs:
                activity_name = brief['activity_name']
                acres = brief['acres']
                brief_date = brief.get('date_needed') or validated_data.get('date_needed')
                
                # Get or create activity
                activity, _ = Activity.objects.get_or_create(
                    name=activity_name,
                    defaults={'name': activity_name}
                )
                
                # Create job
                job = Job.objects.create(
                    farmer=farmer,
                    activity=activity,
                    farm_size_acres=acres,
                    location=validated_data.get('location', farmer_village),
                    requested_date=brief_date or timezone.now().date(),
                    requested_time=validated_data.get('requested_time') or timezone.now().time(),
                    farmer_price_per_acre=validated_data.get('farmer_price_per_acre', 0),
                    notes=f"{validated_data.get('special_requirements', '')}\n{validated_data.get('notes', '')}".strip(),
                    workers_needed=validated_data.get('workers_needed', 5),
                    status='confirmed'
                )
                
                # Log status change
                JobStatusHistory.objects.create(
                    job=job,
                    from_status='',
                    to_status='confirmed',
                    changed_by=changed_by_user,
                    notes=f'Job confirmed from labour need - Activity: {activity_name}'
                )
                
                jobs_created.append(job)
            
            return Response({
                'success': True,
                'message': f'{len(jobs_created)} job(s) confirmed successfully',
                'jobs': JobSerializer(jobs_created, many=True).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign_to_mukadams(self, request, pk=None):
        """Enhanced version with actual webhook notifications"""
        try:
            job = self.get_object()
            mukadam_ids = request.data.get('mukadam_ids', [])
            
            if not mukadam_ids:
                return Response({"error": "At least one mukadam_id required"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            assignments_created = []
            notifications_sent = []
            notification_failures = []
            
            for mukadam_id in mukadam_ids:
                try:
                    mukadam = get_object_or_404(Mukadam, id=mukadam_id)
                    
                    # Create assignment
                    assignment, created = JobAssignment.objects.get_or_create(
                        job=job,
                        mukadam=mukadam
                    )
                    
                    if created:
                        assignments_created.append(assignment)
                        
                        # Create bid record
                        MukadamBid.objects.get_or_create(
                            job=job,
                            mukadam=mukadam,
                            defaults={'status': 'pending'}
                        )
                        
                        # 🔔 Send notification to this specific mukadam
                        try:
                            notification_result = self._send_job_notification_to_mukadam(job, mukadam)
                            notifications_sent.append({
                                'mukadam_id': str(mukadam.id),
                                'mukadam_name': mukadam.name,
                                'notification_status': 'sent',
                                'webhook_response': notification_result
                            })
                        except Exception as webhook_error:
                            notification_failures.append({
                                'mukadam_id': str(mukadam.id),
                                'mukadam_name': mukadam.name,
                                'error': str(webhook_error)
                            })
                
                except Exception as e:
                    notification_failures.append({
                        'mukadam_id': mukadam_id,
                        'error': f"Failed to process: {str(e)}"
                    })
            
            # Update job status
            job.status = 'bidding'
            job.save()
            
            # Create status history
            JobStatusHistory.objects.create(
                job=job,
                from_status='confirmed',
                to_status='bidding',
                changed_by=request.user if request.user.is_authenticated else None,
                notes=f'Assigned to {len(assignments_created)} mukadams. Notifications sent: {len(notifications_sent)}, Failed: {len(notification_failures)}'
            )
            
            return Response({
                "message": f"Job assigned to {len(assignments_created)} mukadams",
                "job": {
                    "id": str(job.id),
                    "status": job.status
                },
                "assignments": len(assignments_created),
                "notifications": {
                    "sent": notifications_sent,
                    "failed": notification_failures,
                    "total_sent": len(notifications_sent),
                    "total_failed": len(notification_failures)
                }
            })
            
        except Exception as e:
            return Response(
                {"error": f"Assignment failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Update your Django views.py to add verbose logging
    def _send_job_notification_to_mukadam(self, job, mukadam):
        """Enhanced with detailed logging for testing"""
        
        print(f"\n{'='*80}")
        print(f"📤 SENDING JOB NOTIFICATION")
        print(f"{'='*80}")
        print(f"🎯 Target Mukadam: {mukadam.name} ({mukadam.id})")
        print(f"🌾 Job: {job.farmer.name} - {job.activity.name}")
        print(f"📏 Farm Size: {job.farm_size_acres} acres")
        
        job_data = {
            "job_id": str(job.id),
            "notification_type": "new_job_assignment",
            "timestamp": timezone.now().isoformat(),
            
            "target_mukadam": {
                "mukadam_id": str(mukadam.id),
                "mukadam_name": mukadam.name,
                "mukadam_phone": mukadam.phone
            },
            
            "farmer": {
                "name": job.farmer.name,
                "phone": job.farmer.phone,
                "location": job.location
            },
            
            "job_details": {
                "activity": job.activity.name,
                "farm_size_acres": float(job.farm_size_acres),
                "requested_date": str(job.requested_date),
                "requested_time": str(job.requested_time) if job.requested_time else None,
                "location": job.location,
                "notes": job.notes or "",
                "urgency": self._calculate_urgency(job),
                "estimated_duration": self._estimate_job_duration(job)
            },
            
            "bidding_info": {
                "deadline": (timezone.now() + timedelta(hours=48)).isoformat(),
                "competition_level": self._get_competition_level(job),
                "submit_bid_url": f"{settings.BASE_URL}/api/bids/submit_bid/"
            }
        }
        
        webhook_url = settings.MUKADAM_WEBHOOK_URLS.get('default')
        
        print(f"\n📋 PAYLOAD TO SEND:")
        print(json.dumps(job_data, indent=2))
        print(f"\n🌐 Webhook URL: {webhook_url}")
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-Platform-Source': 'FarmOps-WorkCrop',
                'X-Job-Assignment': str(job.id)
            }
            
            print(f"\n🔗 Making POST request...")
            response = requests.post(
                webhook_url,
                json=job_data,
                headers=headers,
                timeout=30
            )
            
            print(f"✅ Response Status: {response.status_code}")
            print(f"📋 Response Body:")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text)
            
            print(f"{'='*80}")
            
            if response.status_code == 200:
                return {
                    "status": "success", 
                    "webhook_url": webhook_url,
                    "response_code": response.status_code,
                    "mukadam_notified": mukadam.name
                }
            else:
                raise Exception(f"Webhook returned {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ WEBHOOK FAILED: {str(e)}")
            print(f"{'='*80}")
            raise Exception(f"Webhook notification failed: {str(e)}")
    def _get_mukadam_webhook_url(self, mukadam):
        """Get webhook URL for specific mukadam"""
        # In production, this would be stored in mukadam model
        # For demo, we'll use environment variables or return None for logging
        webhook_urls = getattr(settings, 'MUKADAM_WEBHOOK_URLS', {})
        return webhook_urls.get(str(mukadam.id))
    
    def _get_mukadam_api_token(self, mukadam):
        """Get API token for specific mukadam"""
        # In production, this would be stored securely
        return f"mukadam_token_{mukadam.id}"
    
    def _calculate_urgency(self, job):
        """Calculate job urgency based on requested date"""
        days_until_job = (job.requested_date - timezone.now().date()).days
        
        if days_until_job <= 1:
            return "urgent"
        elif days_until_job <= 3:
            return "high"
        elif days_until_job <= 7:
            return "medium"
        else:
            return "low"
    
    def _estimate_job_duration(self, job):
        """Estimate job duration based on activity and farm size"""
        base_hours = {
            'pruning': 2,
            'harvesting': 3,
            'spraying': 1,
            'tying': 2
        }
        
        activity_name = job.activity.name.lower()
        hours_per_acre = base_hours.get(activity_name, 2)
        estimated_hours = hours_per_acre * float(job.farm_size_acres)
        
        return {
            "estimated_hours": round(estimated_hours, 1),
            "estimated_days": max(1, round(estimated_hours / 8))
        }
    
    def _get_competition_level(self, job):
        """Determine competition level based on assigned mukadams"""
        assignment_count = JobAssignment.objects.filter(job=job).count()
        
        if assignment_count >= 6:
            return "high"
        elif assignment_count >= 3:
            return "medium"
        else:
            return "low"
    @action(detail=True, methods=['get'])
    def bids(self, request, pk=None):
        """
        Get all bids for a job
        GET /api/jobs/{id}/bids/
        """
        job = self.get_object()
        bids = job.bids.select_related('mukadam').order_by('bid_price_per_acre')
        serializer = MukadamBidSerializer(bids, many=True)
        return Response(serializer.data)
    
    # Update your finalize_mukadam method in views.py
    @action(detail=True, methods=['post'])
    def finalize_mukadam(self, request, pk=None):
        """Enhanced finalize with notification to selected mukadam"""
        try:
            job = self.get_object()
            
            # Get the bid ID and final price
            bid_id = request.data.get('bid_id')
            final_price = request.data.get('final_price')
            
            if not bid_id:
                return Response({"error": "bid_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not final_price:
                return Response({"error": "final_price is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the winning bid
            try:
                winning_bid = MukadamBid.objects.get(id=bid_id)
                mukadam = winning_bid.mukadam
            except MukadamBid.DoesNotExist:
                return Response({"error": "Bid not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # Update the winning bid
            winning_bid.status = 'selected'
            winning_bid.final_price_per_acre = final_price
            winning_bid.save()
            
            # Update job
            job.finalized_mukadam = mukadam
            job.finalized_price = final_price
            job.status = 'finalized'
            job.finalized_at = timezone.now()
            job.save()
            
            # Update other bids to rejected
            other_bids = MukadamBid.objects.filter(
                job=job, 
                status='interested'
            ).exclude(id=bid_id)
            
            for bid in other_bids:
                bid.status = 'rejected'
                bid.save()
            
            # Create status history
            JobStatusHistory.objects.create(
                job=job,
                from_status='bidding',
                to_status='finalized',
                changed_by=request.user if request.user.is_authenticated else None,
                notes=f'Selected {mukadam.name} at ₹{final_price}/acre'
            )
            
            # 🔔 Send notification to SELECTED mukadam
            try:
                selection_result = self._notify_selected_mukadam(job, mukadam, winning_bid, final_price)
                print(f"✅ Notified selected mukadam: {selection_result}")
            except Exception as e:
                print(f"⚠️ Failed to notify selected mukadam: {str(e)}")
            
            # 🔔 Send notifications to REJECTED mukadams
            try:
                rejection_results = self._notify_rejected_mukadams(job, other_bids)
                print(f"✅ Notified {len(rejection_results)} rejected mukadams")
            except Exception as e:
                print(f"⚠️ Failed to notify rejected mukadams: {str(e)}")
            
            return Response({
                "message": f"Job finalized with {mukadam.name}",
                "mukadam": mukadam.name,
                "price": float(final_price),
                "job_status": job.status,
                "notifications": {
                    "selected_mukadam_notified": True,
                    "rejected_mukadams_count": other_bids.count()
                }
            })
            
        except Exception as e:
            return Response(
                {"error": f"Failed to finalize job: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _notify_selected_mukadam(self, job, mukadam, bid, final_price):
        """Send 'YOU WON' notification to selected mukadam"""
        
        total_amount = float(final_price) * float(job.farm_size_acres)
        
        notification_data = {
            "notification_type": "job_selection_winner",
            "job_id": str(job.id),
            "timestamp": timezone.now().isoformat(),
            
            # Target mukadam
            "target_mukadam": {
                "mukadam_id": str(mukadam.id),
                "mukadam_name": mukadam.name,
                "mukadam_phone": mukadam.phone
            },
            
            # Selection details
            "selection_result": {
                "status": "selected",
                "message": "🎉 Congratulations! Your bid has been selected!",
                "final_price_per_acre": float(final_price),
                "total_amount": total_amount,
                "original_bid_price": float(bid.bid_price_per_acre) if bid.bid_price_per_acre else None,
                "price_negotiated": float(final_price) != float(bid.bid_price_per_acre) if bid.bid_price_per_acre else False
            },
            
            # Job execution details
            "job_execution": {
                "farmer_contact": {
                    "name": job.farmer.name,
                    "phone": job.farmer.phone,
                    "location": job.location
                },
                "work_details": {
                    "activity": job.activity.name,
                    "farm_size_acres": float(job.farm_size_acres),
                    "scheduled_date": str(job.requested_date),
                    "scheduled_time": str(job.requested_time) if job.requested_time else "Morning",
                    "estimated_duration": bid.estimated_duration_hours,
                    "special_notes": job.notes or ""
                },
                "payment_info": {
                    "rate": float(final_price),
                    "total_amount": total_amount,
                    "payment_terms": "Payment upon completion of work"
                }
            },
            
            # Next steps
            "next_steps": [
                "Contact farmer to confirm timing",
                "Arrange your team for the scheduled date", 
                "Complete the work as per requirements",
                "Submit completion report for payment"
            ]
        }
        
        return self._send_webhook_notification(notification_data, "WINNER")

    def _notify_rejected_mukadams(self, job, rejected_bids):
        """Send 'Better luck next time' notifications to rejected mukadams"""
        
        results = []
        
        for bid in rejected_bids:
            notification_data = {
                "notification_type": "job_selection_rejected", 
                "job_id": str(job.id),
                "timestamp": timezone.now().isoformat(),
                
                # Target mukadam
                "target_mukadam": {
                    "mukadam_id": str(bid.mukadam.id),
                    "mukadam_name": bid.mukadam.name,
                    "mukadam_phone": bid.mukadam.phone
                },
                
                # Rejection details
                "selection_result": {
                    "status": "not_selected",
                    "message": "Thank you for your bid. Another mukadam was selected for this job.",
                    "your_bid_price": float(bid.bid_price_per_acre) if bid.bid_price_per_acre else None,
                    "reason": "Another bid was more competitive"
                },
                
                # Encouragement
                "feedback": {
                    "message": "Keep bidding! More opportunities are coming soon.",
                    "tips": [
                        "Consider competitive pricing",
                        "Highlight your team's expertise", 
                        "Respond quickly to new job alerts"
                    ]
                }
            }
            
            try:
                result = self._send_webhook_notification(notification_data, "REJECTED")
                results.append(result)
            except Exception as e:
                print(f"Failed to notify {bid.mukadam.name}: {str(e)}")
                
        return results

    def _send_webhook_notification(self, notification_data, notification_type):
        """Send webhook notification with detailed logging"""
        
        webhook_url = settings.MUKADAM_WEBHOOK_URLS.get('default')
        target_mukadam = notification_data.get('target_mukadam', {})
        
        print(f"\n{'='*80}")
        print(f"📤 SENDING {notification_type} NOTIFICATION")
        print(f"{'='*80}")
        print(f"🎯 To: {target_mukadam.get('mukadam_name')} ({target_mukadam.get('mukadam_id')})")
        print(f"🌐 Webhook: {webhook_url}")
        print(f"📋 Payload:")
        print(json.dumps(notification_data, indent=2, default=str))
        
        if not webhook_url:
            print(f"⚠️ No webhook configured - notification logged only")
            return {"status": "logged", "method": "console"}
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-Platform-Source': 'FarmOps-WorkCrop',
                'X-Notification-Type': notification_type
            }
            
            response = requests.post(
                webhook_url,
                json=notification_data,
                headers=headers,
                timeout=30
            )
            
            print(f"✅ Response Status: {response.status_code}")
            print(f"📋 Response:")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text)
            
            print(f"{'='*80}")
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "mukadam": target_mukadam.get('mukadam_name'),
                    "notification_type": notification_type
                }
            else:
                raise Exception(f"Webhook returned {response.status_code}")
                
        except Exception as e:
            print(f"❌ Webhook failed: {str(e)}")
            print(f"{'='*80}")
            raise e
    # Add to JobViewSet in views.py
    @action(detail=True, methods=['get'])
    def bid_details(self, request, pk=None):
        """Get complete bid details for a job including all bids and mukadam performance"""
        try:
            job = self.get_object()
            
            # Get all bids for this job
            all_bids = job.bids.all().select_related('mukadam').order_by('-created_at')
            
            bid_data = []
            for bid in all_bids:
                # Calculate additional performance metrics for each mukadam
                mukadam_stats = self._get_mukadam_performance_stats(bid.mukadam)
                
                bid_info = {
                    'id': str(bid.id),
                    'mukadam': {
                        'id': str(bid.mukadam.id),
                        'name': bid.mukadam.name,
                        'phone': bid.mukadam.phone,
                        'location': bid.mukadam.location,
                        'labourers': bid.mukadam.number_of_labourers,
                        'is_active': bid.mukadam.is_active,
                    },
                    'bid': {
                        'status': bid.status,
                        'bid_price_per_acre': float(bid.bid_price_per_acre) if bid.bid_price_per_acre else None,
                        'final_price_per_acre': float(bid.final_price_per_acre) if bid.final_price_per_acre else None,
                        'estimated_duration_hours': bid.estimated_duration_hours,
                        'comments': bid.comments,
                        'responded_at': bid.responded_at,
                    },
                    'performance': mukadam_stats,
                    'comparison': {
                        'vs_farmer_price': self._calculate_price_difference(
                            bid.bid_price_per_acre, job.farmer_price_per_acre
                        ) if bid.bid_price_per_acre else None,
                        'total_cost': float(bid.bid_price_per_acre * job.farm_size_acres) if bid.bid_price_per_acre else None,
                    }
                }
                bid_data.append(bid_info)
            
            # Sort bids: selected first, then interested by price, then others
            def sort_bids(bid):
                if bid['bid']['status'] == 'selected':
                    return (0, 0)  # Selected comes first
                elif bid['bid']['status'] == 'interested':
                    price = bid['bid']['bid_price_per_acre'] or float('inf')
                    return (1, price)  # Then interested by price
                else:
                    return (2, 0)  # Then others
            
            bid_data.sort(key=sort_bids)
            
            return Response({
                'job': {
                    'id': str(job.id),
                    'farmer_name': job.farmer.name,
                    'activity': job.activity.name,
                    'farm_size_acres': float(job.farm_size_acres),
                    'farmer_price_per_acre': float(job.farmer_price_per_acre),
                    'status': job.status,
                    'finalized_mukadam': job.finalized_mukadam.name if job.finalized_mukadam else None,
                    'finalized_price': float(job.finalized_price) if job.finalized_price else None,
                },
                'bid_summary': {
                    'total_bids': len(bid_data),
                    'interested_bids': len([b for b in bid_data if b['bid']['status'] == 'interested']),
                    'declined_bids': len([b for b in bid_data if b['bid']['status'] == 'declined']),
                    'selected_bid': len([b for b in bid_data if b['bid']['status'] == 'selected']),
                    'rejected_bids': len([b for b in bid_data if b['bid']['status'] == 'rejected']),
                },
                'bids': bid_data
            })
            
        except Exception as e:
            return Response(
                {"error": f"Failed to get bid details: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_mukadam_performance_stats(self, mukadam):
        """Calculate comprehensive performance statistics for a mukadam"""
        total_bids = MukadamBid.objects.filter(
            mukadam=mukadam,
            status__in=['interested', 'selected', 'rejected']
        ).count()
        
        won_bids = MukadamBid.objects.filter(mukadam=mukadam, status='selected').count()
        
        # Average bid price
        from django.db.models import Avg
        avg_bid = MukadamBid.objects.filter(
            mukadam=mukadam,
            bid_price_per_acre__isnull=False,
            status__in=['interested', 'selected', 'rejected']
        ).aggregate(avg=Avg('bid_price_per_acre'))['avg']
        
        # Recent performance (last 10 bids)
        recent_bids = MukadamBid.objects.filter(
            mukadam=mukadam,
            status__in=['interested', 'selected', 'rejected']
        ).order_by('-created_at')[:10]
        
        recent_wins = sum(1 for bid in recent_bids if bid.status == 'selected')
        
        return {
            'total_bids': total_bids,
            'won_bids': won_bids,
            'success_rate': round((won_bids / total_bids * 100), 1) if total_bids > 0 else 0,
            'avg_bid_price': round(float(avg_bid), 2) if avg_bid else 0,
            'recent_performance': {
                'last_10_bids': len(recent_bids),
                'recent_wins': recent_wins,
                'recent_success_rate': round((recent_wins / len(recent_bids) * 100), 1) if recent_bids else 0
            }
        }

    def _calculate_price_difference(self, bid_price, farmer_price):
        """Calculate price difference and savings percentage"""
        if not bid_price or not farmer_price:
            return None
        
        difference = float(farmer_price) - float(bid_price)
        percentage = (difference / float(farmer_price)) * 100
        
        return {
            'difference': round(difference, 2),
            'percentage': round(percentage, 1),
            'is_saving': difference > 0
        }
    

    # Add to JobViewSet
    @action(detail=True, methods=['get'])
    def assignments(self, request, pk=None):
        """Get current mukadam assignments for a job"""
        job = self.get_object()
        
        assignments = JobAssignment.objects.filter(job=job).select_related('mukadam')
        
        return Response({
            "job_id": str(job.id),
            "assignments": [
                {
                    "mukadam_id": str(assignment.mukadam.id),
                    "mukadam_name": assignment.mukadam.name,
                    "assigned_at": assignment.assigned_at,
                    "has_responded": hasattr(assignment.mukadam, 'bids') and assignment.mukadam.bids.filter(job=job).exists()
                }
                for assignment in assignments
            ]
        })
    # Add to JobViewSet in views.py
    @action(detail=True, methods=['post'])
    def reassign_to_mukadams(self, request, pk=None):
        """
        Re-assign job to additional mukadams when current bids are unsatisfactory
        POST /api/jobs/{id}/reassign_to_mukadams/
        Body: {"mukadam_ids": ["uuid1", "uuid2"], "reason": "Need better pricing options"}
        """
        try:
            job = self.get_object()
            
            if job.status not in ['bidding', 'assigned']:
                return Response(
                    {"error": f"Job must be in 'bidding' or 'assigned' status to reassign. Current status: {job.status}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            mukadam_ids = request.data.get('mukadam_ids', [])
            reason = request.data.get('reason', 'Additional bidding round requested')
            
            if not mukadam_ids:
                return Response(
                    {"error": "At least one mukadam_id required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get mukadams that haven't been assigned yet
            existing_assignments = JobAssignment.objects.filter(job=job).values_list('mukadam_id', flat=True)
            new_assignments = []
            skipped_assignments = []
            
            for mukadam_id in mukadam_ids:
                try:
                    mukadam = Mukadam.objects.get(id=mukadam_id, is_active=True)
                    
                    # Check if already assigned
                    if str(mukadam.id) in [str(id) for id in existing_assignments]:
                        skipped_assignments.append({
                            'mukadam': mukadam.name,
                            'reason': 'Already assigned to this job'
                        })
                        continue
                    
                    # Create new assignment
                    assignment, created = JobAssignment.objects.get_or_create(
                        job=job,
                        mukadam=mukadam
                    )
                    
                    if created:
                        new_assignments.append(assignment)
                        
                        # Create new bid record in pending status
                        bid, bid_created = MukadamBid.objects.get_or_create(
                            job=job,
                            mukadam=mukadam,
                            defaults={
                                'status': 'pending',
                                'comments': f'Re-assigned for additional bidding. Reason: {reason}'
                            }
                        )
                        
                    else:
                        skipped_assignments.append({
                            'mukadam': mukadam.name,
                            'reason': 'Assignment already exists'
                        })
                        
                except Mukadam.DoesNotExist:
                    skipped_assignments.append({
                        'mukadam': f'ID: {mukadam_id}',
                        'reason': 'Mukadam not found or inactive'
                    })
            
            # Update job status if it was finalized back to bidding
            if job.status != 'bidding':
                job.status = 'bidding'
                job.save()
            
            # Create status history
            changed_by_user = request.user if request.user.is_authenticated else None
            JobStatusHistory.objects.create(
                job=job,
                from_status=job.status,
                to_status='bidding',
                changed_by=changed_by_user,
                notes=f'Re-assigned to {len(new_assignments)} additional mukadams. Reason: {reason}'
            )
            
            # Try to notify new mukadams
            try:
                for assignment in new_assignments:
                    self._notify_mukadam_about_job(job, assignment.mukadam)
            except Exception as e:
                print(f"Notification failed: {e}")
            
            return Response({
                "message": f"Job re-assigned to {len(new_assignments)} additional mukadams",
                "job": {
                    "id": str(job.id),
                    "status": job.status,
                    "total_assignments": JobAssignment.objects.filter(job=job).count()
                },
                "new_assignments": [
                    {
                        "mukadam_id": str(assignment.mukadam.id),
                        "mukadam_name": assignment.mukadam.name,
                        "assigned_at": assignment.assigned_at
                    }
                    for assignment in new_assignments
                ],
                "skipped": skipped_assignments,
                "summary": {
                    "total_requested": len(mukadam_ids),
                    "successfully_assigned": len(new_assignments),
                    "skipped": len(skipped_assignments)
                }
            })
            
        except Exception as e:
            return Response(
                {"error": f"Failed to re-assign job: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

    @action(detail=True, methods=['post'])
    def notify_mukadams(self, request, pk=None):
        """Send notifications to mukadams - NOW WITH PUSH!"""
        try:
            job = self.get_object()
            mukadam_ids = request.data.get('mukadam_ids', [])
            
            if job.status != 'priced':
                return Response({"error": "Job must be priced first"}, status=400)
            
            notifications_sent = []
            push_sent_count = 0
            
            for mukadam_id in mukadam_ids:
                mukadam = get_object_or_404(Mukadam, id=mukadam_id)
                
                # Create interest record
                MukadamInterest.objects.get_or_create(
                    job=job,
                    mukadam=mukadam
                )
                
                notifications_sent.append(mukadam.name)
                
                # ✅ SEND PUSH NOTIFICATION
                if mukadam.fcm_token:
                    success = send_push_notification(
                        fcm_token=mukadam.fcm_token,
                        title="नवीन काम उपलब्ध",
                        body=f"{job.activity.name} - {job.location} - ₹{job.your_price_per_acre}/एकर",
                        data={
                            "job_id": str(job.id),
                            "type": "new_job",
                            "screen": "/available-jobs"
                        }
                    )
                    if success:
                        push_sent_count += 1
            
            job.status = 'notified'
            job.save()
            
            return Response({
                "message": f"Notified {len(notifications_sent)} mukadams",
                "notified": notifications_sent,  # ✅ ADD THIS
                "push_notifications_sent": push_sent_count
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)
    
    
    def _send_simple_notification(self, data):
        """Send simple notification to mukadam app"""
        webhook_url = settings.MUKADAM_WEBHOOK_URLS.get('default')
        
        print(f"\n📱 SIMPLE JOB NOTIFICATION")
        print(f"🎯 To: {data['mukadam_name']}")
        print(f"💰 Price: ₹{data['job_details']['your_price']}/acre")
        print(f"📋 Total: ₹{data['job_details']['total_amount']}")
        
        if webhook_url:
            response = requests.post(webhook_url, json=data, timeout=30)
            return response.json()
        
        return {"status": "logged"}
    
    # Collect mukadam responses
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Mukadam responds YES/NO to job"""
        
        job = self.get_object()
        mukadam_id = request.data.get('mukadam_id')
        interested = request.data.get('interested')
        if mukadam_id is None or interested is None:
            return Response(
                {"error": "Both 'mukadam_id' and 'interested' are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        mukadam = get_object_or_404(Mukadam, id=mukadam_id)
        
        interest, created = MukadamInterest.objects.get_or_create(
            job=job,
            mukadam=mukadam,
            defaults={
                "is_interested": interested,
                "responded_at": timezone.now(),
                "response_status": "interested" if interested else "declined",
            }
        )

        # ✅ If it already existed, update it
        if not created:
            interest.is_interested = interested
            interest.responded_at = timezone.now()
            interest.response_status = "interested" if interested else "declined"
            interest.save()

        print(f"📝 {mukadam.name} responded: {'YES' if interested else 'NO'}")

        return Response({
            "message": f"Response recorded: {'Interested' if interested else 'Not interested'}",
            "mukadam": mukadam.name,
            "interested": interested,
            "new_record_created": created
        },
        status=status.HTTP_201_CREATED)

        # In views.py - UPDATE this method
    
    @action(detail=True, methods=['post'])
    def assign_final(self, request, pk=None):
        """Assign job to mukadam - NOW WITH PUSH!"""
        try:
            job = self.get_object()
            mukadam_id = request.data.get('mukadam_id')
            
            mukadam = get_object_or_404(Mukadam, id=mukadam_id)
            
            # Check if interested
            interest = MukadamInterest.objects.get(job=job, mukadam=mukadam)
            if not interest.is_interested:
                return Response({"error": "Mukadam not interested"}, status=400)
            
            # Assign job
            job.assigned_mukadam = mukadam
            job.status = 'assigned'
            job.assigned_at = timezone.now()
            job.save()
            
            interest.response_status = 'assigned'
            interest.save()
            
            # ✅ SEND PUSH NOTIFICATION
            push_sent = False
            if mukadam.fcm_token:
                push_sent = send_push_notification(
                    fcm_token=mukadam.fcm_token,
                    title="काम मिळाले!",
                    body=f"{job.activity.name} - ₹{job.your_price_per_acre}/एकर",
                    data={
                        "job_id": str(job.id),
                        "type": "job_assigned",
                        "screen": "/assigned-jobs"
                    }
                )
            
            return Response({
                "message": f"Job assigned to {mukadam.name}",
                "push_notification_sent": push_sent
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
    def _notify_mukadam_about_job(self, job, mukadam):
        """Send notification to mukadam about new job assignment"""
        notification_data = {
            "job_id": str(job.id),
            "farmer_name": job.farmer.name,
            "farmer_phone": job.farmer.phone,
            "farmer_village": getattr(job.farmer, 'village', 'N/A'),
            "activity": job.activity.name,
            "farm_size_acres": float(job.farm_size_acres),
            "location": job.location,
            "requested_date": str(job.requested_date),
            "requested_time": str(job.requested_time),
            "notes": job.notes,
            "deadline": "48 hours from now"  # You can make this configurable
        }
        
        # This would call the mukadam app webhook
        print(f"🔔 Would notify {mukadam.name}: New job assignment - {notification_data}")


    # In views.py - ADD this method to JobViewSet
    def _notify_assignment(self, job, mukadam):
        """Send notification to assigned mukadam"""
        
        notification_data = {
            "notification_type": "job_assigned",
            "job_id": str(job.id),
            "timestamp": timezone.now().isoformat(),
            
            "target_mukadam": {
                "mukadam_id": str(mukadam.id),
                "mukadam_name": mukadam.name,
                "mukadam_phone": mukadam.phone
            },
            
            "assignment_details": {
                "status": "assigned",
                "message": "🎉 Job assigned to you!",
                "price_per_acre": float(job.your_price_per_acre),
                "total_amount": float(job.your_price_per_acre * job.farm_size_acres)
            },
            
            "job_details": {
                "farmer_name": job.farmer.name,
                "farmer_phone": job.farmer.phone,
                "activity": job.activity.name,
                "farm_size_acres": float(job.farm_size_acres),
                "location": job.location,
                "scheduled_date": str(job.requested_date),
                "special_notes": job.notes or ""
            },
            
            "next_steps": [
                "Contact farmer to confirm details",
                "Prepare your team for the scheduled date",
                "Complete the work as agreed",
                "Job status will be marked as completed"
            ]
        }
        
        webhook_url = settings.MUKADAM_WEBHOOK_URLS.get('default')
        
        print(f"\n🎯 NOTIFYING ASSIGNED MUKADAM")
        print(f"👤 {mukadam.name} - Job Assigned!")
        print(f"💰 ₹{job.your_price_per_acre}/acre")
        
        if webhook_url:
            try:
                response = requests.post(webhook_url, json=notification_data, timeout=30)
                print(f"✅ Assignment notification sent")
                return response.json()
            except Exception as e:
                print(f"⚠️ Failed to send assignment notification: {e}")
        
        return {"status": "logged"}

    # In views.py - ADD this method to JobViewSet
    # Update your simple_list method to show different response statuses
    @action(detail=False, methods=['get'])
    def simple_list(self, request):
        """Get jobs with enhanced interest data"""
        
        jobs = Job.objects.select_related('farmer', 'activity').prefetch_related(
            'interests__mukadam'
        ).all()
        
        job_data = []
        for job in jobs:
            
            interests_data = []
            for interest in job.interests.all():
                
                # ✅ Determine correct status
                if interest.response_status == 'assigned':
                    status = 'assigned'
                elif interest.responded_at:
                    status = 'interested' if interest.is_interested else 'declined'
                else:
                    status = 'pending'  # ✅ No response yet
                
                interests_data.append({
                    'id': str(interest.id),
                    'mukadam': {
                        'id': str(interest.mukadam.id),
                        'name': interest.mukadam.name,
                        'phone': interest.mukadam.phone,
                        'location': interest.mukadam.location,
                        'team_size': interest.mukadam.number_of_labourers
                    },
                    'is_interested': interest.is_interested,
                    'responded_at': interest.responded_at.isoformat() if interest.responded_at else None,
                    'response_status': status  # ✅ Use correct status
                })
            
            # Add "no_response" entries for notified but not responded mukadams
            # This would require tracking assignments - for now we'll show what we have
            
            job_info = {
                'id': str(job.id),
                'farmer': {
                    'name': job.farmer.name,
                    'phone': job.farmer.phone,
                    'village': getattr(job.farmer, 'village', '')
                },
                'activity': {
                    'name': job.activity.name
                },
                'farm_size_acres': float(job.farm_size_acres),
                'location': job.location,
                'requested_date': str(job.requested_date),
                'farmer_price_per_acre': float(job.farmer_price_per_acre),
                'your_price_per_acre': float(job.your_price_per_acre) if job.your_price_per_acre else None,
                'workers_needed': job.workers_needed,
                'status': job.status,
                'assigned_mukadam': {
                    'id': str(job.assigned_mukadam.id),
                    'name': job.assigned_mukadam.name,
                    'team_size': job.assigned_mukadam.number_of_labourers
                } if job.assigned_mukadam else None,
                'interests': interests_data,
            'response_summary': {
                'pending_count': len([i for i in interests_data if i['response_status'] == 'pending']),
                'interested_count': len([i for i in interests_data if i['response_status'] == 'interested']),
                'declined_count': len([i for i in interests_data if i['response_status'] == 'declined']),
                'assigned_count': len([i for i in interests_data if i['response_status'] == 'assigned']),
           },# ✅ ADD team size analysis
            'team_analysis': {
                'workers_needed': job.workers_needed,
                'suitable_mukadams': len([i for i in interests_data if i['mukadam']['team_size'] >= job.workers_needed]),
                'team_coverage': f"{job.workers_needed} workers needed"
            }
            }
            job_data.append(job_info)
        
        return Response(job_data)
    
    @action(detail=True, methods=['get'])
    def edit_history(self, request, pk=None):
        """Get edit history for a job"""
        job = self.get_object()
        history = job.edit_history.all()
        serializer = JobEditHistorySerializer(history, many=True)
        return Response(serializer.data)


class MukadamViewSet(viewsets.ModelViewSet):
    queryset = Mukadam.objects.all()
    
    def get_serializer_class(self):
        if self.request.query_params.get('detailed'):
            return MukadamDetailSerializer
        return MukadamSerializer
    
    def get_queryset(self):
        queryset = Mukadam.objects.all()
        
        if self.request.query_params.get('detailed'):
            queryset = queryset.prefetch_related('activity_rates__activity')
            
        return queryset.order_by('name')
    
    # views.py - Update the job_history action in MukadamViewSet

    @action(detail=True, methods=['get'])
    def job_history(self, request, pk=None):
        """Get complete job history for a mukadam - including all jobs they were notified about"""
        mukadam = self.get_object()
        
        # Get all jobs where this mukadam has an interest record (was notified)
        interest_records = MukadamInterest.objects.filter(
            mukadam=mukadam
        ).select_related('job', 'job__farmer', 'job__activity').order_by('-job__requested_date')
        
        job_data = []
        for interest in interest_records:
            job = interest.job
            job_data.append({
                'id': str(job.id),
                'farmer_name': job.farmer.name,
                'activity_name': job.activity.name,
                'farm_size_acres': float(job.farm_size_acres),
                'farmer_price_per_acre': float(job.farmer_price_per_acre),
                'your_price_per_acre': float(job.your_price_per_acre) if job.your_price_per_acre else None,
                'finalized_price': float(job.finalized_price) if job.finalized_price else None,
                'status': job.status,
                'requested_date': job.requested_date,
                'completed_at': job.completed_at,
                'location': job.location,
                'workers_needed': job.workers_needed,
                # Interest-specific fields
                'mukadam_response': {
                    'is_interested': interest.is_interested,
                    'response_status': interest.response_status,
                    'responded_at': interest.responded_at,
                    'was_assigned': job.finalized_mukadam_id == mukadam.id if job.finalized_mukadam_id else False
                }
            })
        
        return Response({
            'mukadam': MukadamDetailSerializer(mukadam).data,
            'jobs': job_data,
            'summary': {
                'total_notified': len(job_data),
                'interested': sum(1 for j in job_data if j['mukadam_response']['is_interested']),
                'won': sum(1 for j in job_data if j['mukadam_response']['was_assigned']),
                'pending': sum(1 for j in job_data if j['mukadam_response']['response_status'] == 'pending'),
                'declined': sum(1 for j in job_data if j['mukadam_response']['response_status'] == 'declined')
            }
        })
    
    # views.py - Add this new action to MukadamViewSet

    @action(detail=True, methods=['get'])
    def detailed_stats(self, request, pk=None):
        """
        Get comprehensive statistics for a mukadam
        GET /api/mukadams/{id}/detailed_stats/
        """
        mukadam = self.get_object()
        
        # All interest records
        all_interests = MukadamInterest.objects.filter(mukadam=mukadam)
        
        # Jobs actually won/assigned
        won_jobs = Job.objects.filter(finalized_mukadam=mukadam)
        completed_jobs = won_jobs.filter(status='completed')
        
        # Calculate earnings
        total_earnings = sum(
            (job.finalized_price or 0) * job.farm_size_acres 
            for job in completed_jobs
        )
        
        # Response rate
        total_notified = all_interests.count()
        responded = all_interests.exclude(response_status='pending').count()
        response_rate = (responded / total_notified * 100) if total_notified > 0 else 0
        
        # Win rate (of jobs they showed interest in, how many did they win?)
        interested_count = all_interests.filter(is_interested=True).count()
        win_rate = (won_jobs.count() / interested_count * 100) if interested_count > 0 else 0
        
        return Response({
            'mukadam': MukadamDetailSerializer(mukadam).data,
            'job_statistics': {
                'total_notified': total_notified,
                'pending_responses': all_interests.filter(response_status='pending').count(),
                'showed_interest': interested_count,
                'declined': all_interests.filter(response_status='declined').count(),
                'won_jobs': won_jobs.count(),
                'active_jobs': won_jobs.filter(status__in=['finalized', 'assigned', 'in_progress']).count(),
                'completed_jobs': completed_jobs.count(),
            },
            'performance_metrics': {
                'response_rate_percent': round(response_rate, 2),
                'win_rate_percent': round(win_rate, 2),
                'total_earnings': float(total_earnings),
                'avg_job_value': float(total_earnings / completed_jobs.count()) if completed_jobs.count() > 0 else 0,
            },
            'recent_activity': {
                'last_30_days': {
                    'notified': all_interests.filter(
                        created_at__gte=timezone.now() - timezone.timedelta(days=30)
                    ).count(),
                    'won': won_jobs.filter(
                        finalized_at__gte=timezone.now() - timezone.timedelta(days=30)
                    ).count(),
                }
            }
        })
    
    @action(detail=True, methods=['get'])
    def current_jobs(self, request, pk=None):
        """
        Get current active jobs for a mukadam
        GET /api/mukadams/{id}/current_jobs/
        """
        mukadam = self.get_object()
        active_jobs = Job.objects.filter(
            finalized_mukadam=mukadam,
            status__in=['finalized', 'in_progress']
        ).order_by('requested_date')
        
        serializer = JobSerializer(active_jobs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def performance_stats(self, request, pk=None):
        """
        Get performance statistics for a mukadam
        GET /api/mukadams/{id}/performance_stats/
        """
        mukadam = self.get_object()
        
        # Get all jobs for this mukadam
        all_jobs = Job.objects.filter(finalized_mukadam=mukadam)
        completed_jobs = all_jobs.filter(status='completed')
        
        # Calculate statistics
        total_jobs = all_jobs.count()
        completed_count = completed_jobs.count()
        completion_rate = (completed_count / total_jobs * 100) if total_jobs > 0 else 0
        
        total_earnings = sum(
            job.finalized_price * job.farm_size_acres 
            for job in completed_jobs 
            if job.finalized_price
        )
        
        avg_price_per_acre = (
            completed_jobs.aggregate(avg_price=models.Avg('finalized_price'))['avg_price'] or 0
        )
        
        # Recent performance (last 3 months)
        from datetime import datetime, timedelta
        three_months_ago = datetime.now().date() - timedelta(days=90)
        recent_jobs = completed_jobs.filter(completed_at__gte=three_months_ago)
        
        return Response({
            'mukadam': MukadamSerializer(mukadam).data,
            'statistics': {
                'total_jobs': total_jobs,
                'completed_jobs': completed_count,
                'completion_rate': round(completion_rate, 2),
                'total_earnings': round(total_earnings, 2),
                'avg_price_per_acre': round(avg_price_per_acre, 2),
                'recent_jobs_3_months': recent_jobs.count(),
                'active_jobs': all_jobs.filter(status__in=['finalized', 'in_progress']).count()
            }
        })

    @action(detail=False, methods=['get'])
    def available_for_date(self, request):
        """
        Get mukadams available for a specific date
        GET /api/mukadams/available_for_date/?date=2024-03-15
        """
        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {"error": "date parameter is required (YYYY-MM-DD format)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find mukadams who don't have jobs on that date
        busy_mukadams = Job.objects.filter(
            requested_date=target_date,
            status__in=['finalized', 'in_progress']
        ).values_list('finalized_mukadam_id', flat=True)
        
        available_mukadams = Mukadam.objects.filter(
            is_active=True
        ).exclude(id__in=busy_mukadams)
        
        serializer = MukadamSerializer(available_mukadams, many=True)
        return Response({
            'date': date_str,
            'available_mukadams': serializer.data,
            'total_available': len(serializer.data)
        })
    
    @action(detail=True, methods=['post'], url_path='save-fcm-token')
    def save_fcm_token(self, request, pk=None):
        """Save FCM token from Flutter app"""
        try:
            mukadam = self.get_object()
            
            serializer = SaveFCMTokenSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=400)
            
            # Save token
            fcm_token = serializer.validated_data['fcm_token']
            mukadam.fcm_token = fcm_token
            mukadam.fcm_token_updated_at = timezone.now()
            mukadam.save()
            
            print(f"✅ FCM token saved for {mukadam.name}")
            
            return Response({
                "message": "FCM token saved",
                "mukadam_id": str(mukadam.id)
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class MukadamBidViewSet(viewsets.ModelViewSet):
    queryset = MukadamBid.objects.all()
    serializer_class = MukadamBidSerializer
    # def _send_websocket_update(self, update_type, data):
    #     """Send real-time update via WebSocket"""
    #     channel_layer = get_channel_layer()
    #     if channel_layer:
    #         async_to_sync(channel_layer.group_send)(
    #             'job_updates',
    #             {
    #                 'type': update_type,
    #                 'data': data
    #             }
    #         )

    # Update your submit_bid function in views.py
    @action(detail=False, methods=['post'])
    def submit_bid(self,request):
        try:
            bid_data = request.data
            
            # Validate required fields
            required_fields = ['job', 'mukadam', 'bid_price_per_acre']
            missing_fields = [field for field in required_fields if not bid_data.get(field)]
            
            if missing_fields:
                return Response({
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get job and mukadam
            try:
                job = get_object_or_404(Job, id=bid_data['job'])
                mukadam = get_object_or_404(Mukadam, id=bid_data['mukadam'])
            except Exception as e:
                return Response({
                    "error": f"Job or Mukadam not found: {str(e)}"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check job status
            if job.status not in ['bidding', 'assigned']:
                return Response({
                    "error": f"Job not accepting bids. Current status: {job.status}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ✅ Check if bid already exists
            existing_bid = MukadamBid.objects.filter(job=job, mukadam=mukadam).first()
            
            if existing_bid:
                # Update existing bid
                existing_bid.status = 'interested'
                existing_bid.bid_price_per_acre = bid_data['bid_price_per_acre']
                existing_bid.estimated_duration_hours = bid_data.get('estimated_duration_hours')
                existing_bid.comments = bid_data.get('comments', '')
                existing_bid.responded_at = timezone.now()
                existing_bid.save()
                
                bid = existing_bid
                action = "updated"
                
                print(f"✅ Updated existing bid for {mukadam.name}")
                
            else:
                # Create new bid
                bid = MukadamBid.objects.create(
                    job=job,
                    mukadam=mukadam,
                    status='interested',
                    bid_price_per_acre=bid_data['bid_price_per_acre'],
                    estimated_duration_hours=bid_data.get('estimated_duration_hours'),
                    comments=bid_data.get('comments', ''),
                    responded_at=timezone.now()
                )
                
                action = "created"
                
                print(f"✅ Created new bid for {mukadam.name}")
            
            # Get bid summary
            all_bids = MukadamBid.objects.filter(job=job)
            interested_bids = all_bids.filter(status='interested').order_by('bid_price_per_acre')
            
            response_data = {
                "status": "success",
                "message": f"Bid {action} successfully",
                "action": action,  # ✅ Tell them if it was created or updated
                "bid": {
                    "id": str(bid.id),
                    "job_id": str(job.id),
                    "mukadam_name": mukadam.name,
                    "bid_price_per_acre": float(bid.bid_price_per_acre),
                    "estimated_duration_hours": bid.estimated_duration_hours,
                    "comments": bid.comments,
                    "submitted_at": bid.responded_at,
                    "status": bid.status
                },
                "job_info": {
                    "farmer_name": job.farmer.name,
                    "activity": job.activity.name,
                    "farm_size_acres": float(job.farm_size_acres),
                    "location": job.location
                },
                "bidding_summary": {
                    "total_bids": all_bids.count(),
                    "interested_bids": interested_bids.count(),
                    "your_rank": list(interested_bids.values_list('id', flat=True)).index(bid.id) + 1 if interested_bids else 1,
                    "lowest_bid": float(interested_bids.first().bid_price_per_acre) if interested_bids else None
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Bid submission failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=True, methods=['post'])
    def cancel_bid(self, request, pk=None):
        """
        Mukadam cancels their bid
        POST /api/bids/{id}/cancel_bid/
        """
        bid = self.get_object()
        
        if bid.status == 'selected':
            return Response(
                {"error": "Cannot cancel a selected bid"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bid.status = 'cancelled'
        bid.save()
        
        return Response({"message": "Bid cancelled successfully"})
 
# views.py (replace your MukadamJobViewSet implementation with this)
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import Job, Mukadam, MukadamInterest
import json

class MukadamJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API specifically for Mukadam App Team
    Shows jobs with company pricing, assignment status, and history
    """

    @action(detail=False, methods=['get'])
    def opportunities(self, request):
        """
        GET /api/mukadam-jobs/opportunities/
        Get job opportunities for mukadams with company pricing
        """
        jobs = Job.objects.filter(
            status__in=['priced', 'notified', 'assigned', 'completed']
        ).select_related(
            'farmer', 'activity', 'assigned_mukadam', 'finalized_mukadam'
        ).prefetch_related(
            'interests__mukadam'
        ).order_by('-confirmed_at')

        job_opportunities = []

        for job in jobs:
            try:
                # ✅ Use response_status instead of is_interested
                all_interests = job.interests.all()
                interested_count = all_interests.filter(response_status='interested').count()
                declined_count = all_interests.filter(response_status='declined').count()
                pending_count = all_interests.filter(response_status='pending').count()

                assigned_muk = job.assigned_mukadam or job.finalized_mukadam

                assigned_info = None
                if assigned_muk:
                    assigned_info = {
                        'mukadam_id': str(assigned_muk.id),
                        'mukadam_name': assigned_muk.name,
                        'mukadam_phone': assigned_muk.phone,
                        'assigned_at': job.assigned_at.isoformat() if getattr(job, 'assigned_at', None) else None
                    }

                rate_per_acre = float(job.your_price_per_acre or 0)
                farm_size = float(job.farm_size_acres or 0)
                total_amount = rate_per_acre * farm_size

                created_ts = getattr(job, 'created_at', None) or getattr(job, 'confirmed_at', None)
                updated_ts = getattr(job, 'updated_at', None)

                opportunity = {
                    'job_id': str(job.id),
                    'job_reference': f"JOB-{str(job.id)[:8].upper()}",
                    'farmer': {
                        'name': job.farmer.name,
                        'location': job.location,
                        'village': getattr(job.farmer, 'village', job.location)
                    },
                    'work': {
                        'activity': job.activity.name,
                        'farm_size_acres': farm_size,
                        'workers_needed': job.workers_needed,
                        'scheduled_date': str(job.requested_date),
                        'scheduled_time': str(job.requested_time) if job.requested_time else "Morning",
                        'location': job.location,
                        'special_notes': job.notes or "",
                        'team_requirements': f"{job.workers_needed} workers required" 
                    },
                    'pricing': {
                        'rate_per_acre': rate_per_acre,
                        'total_amount': total_amount,
                        'currency': 'INR'
                    },
                    'status': {
                        'current_status': job.status,
                        'is_available': job.status in ['priced', 'notified'],
                        'is_assigned': job.status == 'assigned',
                        'is_completed': job.status == 'completed',
                        'status_display': self._get_status_display(job.status)
                    },
                    'assignment': assigned_info,
                    'responses': {
                        'total_notified': all_interests.count(),
                        'interested': interested_count,
                        'declined': declined_count,
                        'pending': pending_count,
                        'competition_level': self._get_competition_level_simple(interested_count)
                    },
                    'actions': {
                        'respond_url': f"/api/jobs/{job.id}/respond/",
                        'details_url': f"/api/mukadam-jobs/{job.id}/details/"
                    },
                    'created_at': created_ts.isoformat() if created_ts else None,
                    'updated_at': updated_ts.isoformat() if updated_ts else None
                }

                job_opportunities.append(opportunity)

            except Exception as e:
                print(f"❌ Error building opportunity for job {job.id}: {e}")
                continue

        summary = {
            'total_jobs': len(job_opportunities),
            'available_jobs': len([j for j in job_opportunities if j['status']['is_available']]),
            'assigned_jobs': len([j for j in job_opportunities if j['status']['is_assigned']]),
            'completed_jobs': len([j for j in job_opportunities if j['status']['is_completed']]),
        }

        return Response({
            'summary': summary,
            'opportunities': job_opportunities,
            'last_updated': timezone.now().isoformat()
        })

    def _get_status_display(self, status):
        status_map = {
            'priced': 'Available for Bidding',
            'notified': 'Awaiting Responses',
            'assigned': 'Assigned to Mukadam',
            'completed': 'Job Completed'
        }
        return status_map.get(status, status.title())

    def _get_competition_level_simple(self, interested_count):
        if interested_count >= 5:
            return 'High'
        elif interested_count >= 2:
            return 'Medium'
        elif interested_count >= 1:
            return 'Low'
        else:
            return 'No Interest Yet'

    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        try:
            job = Job.objects.select_related(
                'farmer', 'activity', 'assigned_mukadam', 'finalized_mukadam'
            ).prefetch_related(
                'interests__mukadam'
            ).get(id=pk)

            response_details = []
            for interest in job.interests.all():
                # ✅ Use response_status directly
                response_details.append({
                    'mukadam': {
                        'id': str(interest.mukadam.id),
                        'name': interest.mukadam.name,
                        'phone': interest.mukadam.phone,
                        'location': interest.mukadam.location,
                        'team_size': interest.mukadam.number_of_labourers
                    },
                    'response': {
                        'is_interested': interest.is_interested,
                        'responded_at': interest.responded_at.isoformat() if interest.responded_at else None,
                        'status': interest.response_status  # ✅ Use the field directly
                    }
                })

            job_details = {
                'job_id': str(job.id),
                'job_reference': f"JOB-{str(job.id)[:8].upper()}",
                'farmer': {
                    'name': job.farmer.name,
                    'phone': job.farmer.phone,
                    'location': job.location,
                    'village': getattr(job.farmer, 'village', job.location)
                },
                'work_details': {
                    'activity': job.activity.name,
                    'farm_size_acres': float(job.farm_size_acres),
                    'scheduled_date': str(job.requested_date),
                    'scheduled_time': str(job.requested_time) if job.requested_time else "Morning",
                    'location': job.location,
                    'special_instructions': job.notes or "",
                    'estimated_duration': self._estimate_duration(job)
                },
                'pricing': {
                    'rate_per_acre': float(job.your_price_per_acre or 0),
                    'total_amount': float((job.your_price_per_acre or 0) * job.farm_size_acres),
                    'currency': 'INR',
                    'payment_terms': 'Payment upon completion verification'
                },
                'status': {
                    'current_status': job.status,
                    'is_available': job.status in ['priced', 'notified'],
                    'is_assigned': job.status == 'assigned',
                    'assigned_mukadam': {
                        'name': job.assigned_mukadam.name,
                        'phone': job.assigned_mukadam.phone
                    } if job.assigned_mukadam else None
                },
                'responses': response_details,
                'timeline': self._get_job_timeline(job)
            }

            return Response(job_details)
        except Job.DoesNotExist:
            return Response({'error': 'Job not found'}, status=404)
        except Exception as e:
            print(f"❌ Error in details(): {e}")
            return Response({'error': str(e)}, status=500)
 
    def _estimate_duration(self, job):
        """Estimate job duration"""
        activity_hours = {
            'pruning': 3,
            'harvesting': 4,
            'spraying': 1.5,
            'tying': 2
        }
        
        base_hours = activity_hours.get(job.activity.name.lower(), 2.5)
        total_hours = base_hours * float(job.farm_size_acres)
        
        return {
            'estimated_hours': round(total_hours, 1),
            'estimated_days': max(1, round(total_hours / 8))
        }
    
    def _get_job_timeline(self, job):
        """Get job status timeline"""
        timeline = []
        
        if job.confirmed_at:
            timeline.append({
                'status': 'Price Set',
                'timestamp': job.confirmed_at.isoformat(),
                'description': f'Company set rate: ₹{job.your_price_per_acre}/acre'
            })
        
        if job.status == 'notified':
            timeline.append({
                'status': 'Mukadams Notified',
                'timestamp': timezone.now().isoformat(),
                'description': 'Job opportunity sent to mukadams'
            })
        
        if job.assigned_at:
            timeline.append({
                'status': 'Job Assigned',
                'timestamp': job.assigned_at.isoformat(),
                'description': f'Assigned to {job.assigned_mukadam.name}'
            })
        
        return timeline
# In views.py - ADD new ViewSet for individual mukadam details
class MukadamProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for individual Mukadam profile, statistics, and performance
    """
    
    @action(detail=True, methods=['get'])
    def profile(self, request, pk=None):
        """
        GET /api/mukadamprofile/{mukadam_id}/profile/
        Get complete mukadam profile with performance statistics
        """
        try:
            mukadam = Mukadam.objects.get(id=pk)
            
            # Get all job interests/assignments for this mukadam
            all_interests = MukadamInterest.objects.filter(mukadam=mukadam)
            
            # Calculate statistics
            total_notified = all_interests.count()
            total_responded = all_interests.filter(responded_at__isnull=False).count()
            total_interested = all_interests.filter(is_interested=True).count()
            total_declined = all_interests.filter(is_interested=False).count()
            total_assigned = Job.objects.filter(assigned_mukadam=mukadam).count()
            total_completed = Job.objects.filter(assigned_mukadam=mukadam, status='completed').count()
            
            # Calculate earnings
            completed_jobs = Job.objects.filter(assigned_mukadam=mukadam, status='completed')
            total_earnings = sum(
                float(job.your_price_per_acre) * float(job.farm_size_acres) 
                for job in completed_jobs if job.your_price_per_acre
            )
            
            # Get recent activity (last 30 days)
            from datetime import datetime, timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_interests = all_interests.filter(created_at__gte=thirty_days_ago)
            recent_assignments = Job.objects.filter(
                assigned_mukadam=mukadam, 
                assigned_at__gte=thirty_days_ago
            )
            
            # Performance metrics
            response_rate = (total_responded / total_notified * 100) if total_notified > 0 else 0
            success_rate = (total_assigned / total_interested * 100) if total_interested > 0 else 0
            completion_rate = (total_completed / total_assigned * 100) if total_assigned > 0 else 0
            
            # Average job value
            avg_job_value = total_earnings / total_completed if total_completed > 0 else 0
            
            profile_data = {
                # Basic Info
                'mukadam_info': {
                    'id': str(mukadam.id),
                    'name': mukadam.name,
                    'phone': mukadam.phone,
                    'location': mukadam.location,
                    'team_size': mukadam.number_of_labourers,
                    'is_active': mukadam.is_active,
                    'joined_date': mukadam.created_at.isoformat() if hasattr(mukadam, 'created_at') else None
                },
                
                # Job Statistics
                'job_statistics': {
                    'total_notified': total_notified,
                    'total_responded': total_responded,
                    'total_interested': total_interested,
                    'total_declined': total_declined,
                    'total_assigned': total_assigned,
                    'total_completed': total_completed,
                    'jobs_in_progress': total_assigned - total_completed
                },
                
                # Financial Summary
                'earnings': {
                    'total_earnings': round(total_earnings, 2),
                    'average_job_value': round(avg_job_value, 2),
                    'completed_jobs_count': total_completed,
                    'pending_payments': self._calculate_pending_payments(mukadam),
                    'currency': 'INR'
                },
                
                # Performance Metrics
                'performance': {
                    'response_rate': round(response_rate, 1),
                    'success_rate': round(success_rate, 1),
                    'completion_rate': round(completion_rate, 1),
                    'reliability_score': self._calculate_reliability_score(mukadam),
                    'performance_grade': self._get_performance_grade(response_rate, success_rate, completion_rate)
                },
                
                # Recent Activity (Last 30 days)
                'recent_activity': {
                    'jobs_notified': recent_interests.count(),
                    'jobs_assigned': recent_assignments.count(),
                    'recent_earnings': sum(
                        float(job.your_price_per_acre) * float(job.farm_size_acres) 
                        for job in recent_assignments.filter(status='completed') 
                        if job.your_price_per_acre
                    )
                },
                
                # Activity Breakdown
                'activity_breakdown': self._get_activity_breakdown(mukadam),
                
                # Monthly Performance
                'monthly_summary': self._get_monthly_summary(mukadam),
                
                # Current Status
                'current_status': self._get_current_status(mukadam)
            }
            
            return Response(profile_data)
            
        except Mukadam.DoesNotExist:
            return Response({'error': 'Mukadam not found'}, status=404)
    

    def _calculate_pending_payments(self, mukadam):
        """Calculate pending payments for completed but unpaid jobs"""
        # Assuming you track payment status
        completed_unpaid = Job.objects.filter(
            assigned_mukadam=mukadam, 
            status='completed'
            # Add payment_status='pending' when you implement payment tracking
        )
        
        pending_amount = sum(
            float(job.your_price_per_acre) * float(job.farm_size_acres) 
            for job in completed_unpaid if job.your_price_per_acre
        )
        
        return {
            'amount': round(pending_amount, 2),
            'jobs_count': completed_unpaid.count()
        }
    
    def _calculate_reliability_score(self, mukadam):
        """Calculate reliability score based on various factors"""
        # You can customize this based on your criteria
        recent_jobs = Job.objects.filter(
            assigned_mukadam=mukadam,
            assigned_at__gte=timezone.now() - timedelta(days=90)
        )
        
        if not recent_jobs.exists():
            return 0
        
        completed = recent_jobs.filter(status='completed').count()
        total = recent_jobs.count()
        
        base_score = (completed / total) * 100 if total > 0 else 0
        
        # Bonus for quick responses
        quick_responses = MukadamInterest.objects.filter(
            mukadam=mukadam,
            responded_at__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=90)
        ).filter(
            responded_at__lte=models.F('created_at') + timedelta(hours=24)
        ).count()
        
        total_opportunities = MukadamInterest.objects.filter(
            mukadam=mukadam,
            created_at__gte=timezone.now() - timedelta(days=90)
        ).count()
        
        response_bonus = (quick_responses / total_opportunities * 10) if total_opportunities > 0 else 0
        
        return round(min(100, base_score + response_bonus), 1)
    
    def _get_performance_grade(self, response_rate, success_rate, completion_rate):
        """Get letter grade based on performance"""
        avg_score = (response_rate + success_rate + completion_rate) / 3
        
        if avg_score >= 90:
            return 'A+'
        elif avg_score >= 80:
            return 'A'
        elif avg_score >= 70:
            return 'B'
        elif avg_score >= 60:
            return 'C'
        else:
            return 'D'
    
    def _get_activity_breakdown(self, mukadam):
        """Get breakdown by activity type"""
        from django.db.models import Count
        
        activity_stats = Job.objects.filter(
            assigned_mukadam=mukadam
        ).values(
            'activity__name'
        ).annotate(
            count=Count('id')
        )
        
        breakdown = []
        for stat in activity_stats:
            # Calculate earnings for this activity
            activity_jobs = Job.objects.filter(
                assigned_mukadam=mukadam,
                activity__name=stat['activity__name'],
                status='completed'
            )
            
            earnings = sum(
                float(job.your_price_per_acre) * float(job.farm_size_acres) 
                for job in activity_jobs if job.your_price_per_acre
            )
            
            breakdown.append({
                'activity': stat['activity__name'],
                'jobs_assigned': stat['count'],
                'jobs_completed': activity_jobs.count(),
                'total_earnings': round(earnings, 2)
            })
        
        return breakdown
    
    def _get_monthly_summary(self, mukadam):
        """Get last 6 months performance summary"""
        monthly_data = []
        
        for i in range(6):
            month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            month_interests = MukadamInterest.objects.filter(
                mukadam=mukadam,
                created_at__gte=month_start,
                created_at__lt=month_end
            )
            
            month_assignments = Job.objects.filter(
                assigned_mukadam=mukadam,
                assigned_at__gte=month_start,
                assigned_at__lt=month_end
            )
            
            month_completed = month_assignments.filter(status='completed')
            
            month_earnings = sum(
                float(job.your_price_per_acre) * float(job.farm_size_acres) 
                for job in month_completed if job.your_price_per_acre
            )
            
            monthly_data.append({
                'month': month_start.strftime('%B %Y'),
                'notified': month_interests.count(),
                'assigned': month_assignments.count(),
                'completed': month_completed.count(),
                'earnings': round(month_earnings, 2)
            })
        
        return monthly_data[:6]  # Return last 6 months
    
    def _get_current_status(self, mukadam):
        """Get current job status"""
        active_jobs = Job.objects.filter(
            assigned_mukadam=mukadam,
            status__in=['assigned']
        )
        
        pending_responses = MukadamInterest.objects.filter(
            mukadam=mukadam,
            responded_at__isnull=True,
            job__status='notified'
        )
        
        return {
            'active_jobs': active_jobs.count(),
            'pending_responses': pending_responses.count(),
            'is_available': mukadam.is_active and active_jobs.count() < 3,  # Customize availability logic
            'last_activity': self._get_last_activity(mukadam)
        }
    
    def _get_last_activity(self, mukadam):
        """Get last activity timestamp"""
        last_response = MukadamInterest.objects.filter(
            mukadam=mukadam,
            responded_at__isnull=False
        ).order_by('-responded_at').first()
        
        if last_response:
            return {
                'type': 'response',
                'timestamp': last_response.responded_at.isoformat(),
                'description': f"Responded to job opportunity"
            }
        
        return None
    
    @action(detail=True, methods=['get'])
    def job_history(self, request, pk=None):
        """
        GET /api/mukadams/{mukadam_id}/job_history/
        Get detailed job history for mukadam
        """
        try:
            mukadam = Mukadam.objects.get(id=pk)
            
            # Get all job interactions
            all_interests = MukadamInterest.objects.filter(
                mukadam=mukadam
            ).select_related('job__farmer', 'job__activity').order_by('-created_at')
            
            job_history = []
            
            for interest in all_interests:
                job = interest.job
                
                # Determine final status
                if job.assigned_mukadam == mukadam:
                    if job.status == 'completed':
                        final_status = 'completed'
                        earnings = float(job.your_price_per_acre) * float(job.farm_size_acres) if job.your_price_per_acre else 0
                    else:
                        final_status = 'assigned'
                        earnings = 0
                elif interest.is_interested:
                    final_status = 'interested_not_selected'
                    earnings = 0
                elif interest.responded_at:
                    final_status = 'declined'
                    earnings = 0
                else:
                    final_status = 'no_response'
                    earnings = 0
                
                history_item = {
                    'job_id': str(job.id),
                    'job_reference': f"JOB-{str(job.id)[:8].upper()}",
                    'farmer_name': job.farmer.name,
                    'activity': job.activity.name,
                    'location': job.location,
                    'farm_size': float(job.farm_size_acres),
                    'rate_offered': float(job.your_price_per_acre) if job.your_price_per_acre else None,
                    'total_value': float(job.your_price_per_acre) * float(job.farm_size_acres) if job.your_price_per_acre else None,
                    'scheduled_date': str(job.requested_date),
                    'notified_at': interest.created_at.isoformat() if hasattr(interest, 'created_at') else None,
                    'responded_at': interest.responded_at.isoformat() if interest.responded_at else None,
                    'was_interested': interest.is_interested,
                    'final_status': final_status,
                    'earnings': round(earnings, 2) if earnings > 0 else 0,
                    'assigned_date': job.assigned_at.isoformat() if job.assigned_at else None
                }
                
                job_history.append(history_item)
            
            return Response({
                'mukadam_id': str(mukadam.id),
                'mukadam_name': mukadam.name,
                'total_jobs': len(job_history),
                'job_history': job_history
            })
            
        except Mukadam.DoesNotExist:
            return Response({'error': 'Mukadam not found'}, status=404)
        
class WhatsAppNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WhatsAppNotification.objects.all()
    serializer_class = WhatsAppNotificationSerializer
    
    @action(detail=False, methods=['post'])
    def send_job_day_notifications(self, request):
        """
        Send WhatsApp notifications for jobs happening today
        POST /api/whatsapp/send_job_day_notifications/
        """
        today = timezone.now().date()
        
        # Get finalized jobs for today
        jobs_today = Job.objects.filter(
            requested_date=today,
            status='finalized'
        ).select_related('farmer', 'finalized_mukadam', 'activity')
        
        notifications_sent = 0
        
        for job in jobs_today:
            # Send to farmer
            farmer_message = self._generate_farmer_notification(job)
            farmer_notification = WhatsAppNotification.objects.create(
                job=job,
                recipient_type='farmer',
                recipient_phone=job.farmer.phone,
                message=farmer_message
            )
            
            # Send to mukadam
            mukadam_message = self._generate_mukadam_notification(job)
            mukadam_notification = WhatsAppNotification.objects.create(
                job=job,
                recipient_type='mukadam',
                recipient_phone=job.finalized_mukadam.phone,
                message=mukadam_message
            )
            
            # Actually send via WhatsApp API
            self._send_whatsapp_message(farmer_notification)
            self._send_whatsapp_message(mukadam_notification)
            
            notifications_sent += 2
        
        return Response({
            "message": f"Sent {notifications_sent} notifications for {len(jobs_today)} jobs",
            "jobs_today": len(jobs_today)
        })
    
    def _generate_farmer_notification(self, job):
        return f"""🌱 FarmOps - Work Starting Today!

Dear {job.farmer.name},

Your {job.activity.name} is scheduled to start today:

📅 Date: {job.requested_date.strftime('%B %d, %Y')}
⏰ Time: {job.requested_time.strftime('%I:%M %p')}
👷 Mukadam: {job.finalized_mukadam.name}
👥 Team Size: {job.finalized_mukadam.number_of_labourers} labourers
📱 Mukadam Contact: {job.finalized_mukadam.phone}
📏 Area: {job.farm_size_acres} acres

The team will arrive at the scheduled time. Please ensure:
✓ Farm access is clear
✓ Water available for workers
✓ Any specific instructions shared

For support, contact us at +91-XXXXXXXXXX

- FarmOps Team"""
    
    def _generate_mukadam_notification(self, job):
        return f"""🌱 FarmOps - Job Starting Today!

Dear {job.finalized_mukadam.name},

Your assigned work starts today:

👨‍🌾 Farmer: {job.farmer.name}
📱 Contact: {job.farmer.phone}
📍 Location: {job.location}, {job.farmer.village}
🔧 Work: {job.activity.name}
📏 Area: {job.farm_size_acres} acres
⏰ Time: {job.requested_time.strftime('%I:%M %p')}
💰 Rate: ₹{job.finalized_price}/acre

Please coordinate with the farmer and start on time.

- FarmOps Team"""
    
    def _send_whatsapp_message(self, notification):
        """Send actual WhatsApp message via API"""
        try:
            # Use your WhatsApp API (Twilio, Gupshup, etc.)
            # This is a placeholder - replace with actual implementation
            
            whatsapp_api_url = "https://your-whatsapp-api.com/send"
            payload = {
                "to": notification.recipient_phone,
                "message": notification.message
            }
            
            response = requests.post(whatsapp_api_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                notification.status = 'sent'
                notification.sent_at = timezone.now()
            else:
                notification.status = 'failed'
                
            notification.save()
            
        except Exception as e:
            notification.status = 'failed'
            notification.save()
            print(f"WhatsApp send failed: {str(e)}")
def index(request):
    return HttpResponse("Hello from assign app!")
