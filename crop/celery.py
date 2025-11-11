import os
from celery import Celery

from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crop.settings')

app = Celery('farmops')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Schedule periodic tasks
app.conf.beat_schedule = {
    'send-daily-notifications': {
        'task': 'your_app.tasks.send_daily_job_notifications',
        'schedule': crontab(hour=6, minute=0),  # 6 AM daily
    },
    'send-reminder-notifications': {
        'task': 'your_app.tasks.send_job_reminder_notifications', 
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
}

app.conf.timezone = 'Asia/Kolkata'