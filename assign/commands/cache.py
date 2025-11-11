# reply/management/commands/cache_vectors.py
from django.core.management.base import BaseCommand
from django.core.cache import cache
import json

class Command(BaseCommand):
    help = 'Load vector_database.json into Redis cache'

    def handle(self, *args, **kwargs):
        with open('vector_database.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i, chunk in enumerate(data):
            cache.set(f"rag:vector:chunk:{i}", chunk, timeout=None)
        cache.set(f"rag:vector:count", len(data), timeout=None)
        self.stdout.write(self.style.SUCCESS(f"Stored {len(data)} vector chunks in Redis"))
