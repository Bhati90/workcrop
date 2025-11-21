# your_app/management/commands/set_company_rates.py

from django.core.management.base import BaseCommand
from assign.models import Activity, CompanyActivityRate

class Command(BaseCommand):
    help = 'Set company activity rates'

    def handle(self, *args, **options):
        # Define your rates here (Activity UUID: Rate per acre)
        COMPANY_RATES = {
            # Pruning activities
            "09d5ed3f-6ead-4dad-b0d0-b8407153311e": 1200,  # Pruning - Cutting back vines
            "9fd06862-0127-43d5-8194-61bb092ecdf0": 1200,  # Pruning - Cutting back vines for new growth
            
            # Harvesting
            "626fd58e-db24-416c-9848-8bf7b0764442": 3500,  # Harvesting - Grape harvest
            
            # Berry Thinning
            "76161314-7bc6-4f85-a091-27b1772f2077": 2800,  # Berry Thinning
            
            # GA3 Spray
            "79867264-98df-431e-8e7f-29d60ab3ec62": 1800,  # Gibberellic Acid Spray
            
            # Tying activities
            "7b1a2da3-df20-4692-a10c-850ccf7bf6ca": 2200,  # Tying - Tying vines
            "e774ddc0-aa39-4029-afe9-d1a18a469aea": 2200,  # Tying - Tying vines to support structures
            
            # Spray
            "8ef2e35b-0515-4fed-b3ce-06b7501ef8ce": 1500,  # Spray - Pesticide/Fertilizer spray
        }

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for activity_id, rate in COMPANY_RATES.items():
            try:
                activity = Activity.objects.get(id=activity_id)
                
                # Create or update the rate
                rate_obj, created = CompanyActivityRate.objects.update_or_create(
                    activity=activity,
                    defaults={
                        'rate_per_acre': rate,
                        'is_active': True,
                        'notes': f'Standard company rate for {activity.name}'
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Created rate for {activity.name}: ₹{rate}/acre')
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'🔄 Updated rate for {activity.name}: ₹{rate}/acre')
                    )
                    
            except Activity.DoesNotExist:
                skipped_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ Activity not found: {activity_id}')
                )

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\n📊 Summary:'))
        self.stdout.write(f'  ✅ Created: {created_count}')
        self.stdout.write(f'  🔄 Updated: {updated_count}')
        self.stdout.write(f'  ❌ Skipped: {skipped_count}')
        self.stdout.write(f'  📝 Total: {created_count + updated_count + skipped_count}')
        self.stdout.write('='*50 + '\n')# your_app/management/commands/set_company_rates.py

from django.core.management.base import BaseCommand
from assign.models import Activity, CompanyActivityRate

class Command(BaseCommand):
    help = 'Set company activity rates'

    def handle(self, *args, **options):
        # Define your rates here (Activity UUID: Rate per acre)
        COMPANY_RATES = {
            # Pruning activities
            "09d5ed3f-6ead-4dad-b0d0-b8407153311e": 1200,  # Pruning - Cutting back vines
            "9fd06862-0127-43d5-8194-61bb092ecdf0": 1200,  # Pruning - Cutting back vines for new growth
            
            # Harvesting
            "626fd58e-db24-416c-9848-8bf7b0764442": 3500,  # Harvesting - Grape harvest
            
            # Berry Thinning
            "76161314-7bc6-4f85-a091-27b1772f2077": 2800,  # Berry Thinning
            
            # GA3 Spray
            "79867264-98df-431e-8e7f-29d60ab3ec62": 1800,  # Gibberellic Acid Spray
            
            # Tying activities
            "7b1a2da3-df20-4692-a10c-850ccf7bf6ca": 2200,  # Tying - Tying vines
            "e774ddc0-aa39-4029-afe9-d1a18a469aea": 2200,  # Tying - Tying vines to support structures
            
            # Spray
            "8ef2e35b-0515-4fed-b3ce-06b7501ef8ce": 1500,  # Spray - Pesticide/Fertilizer spray
        }

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for activity_id, rate in COMPANY_RATES.items():
            try:
                activity = Activity.objects.get(id=activity_id)
                
                # Create or update the rate
                rate_obj, created = CompanyActivityRate.objects.update_or_create(
                    activity=activity,
                    defaults={
                        'rate_per_acre': rate,
                        'is_active': True,
                        'notes': f'Standard company rate for {activity.name}'
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Created rate for {activity.name}: ₹{rate}/acre')
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'🔄 Updated rate for {activity.name}: ₹{rate}/acre')
                    )
                    
            except Activity.DoesNotExist:
                skipped_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ Activity not found: {activity_id}')
                )

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\n📊 Summary:'))
        self.stdout.write(f'  ✅ Created: {created_count}')
        self.stdout.write(f'  🔄 Updated: {updated_count}')
        self.stdout.write(f'  ❌ Skipped: {skipped_count}')
        self.stdout.write(f'  📝 Total: {created_count + updated_count + skipped_count}')
        self.stdout.write('='*50 + '\n')