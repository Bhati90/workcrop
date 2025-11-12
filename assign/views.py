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
            # self._send_websocket_update('job_status_changed', {
            #     'job_id': str(job.id),
            #     'message': 'New job confirmed',
            #     'status': job.status
            # })
            
            return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
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
        """Send simple Yes/No job notifications to selected mukadams"""
        try:
            job = self.get_object()
            mukadam_ids = request.data.get('mukadam_ids', [])
            
            if job.status != 'priced':
                return Response(
                    {"error": "Job must be priced first"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            notifications_sent = []
            
            for mukadam_id in mukadam_ids:
                mukadam = get_object_or_404(Mukadam, id=mukadam_id)
                
                # Create interest record
                interest, created = MukadamInterest.objects.get_or_create(
                    job=job,
                    mukadam=mukadam
                )
                
                # Send simple notification
                notification_data = {
                    "notification_type": "simple_job_offer",
                    "job_id": str(job.id),
                    "mukadam_id": str(mukadam.id),
                    "mukadam_name": mukadam.name,
                    
                    "job_details": {
                        "farmer_name": job.farmer.name,
                        "activity": job.activity.name,
                        "farm_size_acres": float(job.farm_size_acres),
                        "location": job.location,
                        "date": str(job.requested_date),
                        "your_price": float(job.your_price_per_acre),
                        "total_amount": float(job.your_price_per_acre * job.farm_size_acres)
                    },
                    
                    "response_required": {
                        "question": f"Are you interested in this {job.activity.name} job for ₹{job.your_price_per_acre}/acre?",
                        "options": ["YES", "NO"],
                        "respond_url": f"{settings.BASE_URL}/api/jobs/{job.id}/respond/"
                    }
                }
                
                # Send webhook
                try:
                    self._send_simple_notification(notification_data)
                    notifications_sent.append(mukadam.name)
                except Exception as e:
                    print(f"Failed to notify {mukadam.name}: {e}")
            
            job.status = 'notified'
            job.save()
            
            return Response({
                "message": f"Notified {len(notifications_sent)} mukadams",
                "notified": notifications_sent,
                "job_price": float(job.your_price_per_acre)
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
        
        mukadam = get_object_or_404(Mukadam, id=mukadam_id)
        
        # Update interest record
        interest = MukadamInterest.objects.get(job=job, mukadam=mukadam)
        interest.is_interested = interested
        interest.responded_at = timezone.now()
        interest.save()
        
        print(f"📝 {mukadam.name} responded: {'YES' if interested else 'NO'}")
        
        return Response({
            "message": f"Response recorded: {'Interested' if interested else 'Not interested'}",
            "mukadam": mukadam.name,
            "interested": interested
        })

    # Assign to one mukadam
    @action(detail=True, methods=['post'])
    def assign_final(self, request, pk=None):
        """Assign job to selected mukadam (from interested ones)"""
        
        job = self.get_object()
        mukadam_id = request.data.get('mukadam_id')
        
        mukadam = get_object_or_404(Mukadam, id=mukadam_id)
        
        # Check if they were interested
        interest = MukadamInterest.objects.get(job=job, mukadam=mukadam)
        if not interest.is_interested:
            return Response({"error": "This mukadam was not interested"}, status=400)
        
        # Assign job
        job.assigned_mukadam = mukadam
        job.status = 'assigned'
        job.assigned_at = timezone.now()
        job.save()
        
        # Notify assigned mukadam
        self._notify_assignment(job, mukadam)
        
        return Response({
            "message": f"Job assigned to {mukadam.name}",
            "mukadam": mukadam.name,
            "price": float(job.your_price_per_acre),
            "total": float(job.your_price_per_acre * job.farm_size_acres)
        })

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


# Add to views.py
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
        job.your_price_per_acre = your_price  # Add this field to model
        job.status = 'priced'  # New status
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

# Add this to your views.py
# Add this to your views.py in Django



# Update your submit_bid function in views.py
# @api_view(['POST'])
# def submit_bid(self,request):
#     try:
#         bid_data = request.data
        
#         # Validate required fields
#         required_fields = ['job', 'mukadam', 'bid_price_per_acre']
#         missing_fields = [field for field in required_fields if not bid_data.get(field)]
        
#         if missing_fields:
#             return Response({
#                 "error": f"Missing required fields: {', '.join(missing_fields)}"
#             }, status=status.HTTP_400_BAD_REQUEST)
        
#         # Get job and mukadam
#         try:
#             job = get_object_or_404(Job, id=bid_data['job'])
#             mukadam = get_object_or_404(Mukadam, id=bid_data['mukadam'])
#         except Exception as e:
#             return Response({
#                 "error": f"Job or Mukadam not found: {str(e)}"
#             }, status=status.HTTP_404_NOT_FOUND)
        
#         # Check job status
#         if job.status not in ['bidding', 'assigned']:
#             return Response({
#                 "error": f"Job not accepting bids. Current status: {job.status}"
#             }, status=status.HTTP_400_BAD_REQUEST)
        
#         # ✅ Check if bid already exists
#         existing_bid = MukadamBid.objects.filter(job=job, mukadam=mukadam).first()
        
#         if existing_bid:
#             # Update existing bid
#             existing_bid.status = 'interested'
#             existing_bid.bid_price_per_acre = bid_data['bid_price_per_acre']
#             existing_bid.estimated_duration_hours = bid_data.get('estimated_duration_hours')
#             existing_bid.comments = bid_data.get('comments', '')
#             existing_bid.responded_at = timezone.now()
#             existing_bid.save()
            
#             bid = existing_bid
#             action = "updated"
            
#             print(f"✅ Updated existing bid for {mukadam.name}")
            
#         else:
#             # Create new bid
#             bid = MukadamBid.objects.create(
#                 job=job,
#                 mukadam=mukadam,
#                 status='interested',
#                 bid_price_per_acre=bid_data['bid_price_per_acre'],
#                 estimated_duration_hours=bid_data.get('estimated_duration_hours'),
#                 comments=bid_data.get('comments', ''),
#                 responded_at=timezone.now()
#             )
            
#             action = "created"
            
#             print(f"✅ Created new bid for {mukadam.name}")
        
#         # Get bid summary
#         all_bids = MukadamBid.objects.filter(job=job)
#         interested_bids = all_bids.filter(status='interested').order_by('bid_price_per_acre')
        
#         response_data = {
#             "status": "success",
#             "message": f"Bid {action} successfully",
#             "action": action,  # ✅ Tell them if it was created or updated
#             "bid": {
#                 "id": str(bid.id),
#                 "job_id": str(job.id),
#                 "mukadam_name": mukadam.name,
#                 "bid_price_per_acre": float(bid.bid_price_per_acre),
#                 "estimated_duration_hours": bid.estimated_duration_hours,
#                 "comments": bid.comments,
#                 "submitted_at": bid.responded_at,
#                 "status": bid.status
#             },
#             "job_info": {
#                 "farmer_name": job.farmer.name,
#                 "activity": job.activity.name,
#                 "farm_size_acres": float(job.farm_size_acres),
#                 "location": job.location
#             },
#             "bidding_summary": {
#                 "total_bids": all_bids.count(),
#                 "interested_bids": interested_bids.count(),
#                 "your_rank": list(interested_bids.values_list('id', flat=True)).index(bid.id) + 1 if interested_bids else 1,
#                 "lowest_bid": float(interested_bids.first().bid_price_per_acre) if interested_bids else None
#             }
#         }
        
#         return Response(response_data, status=status.HTTP_200_OK)
        
#     except Exception as e:
#         return Response({
#             "error": f"Bid submission failed: {str(e)}"
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
