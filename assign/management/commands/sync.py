

from django.core.management.base import BaseCommand
from assign.models import Job, FarmerPlot, Farmer

class Command(BaseCommand):
    help = 'Sync farmer plots from existing jobs'

    def handle(self, *args, **options):
        self.stdout.write('Starting plot sync...')
        
        jobs = Job.objects.select_related('farmer', 'activity').all()
        created_count = 0
        updated_count = 0
        
        for job in jobs:
            if not job.farmer or not job.activity:
                continue
            
            plot, created = FarmerPlot.objects.get_or_create(
                farmer=job.farmer,
                activity_name=job.activity.name,
                defaults={
                    'acres': job.farm_size_acres,
                    'location': job.location or job.farmer.village,
                    'pruning_date': job.requested_date,
                    'notes': f"Auto-synced from jobs"
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created plot for {job.farmer.name} - {job.activity.name}')
            else:
                # Update if job has more acres
                if job.farm_size_acres > plot.acres:
                    plot.acres = job.farm_size_acres
                    plot.save()
                    updated_count += 1
                    self.stdout.write(f'Updated plot for {job.farmer.name} - {job.activity.name}')
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSync complete! Created: {created_count}, Updated: {updated_count}'
        ))
