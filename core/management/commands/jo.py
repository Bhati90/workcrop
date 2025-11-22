"""
Django Management Command to Import Jobs from External API

Usage:
    python manage.py import_jobs
    python manage.py import_jobs --url "https://api.example.com/jobs"
    python manage.py import_jobs --file data.json
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import datetime
import requests
import json
from decimal import Decimal
from typing import List, Dict, Any, Optional

from core.models import Job  # Replace 'your_app' with your actual app name


class Command(BaseCommand):
    help = 'Import jobs from external API or JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='API URL to fetch jobs from',
            default=None
        )
        parser.add_argument(
            '--file',
            type=str,
            help='JSON file path to import from',
            default=None
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username who is importing (defaults to first superuser)',
            default=None
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            help='Number of records to process in one batch',
            default=50
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing jobs if they exist (match by title and start_date)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting job import...'))
        
        # Get the user who is creating these jobs
        user = self.get_user(options['user'])
        if not user:
            self.stdout.write(self.style.ERROR('No user found for job creation'))
            return

        # Fetch data
        data = self.fetch_data(options['url'], options['file'])
        if not data:
            return

        # Process jobs
        stats = self.process_jobs(
            data, 
            user, 
            batch_size=options['batch_size'],
            update_existing=options['update']
        )
        
        # Print summary
        self.print_summary(stats)

    def get_user(self, username: Optional[str]) -> Optional[User]:
        """Get user for job creation"""
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'User {username} not found'))
        
        # Default to first superuser
        return User.objects.filter(is_superuser=True).first()

    def fetch_data(self, url: Optional[str], file_path: Optional[str]) -> Optional[List[Dict]]:
        """Fetch data from API or file"""
        if url:
            return self.fetch_from_api(url)
        elif file_path:
            return self.fetch_from_file(file_path)
        else:
            self.stdout.write(self.style.ERROR('Please provide either --url or --file'))
            return None

    def fetch_from_api(self, url: str) -> Optional[List[Dict]]:
        """Fetch data from API"""
        try:
            self.stdout.write(f'Fetching data from {url}...')
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different API response formats
            if isinstance(data, dict):
                if 'data' in data:
                    data = data['data']
                elif 'results' in data:
                    data = data['results']
                elif 'jobs' in data:
                    data = data['jobs']
            
            if not isinstance(data, list):
                self.stdout.write(self.style.ERROR('API response is not a list'))
                return None
            
            self.stdout.write(self.style.SUCCESS(f'Fetched {len(data)} jobs'))
            return data
            
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Error fetching from API: {e}'))
            return None
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Error parsing JSON: {e}'))
            return None

    def fetch_from_file(self, file_path: str) -> Optional[List[Dict]]:
        """Fetch data from JSON file"""
        try:
            self.stdout.write(f'Reading data from {file_path}...')
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different file formats
            if isinstance(data, dict):
                if 'data' in data:
                    data = data['data']
                elif 'results' in data:
                    data = data['results']
                elif 'jobs' in data:
                    data = data['jobs']
            
            if not isinstance(data, list):
                self.stdout.write(self.style.ERROR('File data is not a list'))
                return None
            
            self.stdout.write(self.style.SUCCESS(f'Loaded {len(data)} jobs'))
            return data
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return None
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Error parsing JSON file: {e}'))
            return None

    def process_jobs(
        self, 
        jobs_data: List[Dict], 
        user: User,
        batch_size: int = 50,
        update_existing: bool = False
    ) -> Dict[str, int]:
        """Process and create/update jobs"""
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }
        
        total = len(jobs_data)
        
        for i, job_data in enumerate(jobs_data, 1):
            try:
                # Process in batches with transactions
                if i % batch_size == 0:
                    self.stdout.write(f'Processing: {i}/{total}...')
                
                with transaction.atomic():
                    result = self.process_single_job(job_data, user, update_existing)
                    stats[result] += 1
                    
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(
                    self.style.ERROR(f'Error processing job {i}: {str(e)}')
                )
                continue
        
        return stats

    def process_single_job(
        self, 
        job_data: Dict[str, Any], 
        user: User,
        update_existing: bool
    ) -> str:
        """Process a single job record"""
        
        # Extract and clean data
        cleaned_data = self.clean_job_data(job_data)
        
        if not cleaned_data.get('title') or not cleaned_data.get('start_date'):
            return 'skipped'
        
        # Check if job exists
        existing_job = None
        if update_existing:
            existing_job = Job.objects.filter(
                title=cleaned_data['title'],
                start_date=cleaned_data['start_date']
            ).first()
        
        if existing_job:
            # Update existing job
            for key, value in cleaned_data.items():
                setattr(existing_job, key, value)
            existing_job.save()
            return 'updated'
        else:
            # Create new job
            cleaned_data['created_by'] = user
            Job.objects.create(**cleaned_data)
            return 'created'

    def clean_job_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and transform raw API data to Job model format"""
        
        # Handle different field name formats
        cleaned = {}
        
        # Title - required field
        cleaned['title'] = self.extract_field(
            raw_data, 
            ['title', 'job_title', 'name', 'job_name']
        )
        
        # Start date - required field
        start_date = self.extract_field(
            raw_data,
            ['start_date', 'startDate', 'date', 'scheduled_date']
        )
        cleaned['start_date'] = self.parse_datetime(start_date)
        
        # Plot details
        cleaned['plot_name'] = self.extract_field(
            raw_data,
            ['plot_name', 'plotName', 'field_name']
        )
        
        plot_area = self.extract_field(
            raw_data,
            ['plot_area', 'plotArea', 'area', 'field_area']
        )
        cleaned['plot_area'] = self.parse_decimal(plot_area)
        
        cleaned['plot_crop'] = self.extract_field(
            raw_data,
            ['plot_crop', 'plotCrop', 'crop', 'crop_name']
        )
        
        # Farmer details
        cleaned['farmer_name'] = self.extract_field(
            raw_data,
            ['farmer_name', 'farmerName', 'farmer', 'owner_name']
        )
        
        cleaned['farmer_phone'] = self.extract_field(
            raw_data,
            ['farmer_phone', 'farmerPhone', 'phone', 'contact', 'mobile']
        )
        
        cleaned['farmer_id'] = self.extract_field(
            raw_data,
            ['farmer_id', 'farmerId', 'fid']
        )
        
        # Location details
        cleaned['location'] = self.extract_field(
            raw_data,
            ['location', 'address', 'place']
        )
        
        cleaned['village'] = self.extract_field(
            raw_data,
            ['village', 'gaon', 'gram']
        )
        
        cleaned['taluka'] = self.extract_field(
            raw_data,
            ['taluka', 'tehsil', 'block']
        )
        
        cleaned['district'] = self.extract_field(
            raw_data,
            ['district', 'zilla']
        )
        
        # Job requirements
        fir_id = self.extract_field(
            raw_data,
            ['fir_id', 'firId', 'fid']
        )
        cleaned['fir_id'] = int(fir_id) if fir_id and str(fir_id).isdigit() else None
        
        cleaned['notes'] = self.extract_field(
            raw_data,
            ['notes', 'description', 'details', 'remarks']
        )
        
        cleaned['class_name'] = self.extract_field(
            raw_data,
            ['class_name', 'className', 'class', 'category']
        )
        
        # Workers required
        workers = self.extract_field(
            raw_data,
            ['workers_required', 'workersRequired', 'workers', 'labor_count', 'team_size']
        )
        cleaned['workers_required'] = int(workers) if workers and str(workers).isdigit() else 0
        
        # Status
        status = self.extract_field(
            raw_data,
            ['status', 'job_status', 'state']
        )
        cleaned['status'] = self.normalize_status(status)
        
        # All day flag
        all_day = self.extract_field(
            raw_data,
            ['all_day', 'allDay', 'full_day']
        )
        cleaned['all_day'] = self.parse_boolean(all_day)
        
        return cleaned

    def extract_field(self, data: Dict, field_names: List[str]) -> Any:
        """Extract field from data with multiple possible names"""
        for field_name in field_names:
            value = data.get(field_name)
            if value is not None and value != '':
                # Handle arrays - take first element
                if isinstance(value, list):
                    return value[0] if value else None
                return value
        return None

    def parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if not value:
            return timezone.now()  # Default to now if not provided
        
        if isinstance(value, datetime):
            return value
        
        # Handle string formats
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(str(value), fmt)
                # Make timezone aware
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt
            except ValueError:
                continue
        
        # If all parsing fails, return current time
        return timezone.now()

    def parse_decimal(self, value: Any) -> Optional[Decimal]:
        """Parse decimal value"""
        if not value:
            return None
        
        try:
            return Decimal(str(value))
        except:
            return None

    def parse_boolean(self, value: Any) -> bool:
        """Parse boolean value"""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ['true', 'yes', '1', 'on']
        
        return bool(value)

    def normalize_status(self, status: Any) -> str:
        """Normalize status to valid choices"""
        if not status:
            return 'pending'
        
        status = str(status).lower()
        
        status_mapping = {
            'pending': 'pending',
            'assigned': 'assigned',
            'in_progress': 'in_progress',
            'in progress': 'in_progress',
            'inprogress': 'in_progress',
            'ongoing': 'in_progress',
            'completed': 'completed',
            'complete': 'completed',
            'done': 'completed',
            'cancelled': 'cancelled',
            'canceled': 'cancelled',
        }
        
        return status_mapping.get(status, 'pending')

    def print_summary(self, stats: Dict[str, int]):
        """Print import summary"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Import Summary:'))
        self.stdout.write('='*50)
        self.stdout.write(f"Created:  {stats['created']}")
        self.stdout.write(f"Updated:  {stats['updated']}")
        self.stdout.write(f"Skipped:  {stats['skipped']}")
        self.stdout.write(f"Errors:   {stats['errors']}")
        self.stdout.write('='*50 + '\n')