from celery import shared_task
from django.utils import timezone
from datetime import datetime
import pytz
from .models import Job
from .utils.fcm_helper import send_push_notification


@shared_task(name='assign.tasks.send_daily_job_reminders')
def send_daily_job_reminders():
    """Runs daily at 9 AM IST - sends job reminders"""
    
    print("🔔 Running job reminders...")
    
    IST = pytz.timezone('Asia/Kolkata')
    today = timezone.now().astimezone(IST).date()
    
    # Get assigned jobs
    assigned_jobs = Job.objects.filter(
        status__in=['assigned', 'notified'],
        assigned_mukadam__isnull=False,
        requested_date__gte=today
    ).select_related('assigned_mukadam', 'farmer', 'activity')
    
    reminders_sent = 0
    
    for job in assigned_jobs:
        mukadam = job.assigned_mukadam
        
        if not mukadam.fcm_token:
            continue
        
        days_until = (job.requested_date - today).days
        
        # Send reminders based on days until job
        if days_until == 2:
            if send_reminder(job, mukadam, '2_days_before'):
                reminders_sent += 1
        elif days_until == 1:
            if send_reminder(job, mukadam, '1_day_before'):
                reminders_sent += 1
        elif days_until == 0:
            if send_reminder(job, mukadam, 'today'):
                reminders_sent += 1
    
    print(f"✅ Sent {reminders_sent} reminders")
    return {'success': True, 'reminders_sent': reminders_sent}


def send_reminder(job, mukadam, reminder_type):
    """Send reminder notification"""
    
    job_time = job.requested_time or datetime.strptime('08:00', '%H:%M').time()
    total_amount = float(job.your_price_per_acre * job.farm_size_acres)
    
    # Notification content
    if reminder_type == '2_days_before':
        title = "🔔 काम आठवण - 2 दिवस"
        body = f"{job.activity.name} - {job.location}\n2 दिवसांत काम. {job.workers_needed} कामगार तयार ठेवा!"
        
    elif reminder_type == '1_day_before':
        title = "⏰ काम आठवण - उद्या"
        body = f"{job.activity.name} - {job.location}\nउद्या {job_time.strftime('%I:%M %p')} वाजता. कामगार तयार ठेवा!"
        
    else:  # today
        title = "🚨 आज काम आहे!"
        body = f"{job.activity.name} - {job.location}\nआज {job_time.strftime('%I:%M %p')} वाजता!\nशेतकरी: {job.farmer.name}"
    
    # Send push notification
    success = send_push_notification(
        fcm_token=mukadam.fcm_token,
        title=title,
        body=body,
        data={
            "job_id": str(job.id),
            "type": "job_reminder",
            "reminder_type": reminder_type,
            "farmer_name": job.farmer.name,
            "farmer_phone": job.farmer.phone,
            "activity": job.activity.name,
            "location": job.location,
            "workers_needed": str(job.workers_needed),
            "total_amount": str(total_amount),
            "screen": "/assigned-jobs"
        }
    )
    
    if success:
        print(f"   ✅ Sent to {mukadam.name}")
    
    return success