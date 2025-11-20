# your_app/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Job, CompanyActivityRate

@receiver(post_save, sender=Job)
def auto_price_job(sender, instance, created, **kwargs):
    """
    Automatically price a job when it's created or updated to 'confirmed' status
    if company rate is available
    """
    # Only auto-price if job is in 'confirmed' status and doesn't have price yet
    if instance.status == 'confirmed' and not instance.your_price_per_acre:
        try:
            # Get company rate for this activity
            company_rate = CompanyActivityRate.objects.get(
                activity=instance.activity,
                is_active=True
            )
            
            # Check if rate is within farmer's budget
            if company_rate.rate_per_acre <= instance.farmer_price_per_acre:
                # Update the job with auto-pricing
                Job.objects.filter(id=instance.id).update(
                    your_price_per_acre=company_rate.rate_per_acre,
                    status='priced'
                )
                
                print(f"✅ Auto-priced job {instance.id}: {instance.activity.name} at ₹{company_rate.rate_per_acre}/acre")
            else:
                print(f"⚠️ Company rate (₹{company_rate.rate_per_acre}) exceeds farmer budget (₹{instance.farmer_price_per_acre}) for job {instance.id}")
                
        except CompanyActivityRate.DoesNotExist:
            print(f"ℹ️ No company rate found for activity: {instance.activity.name}")