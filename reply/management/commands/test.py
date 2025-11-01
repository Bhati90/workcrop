from django.core.management.base import BaseCommand
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test Redis connection'

    def handle(self, *args, **options):
        try:
            # Test set
            cache.set('test_key', 'Hello Redis!', 30)
            
            # Test get
            value = cache.get('test_key')
            
            if value == 'Hello Redis!':
                self.stdout.write(self.style.SUCCESS('✅ Redis connection successful!'))
                self.stdout.write(f'Value: {value}')
            else:
                self.stdout.write(self.style.ERROR('❌ Redis read failed'))
            
            # Test delete
            cache.delete('test_key')
            
            # Verify delete
            if cache.get('test_key') is None:
                self.stdout.write(self.style.SUCCESS('✅ Redis delete successful!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Redis error: {str(e)}'))