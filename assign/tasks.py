from celery import shared_task
from django.utils import timezone
from .models import Job, WhatsAppNotification
from .views import WhatsAppNotificationViewSet
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_daily_job_notifications():
    """
    Celery task to send WhatsApp notifications for jobs happening today
    Run this task every morning at 6 AM
    """
    try:
        today = timezone.now().date()
        
        # Get finalized jobs for today that haven't been notified
        jobs_today = Job.objects.filter(
            requested_date=today,
            status='finalized',
            whatsapp_notifications__isnull=True
        ).select_related('farmer', 'finalized_mukadam', 'activity')
        
        notifications_sent = 0
        
        for job in jobs_today:
            try:
                # Use the existing WhatsApp notification logic
                viewset = WhatsAppNotificationViewSet()
                
                # Send to farmer
                farmer_message = viewset._generate_farmer_notification(job)
                farmer_notification = WhatsAppNotification.objects.create(
                    job=job,
                    recipient_type='farmer',
                    recipient_phone=job.farmer.phone,
                    message=farmer_message
                )
                viewset._send_whatsapp_message(farmer_notification)
                
                # Send to mukadam
                mukadam_message = viewset._generate_mukadam_notification(job)
                mukadam_notification = WhatsAppNotification.objects.create(
                    job=job,
                    recipient_type='mukadam',
                    recipient_phone=job.finalized_mukadam.phone,
                    message=mukadam_message
                )
                viewset._send_whatsapp_message(mukadam_notification)
                
                notifications_sent += 2
                logger.info(f"Sent notifications for job {job.id}")
                
            except Exception as e:
                logger.error(f"Failed to send notifications for job {job.id}: {str(e)}")
        
        logger.info(f"Daily notification task completed. Sent {notifications_sent} notifications for {len(jobs_today)} jobs")
        return f"Sent {notifications_sent} notifications"
        
    except Exception as e:
        logger.error(f"Daily notification task failed: {str(e)}")
        raise

@shared_task
def send_job_reminder_notifications():
    """
    Send reminder notifications 1 day before job date
    Run daily at 9 AM
    """
    try:
        tomorrow = timezone.now().date() + timezone.timedelta(days=1)
        
        jobs_tomorrow = Job.objects.filter(
            requested_date=tomorrow,
            status='finalized'
        ).select_related('farmer', 'finalized_mukadam')
        
        reminders_sent = 0
        
        for job in jobs_tomorrow:
            # Send reminder to farmer
            reminder_message = f"""🌱 FarmOps - Reminder

Dear {job.farmer.name},

Your {job.activity.name} is scheduled for TOMORROW:

📅 Date: {job.requested_date.strftime('%B %d, %Y')}
⏰ Time: {job.requested_time.strftime('%I:%M %p')}
👷 Mukadam: {job.finalized_mukadam.name}
📱 Contact: {job.finalized_mukadam.phone}

Please ensure farm access is ready.

- FarmOps Team"""
            
            WhatsAppNotification.objects.create(
                job=job,
                recipient_type='farmer',
                recipient_phone=job.farmer.phone,
                message=reminder_message
            )
            
            reminders_sent += 1
        
        logger.info(f"Sent {reminders_sent} reminder notifications")
        return f"Sent {reminders_sent} reminders"
        
    except Exception as e:
        logger.error(f"Reminder task failed: {str(e)}")
        raise