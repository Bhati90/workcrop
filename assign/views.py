from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import *
from .serializers import *
import requests
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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

class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    
    def _send_websocket_update(self, update_type, data):
        """Send real-time update via WebSocket"""
        try :
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'job_updates',
                    {
                        'type': update_type,
                        'data': data
                    }
                )
        except Exception as e:
        # Log the error but don't crash the request
            print(f"WebSocket update failed: {e}")
            pass 

    @action(detail=False, methods=['post'])
    def confirm_job(self, request):
        """
        Endpoint for team members to confirm a job
        POST /api/jobs/confirm_job/
        """
        serializer = JobCreateSerializer(data=request.data)
        if serializer.is_valid():
            job = serializer.save()
            
            changed_by_user = None
            if request.user.is_authenticated:
                changed_by_user = request.user
            # Log status change
            JobStatusHistory.objects.create(
                job=job,
                from_status='',
                to_status='confirmed',
                changed_by=changed_by_user,
                notes='Job confirmed by team member'
            )
            self._send_websocket_update('job_status_changed', {
                'job_id': str(job.id),
                'message': 'New job confirmed',
                'status': job.status
            })
            
            return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign_to_mukadams(self, request, pk=None):
        """
        Assign job to multiple mukadams for bidding
        POST /api/jobs/{id}/assign_to_mukadams/
        Body: {"mukadam_ids": ["uuid1", "uuid2", "uuid3"]}
        """
        job = self.get_object()
        
        if job.status != 'confirmed':
            return Response(
                {"error": "Job must be in confirmed status to assign"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        mukadam_ids = request.data.get('mukadam_ids', [])
        if not mukadam_ids:
            return Response(
                {"error": "At least one mukadam_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            # Create assignments
            assignments = []
            for mukadam_id in mukadam_ids:
                mukadam = get_object_or_404(Mukadam, id=mukadam_id, is_active=True)
                
                # Create assignment record
                assignment, created = JobAssignment.objects.get_or_create(
                    job=job,
                    mukadam=mukadam
                )
                if created:
                    assignments.append(assignment)
                    
                    # Create bid record
                    MukadamBid.objects.get_or_create(
                        job=job,
                        mukadam=mukadam,
                        defaults={'status': 'pending'}
                    )
            
            # Update job status
            job.status = 'assigned'
            job.save()

            changed_by_user = None
            if request.user.is_authenticated:
                changed_by_user = request.user
            
            # Log status change
            JobStatusHistory.objects.create(
                job=job,
                from_status='confirmed',
                to_status='assigned',
                changed_by=changed_by_user,
                notes=f'Assigned to {len(assignments)} mukadams'
            )
            
            # Send notifications to mukadams (API calls)
            self._notify_mukadams_about_job(job, [a.mukadam for a in assignments])
            
            # Update job status to bidding after notifications
            job.status = 'bidding'
            job.save()
            
            return Response({
                "message": f"Job assigned to {len(assignments)} mukadams",
                "assignments": len(assignments),
                "job_status": job.status
            })
            try:
                self._send_websocket_update('job_assigned', {
                    'job_id': str(job.id),
                    'message': f'Job assigned to {len(assignments)} mukadams',
                    'status': job.status
                })
            except Exception as e:
                print(f"WebSocket notification failed: {e}")
        
        
            return Response(response_data)
        except Exception as e:
            return Response(
                {"error": f"Failed to assign job: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _notify_mukadams_about_job(self, job, mukadams):
        """Send job notification to mukadams via API"""
        for mukadam in mukadams:
            try:
                # Prepare job data (without price)
                job_data = {
                    "job_id": str(job.id),
                    "farmer_name": job.farmer.name,
                    "activity": job.activity.name,
                    "farm_size_acres": float(job.farm_size_acres),
                    "location": job.location,
                    "requested_date": job.requested_date.isoformat(),
                    "requested_time": job.requested_time.isoformat(),
                    "notes": job.notes,
                    "farmer_phone": job.farmer.phone,
                    "farmer_village": job.farmer.village,
                }
                
                # Call mukadam's app API (replace with actual endpoint)
                api_url = f"https://mukadam-app-api.com/jobs/new"
                headers = {
                    "Authorization": f"Bearer {mukadam.api_token}",  # If you use auth
                    "Content-Type": "application/json"
                }
                
                response = requests.post(api_url, json=job_data, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # Mark as notified
                    assignment = JobAssignment.objects.get(job=job, mukadam=mukadam)
                    assignment.notified_at = timezone.now()
                    assignment.save()
                    
            except Exception as e:
                # Log error but don't fail the whole process
                print(f"Failed to notify mukadam {mukadam.name}: {str(e)}")
    
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
    
    @action(detail=True, methods=['post'])
    def finalize_mukadam(self, request, pk=None):
        """
        Finalize a mukadam for the job
        POST /api/jobs/{id}/finalize_mukadam/
        Body: {"bid_id": "uuid"}
        """
        job = self.get_object()
        bid_id = request.data.get('bid_id')
        
        if not bid_id:
            return Response(
                {"error": "bid_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bid = get_object_or_404(MukadamBid, id=bid_id, job=job, status='interested')
        
        # Update job
        job.finalized_mukadam = bid.mukadam
        job.finalized_price = bid.bid_price_per_acre
        job.status = 'finalized'
        job.finalized_at = timezone.now()
        job.save()
        
        # Update bid status
        bid.status = 'selected'
        bid.save()
        
        # Reject other bids
        job.bids.exclude(id=bid.id).update(status='rejected')
        
        changed_by_user = None
        if request.user.is_authenticated:
            changed_by_user = request.user
        # Log status change
        JobStatusHistory.objects.create(
            job=job,
            from_status='bidding',
            to_status='finalized',
            changed_by=changed_by_user,
            notes=f'Selected {bid.mukadam.name} at ₹{bid.bid_price_per_acre}/acre'
        )
        
        # Notify selected mukadam
        self._notify_mukadam_selection(job, bid.mukadam)
        
        return Response({
            "message": f"Job finalized with {bid.mukadam.name}",
            "mukadam": bid.mukadam.name,
            "price": bid.bid_price_per_acre,
            "job_status": job.status
        })
    
    def _notify_mukadam_selection(self, job, mukadam):
        """Notify mukadam that they were selected"""
        try:
            selection_data = {
                "job_id": str(job.id),
                "selected": True,
                "final_price": float(job.finalized_price),
                "farmer_contact": job.farmer.phone,
                "start_date": job.requested_date.isoformat(),
                "start_time": job.requested_time.isoformat()
            }
            
            api_url = f"https://mukadam-app-api.com/jobs/{job.id}/selection"
            response = requests.post(api_url, json=selection_data, timeout=10)
            
        except Exception as e:
            print(f"Failed to notify selection to {mukadam.name}: {str(e)}")

class MukadamBidViewSet(viewsets.ModelViewSet):
    queryset = MukadamBid.objects.all()
    serializer_class = MukadamBidSerializer
    def _send_websocket_update(self, update_type, data):
        """Send real-time update via WebSocket"""
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'job_updates',
                {
                    'type': update_type,
                    'data': data
                }
            )

    @action(detail=False, methods=['post'])
    def submit_bid(self, request):
        """
        Endpoint for mukadams to submit their bids
        POST /api/bids/submit_bid/
        """
        serializer = MukadamBidCreateSerializer(data=request.data)
        if serializer.is_valid():
            bid = serializer.save()
            
            # Check if all mukadams have responded
            job = bid.job
            total_assignments = job.assignments.count()
            responded_bids = job.bids.exclude(status='pending').count()
            
            response_data = MukadamBidSerializer(bid).data
            response_data['bidding_status'] = {
                'total_mukadams': total_assignments,
                'responses_received': responded_bids,
                'pending_responses': total_assignments - responded_bids
            }
            self._send_websocket_update('new_bid', {
                'job_id': str(bid.job.id),
                'message': f'{bid.mukadam.name} submitted bid',
                'bid_id': str(bid.id)
            })
            
            # ✅ FIXED: Single return statement
            return Response(response_data, status=status.HTTP_201_CREATED)
            
            
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
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

# Add this to your views.py

# Update views.py to support the enhanced features
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
    
    @action(detail=True, methods=['get'])
    def job_history(self, request, pk=None):
        """Get complete job history for a mukadam"""
        mukadam = self.get_object()
        jobs = Job.objects.filter(finalized_mukadam=mukadam).select_related('farmer', 'activity').order_by('-requested_date')
        
        job_data = []
        for job in jobs:
            job_data.append({
                'id': str(job.id),
                'farmer_name': job.farmer.name,
                'activity_name': job.activity.name,
                'farm_size_acres': job.farm_size_acres,
                'finalized_price': job.finalized_price,
                'status': job.status,
                'requested_date': job.requested_date,
                'completed_at': job.completed_at,
            })
        
        return Response({
            'mukadam': MukadamDetailSerializer(mukadam).data,
            'jobs': job_data
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
