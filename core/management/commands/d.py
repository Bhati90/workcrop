"""
Django Management Command to Import Mukkadam Data from Excel

Usage:
    python manage.py import_mukkadam_data path/to/mukkadam_data.xlsx

Features:
    - Imports Excel data into Mukkadam model
    - Detects and handles duplicates (based on mobile number)
    - Sets null for missing fields
    - Creates activity log for each import
    - Generates detailed import report
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import Mukkadam, ActivityLog  # CHANGE 'your_app' to your actual app name
import pandas as pd
import json
from datetime import datetime
import os


class Command(BaseCommand):
    help = 'Import Mukkadam data from Excel file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the Excel file')
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            help='Skip duplicate entries based on mobile number'
        )
        parser.add_argument(
            '--update-duplicates',
            action='store_true',
            help='Update existing records if duplicate mobile found'
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username of the user importing data (default: admin)'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        skip_duplicates = options['skip_duplicates']
        update_duplicates = options['update_duplicates']
        username = options['username']

        # Verify file exists
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        # Get or create the importing user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found. Please create this user first.'))
            return

        # Read Excel file
        self.stdout.write(self.style.SUCCESS(f'Reading file: {file_path}'))
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading file: {str(e)}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(df)} records in file'))

        # Statistics
        stats = {
            'total': len(df),
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'duplicates_found': 0
        }

        duplicate_report = []
        error_report = []

        # Process each row
        for idx, row in df.iterrows():
            try:
                with transaction.atomic():
                    mobile = self._clean_mobile(row.get('mobile_number'))
                    name = self._clean_string(row.get('full_name'))

                    # Skip if no name or mobile
                    if not name or not mobile:
                        stats['skipped'] += 1
                        self.stdout.write(
                            self.style.WARNING(f'Row {idx+1}: Skipped - Missing name or mobile')
                        )
                        continue

                    # Check for existing record
                    existing = Mukkadam.objects.filter(mobile_numbers__contains=mobile).first()

                    if existing:
                        stats['duplicates_found'] += 1
                        duplicate_report.append({
                            'row': idx + 1,
                            'name': name,
                            'mobile': mobile,
                            'village': self._clean_string(row.get('village')),
                            'existing_id': existing.id
                        })

                        if skip_duplicates:
                            stats['skipped'] += 1
                            self.stdout.write(
                                self.style.WARNING(f'Row {idx+1}: Skipped duplicate - {name} ({mobile})')
                            )
                            continue
                        elif update_duplicates:
                            mukkadam = existing
                            action = 'updated'
                            stats['updated'] += 1
                        else:
                            # Create anyway (but log as duplicate)
                            mukkadam = Mukkadam()
                            action = 'imported'
                            stats['imported'] += 1
                    else:
                        mukkadam = Mukkadam()
                        action = 'imported'
                        stats['imported'] += 1

                    # Map Excel columns to Model fields
                    mukkadam.mukkadam_name = name
                    mukkadam.mobile_numbers = mobile
                    mukkadam.village = self._clean_string(row.get('village', ''))
                    mukkadam.has_smartphone = 'yes'  # Default to yes, edit manually if needed
                    
                    # Crew Details
                    mukkadam.crew_size = str(row.get('total_workers_peak', 0))
                    mukkadam.max_crew_capacity = str(row.get('total_workers_peak', 0))
                    mukkadam.splitting_logic = ''  # Empty string instead of None
                    mukkadam.deputy_mukkadam_name = ''  # Empty string instead of None
                    mukkadam.deputy_mukkadam_mobile = ''  # Empty string instead of None
                    mukkadam.team_members = []

                    # Availability - Set to empty/null for manual editing
                    mukkadam.start_date = None
                    mukkadam.end_date = None
                    mukkadam.daily_work_timing = ''  # Empty string instead of None
                    mukkadam.team_availabilities = []

                    # Rate Card - Build from expected charges and skills
                    rate_card = {}
                    expected_charges = row.get('expected_charges', 0)
                    
                    if pd.notna(row.get('skill_pruning')) and row.get('skill_pruning'):
                        rate_card['pruning'] = str(expected_charges)
                    if pd.notna(row.get('skill_harvesting')) and row.get('skill_harvesting'):
                        rate_card['harvesting'] = str(expected_charges)
                    if pd.notna(row.get('skill_dipping')) and row.get('skill_dipping'):
                        rate_card['dipping'] = str(expected_charges)
                    if pd.notna(row.get('skill_thinning')) and row.get('skill_thinning'):
                        rate_card['thinning'] = str(expected_charges)
                    
                    mukkadam.rate_card = rate_card if rate_card else {}

                    # Work Area Preference
                    mukkadam.home_location = self._clean_string(row.get('village', ''))
                    mukkadam.preferred_work_locations = self._clean_string(row.get('supply_areas', ''))
                    mukkadam.max_travel_distance = ''  # Empty string for manual editing

                    # Transport Details
                    transport = self._clean_string(row.get('arrange_transport', ''))
                    if transport == 'labour':
                        mukkadam.transport_mode = 'no_vehicle'
                        mukkadam.transport_arranged_by = 'mukkadam'
                    else:
                        mukkadam.transport_mode = 'no_vehicle'  # Default
                        mukkadam.transport_arranged_by = ''
                    
                    mukkadam.transport_charges = {}

                    # Payment Details
                    mukkadam.payment_details = {
                        'modes': {},
                        'upiId': '',
                        'accountNumber': '',
                        'ifscCode': '',
                        'bankName': '',
                        'accountHolderName': ''
                    }

                    # Work Mode
                    mukkadam.work_mode = 'daily_up_down'  # Default, edit manually if needed
                    mukkadam.move_in_preferred_region = ''

                    # Referral - Set to null for manual editing
                    mukkadam.referral_source = ''
                    mukkadam.referred_by = None
                    mukkadam.referral_source_text = ''

                    # Notification Preferences
                    mukkadam.notification_preferences = {
                        'sms': True,
                        'whatsapp': True,
                        'call': True
                    }

                    # Other Info
                    mukkadam.other_commitments = ''
                    
                    # Documents - Set to null (will be uploaded manually)
                    mukkadam.aadhar_number = None
                    mukkadam.pan_number = None
                    mukkadam.profile_photo = None
                    mukkadam.aadhar_card = None
                    mukkadam.pan_card = None
                    mukkadam.bank_proof = None

                    # Tracking
                    mukkadam.created_by = user

                    mukkadam.save()

                    # Create Activity Log
                    ActivityLog.objects.create(
                        mukkadam=mukkadam,
                        user=user,
                        action_type='Bulk Import' if action == 'imported' else 'Bulk Update',
                        details=f'Imported from Excel file: {os.path.basename(file_path)}'
                    )

                    self.stdout.write(
                        self.style.SUCCESS(f'Row {idx+1}: {action.title()} - {name} ({mobile})')
                    )

            except Exception as e:
                stats['errors'] += 1
                error_report.append({
                    'row': idx + 1,
                    'name': name if 'name' in locals() else 'Unknown',
                    'error': str(e)
                })
                self.stdout.write(
                    self.style.ERROR(f'Row {idx+1}: Error - {str(e)}')
                )

        # Print Summary Report
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total Records in File: {stats["total"]}')
        self.stdout.write(self.style.SUCCESS(f'Successfully Imported: {stats["imported"]}'))
        if stats['updated'] > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully Updated: {stats["updated"]}'))
        self.stdout.write(self.style.WARNING(f'Skipped: {stats["skipped"]}'))
        self.stdout.write(self.style.ERROR(f'Errors: {stats["errors"]}'))
        self.stdout.write(self.style.WARNING(f'Duplicates Found: {stats["duplicates_found"]}'))

        # Duplicate Report
        if duplicate_report:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.WARNING('DUPLICATE MOBILE NUMBERS DETECTED'))
            self.stdout.write('='*60)
            for dup in duplicate_report:
                self.stdout.write(
                    f"Row {dup['row']}: {dup['name']} | {dup['mobile']} | {dup['village']} "
                    f"(Existing ID: {dup['existing_id']})"
                )

        # Error Report
        if error_report:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.ERROR('ERRORS ENCOUNTERED'))
            self.stdout.write('='*60)
            for err in error_report:
                self.stdout.write(f"Row {err['row']}: {err['name']} - {err['error']}")

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('IMPORT COMPLETED'))
        self.stdout.write('='*60)

    def _clean_string(self, value):
        """Clean and return string value or empty string if null"""
        if pd.isna(value) or value is None:
            return ''
        return str(value).strip()

    def _clean_mobile(self, value):
        """Clean and format mobile number"""
        if pd.isna(value) or value is None:
            return None
        
        # Convert to string and remove decimals
        mobile = str(int(float(value))) if isinstance(value, (int, float)) else str(value)
        
        # Remove any non-digit characters
        mobile = ''.join(filter(str.isdigit, mobile))
        
        # Keep last 10 digits if longer
        if len(mobile) > 10:
            mobile = mobile[-10:]
        
        return mobile if len(mobile) == 10 else None