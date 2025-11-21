# your_app/management/commands/autoprice_existing_jobs.py

from django.core.management.base import BaseCommand
from assign.models import Job, CompanyActivityRate

class Command(BaseCommand):
    help = 'Auto-price existing confirmed jobs based on company rates'

    def handle(self, *args, **options):
        # Get all confirmed jobs without pricing
        unpriced_jobs = Job.objects.filter(
            status='confirmed',
            your_price_per_acre__isnull=True
        )
        
        priced_count = 0
        skipped_count = 0
        
        self.stdout.write(f'Found {unpriced_jobs.count()} unpriced jobs\n')
        
        for job in unpriced_jobs:
            try:
                company_rate = CompanyActivityRate.objects.get(
                    activity=job.activity,
                    is_active=True
                )
                
                if company_rate.rate_per_acre <= job.farmer_price_per_acre:
                    job.your_price_per_acre = company_rate.rate_per_acre
                    job.status = 'priced'
                    job.save()
                    
                    priced_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Priced: {job.farmer.name} - {job.activity.name} at ₹{company_rate.rate_per_acre}/acre'
                        )
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ Skipped: {job.farmer.name} - {job.activity.name} (rate ₹{company_rate.rate_per_acre} > budget ₹{job.farmer_price_per_acre})'
                        )
                    )
                    
            except CompanyActivityRate.DoesNotExist:
                skipped_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ No rate: {job.farmer.name} - {job.activity.name}'
                    )
                )
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\n📊 Summary:'))
        self.stdout.write(f'  ✅ Auto-priced: {priced_count}')
        self.stdout.write(f'  ⚠️ Skipped: {skipped_count}')
        self.stdout.write('='*50 + '\n')