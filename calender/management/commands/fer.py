"""
Django management command to ADD FERTILIZER/FERTIGATION SCHEDULES to existing grape varieties
This is an ADDON - run AFTER importing the main crop protection schedules

Place this file in: your_app/management/commands/add_fertilizer_schedules.py

Usage: python manage.py add_fertilizer_schedules
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from calender.models import CropVariety, Activity, Product, DayRange, DayRangeProduct


class Command(BaseCommand):
    help = 'Add fertilizer/fertigation schedules to existing grape varieties'

    def __init__(self):
        super().__init__()
        self.fertilizer_name_mapping = {
            # Marathi to English mappings for fertilizers
            'कॅल्शियम नाइट्रेट': 'Calcium Nitrate',
            'मॅग्नेशियम नाइट्रेट': 'Magnesium Nitrate',
            'मॅग्नेशियम सल्फेट': 'Magnesium Sulphate',
            'क्षीरवॅम + आद्रा': 'Kshirvam + Ardra',
            'व्हिटाफ्लोरा': 'Vitaflora',
            'बॅटलोन': 'Battalion',
            'फोस्फोरीक अॅसिड': 'Phosphoric Acid',
            'पोटॅशियम नाइट्रेट': 'Potassium Nitrate',
            'पोटॅशियम सल्फेट': 'Potassium Sulphate',
            'धनिष्ठा': 'Dhanishtha',
            'सह्याद्री Ca थायोसल्फेट': 'Sahyadri Ca Thiosulphate',
            'डी. एफ. १': 'DF 1',
            'युरिया': 'Urea',
            'मोनो पोटॅशियम फॉस्फेट': 'Mono Potassium Phosphate',
            'बोरॅक्स': 'Borax',
            '००:५२:३४': '00:52:34',
            '००:००:५०': '00:00:50',
            '१२:६१:००': '12:61:00',
            '१३:००:४५': '13:00:45',
            '१९:१९:१९': '19:19:19',
            '००:६०:२०': '00:60:20',
        }
    
    def get_english_name(self, marathi_name):
        """Get English name from Marathi"""
        return self.fertilizer_name_mapping.get(marathi_name, marathi_name)
    
    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write('Adding fertilizer schedules to existing varieties...')
        
        # Create Fertigation activity
        fertigation_activity, _ = Activity.objects.get_or_create(
            name='Fertigation',
            defaults={'name_marathi': 'खतीकरण'}
        )
        
        self.stdout.write(f'Fertigation activity: {fertigation_activity.name}')
        
        # Import fertilizer schedules for each variety
        self.add_thompson_fertilizers(fertigation_activity)
        self.add_arra15_fertilizers(fertigation_activity)
        self.add_crimson_fertilizers(fertigation_activity)
        self.add_ard35_fertilizers(fertigation_activity)
        self.add_ard36_fertilizers(fertigation_activity)
        
        self.stdout.write(self.style.SUCCESS('All fertilizer schedules added successfully!'))
    
    def add_thompson_fertilizers(self, activity):
        """Add Thompson Seedless fertilizer schedule"""
        variety = CropVariety.objects.get(name='Thompson Seedless')
        self.stdout.write(f'\nAdding fertilizers for {variety.name}...')
        
        # Create products
        products = self._create_fertilizer_products()
        
        schedule = [
            {
                'day': 0,
                'activity': 'छाटणी',
                'fertilizers': [
                    {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                    {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                    {'name': 'बॅटलोन', 'dosage': 1},
                    {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
                ],
                'info': 'छाटणी नंतर लगेच द्यावे'
            },
            {
                'day': 9,
                'activity': '१० ऑक्टो नंतर छाटणीसाठीच',
                'fertilizers': [
                    {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                    {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3}
                ],
                'info': 'फक्त १० ऑक्टोबर नंतर छाटणी केलेल्या वेलींसाठी'
            },
            {
                'day': 15,
                'activity': 'फेल फुट काढल्या नंतर',
                'fertilizers': [
                    {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                    {'name': 'धनिष्ठा', 'dosage': 0.2},
                    {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
                ],
                'info': ''
            },
            {
                'day': 22,
                'activity': '९-१० पान अवस्था',
                'fertilizers': [
                    {'name': '००:५२:३४', 'dosage': 5},
                    {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                    {'name': 'डी. एफ. १', 'dosage': 20}
                ],
                'info': ''
            },
            {
                'day': 29,
                'activity': 'दोडा अवस्था',
                'fertilizers': [
                    {'name': '००:५२:३४', 'dosage': 3},
                    {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                    {'name': '००:००:५०', 'dosage': 5}
                ],
                'info': ''
            },
            {
                'day': 36,
                'activity': 'फ्लॉवरिंग',
                'fertilizers': [
                    {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                    {'name': '००:००:५०', 'dosage': 5},
                    {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
                ],
                'info': ''
            },
            {
                'day': 46,
                'activity': '२-४ एम एम',
                'fertilizers': [
                    {'name': '१२:६१:००', 'dosage': 5},
                    {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                    {'name': '००:००:५०', 'dosage': 5}
                ],
                'info': ''
            },
            {
                'day': 50,
                'activity': '६-७ एम एम',
                'fertilizers': [
                    {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                    {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                    {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                    {'name': 'व्हिटाफ्लोरा', 'dosage': 4},
                    {'name': 'बॅटलोन', 'dosage': 1},
                    {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
                ],
                'info': ''
            },
            {
                'day': 57,
                'activity': '८-१० एम एम',
                'fertilizers': [
                    {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 7},
                    {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
                ],
                'info': ''
            },
            {
                'day': 64,
                'activity': '११-१२ एम एम',
                'fertilizers': [
                    {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                    {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                    {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
                ],
                'info': ''
            },
            {
                'day': 72,
                'activity': '१२-१४ एम एम',
                'fertilizers': [
                    {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                    {'name': '१३:००:४५', 'dosage': 5},
                    {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
                ],
                'info': ''
            },
            {
                'day': 80,
                'activity': '१४-१६ एम एम',
                'fertilizers': [
                    {'name': '१३:००:४५', 'dosage': 5},
                    {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                    {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                    {'name': 'बॅटलोन', 'dosage': 1},
                    {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
                ],
                'info': ''
            },
            {
                'day': 87,
                'activity': 'पाणी उतरणे',
                'fertilizers': [
                    {'name': '१३:००:४५', 'dosage': 5},
                    {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
                ],
                'info': ''
            },
            {
                'day': 94,
                'activity': '१००% पाणी उतरणे',
                'fertilizers': [
                    {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
                ],
                'info': ''
            },
            {
                'day': 101,
                'activity': 'काढणीअगोदर',
                'fertilizers': [
                    {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
                ],
                'info': 'काढणीच्या आधी शेवटचे खत'
            }
        ]
        
        self._insert_fertilizer_schedule(variety, activity, products, schedule)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(schedule)} fertilizer entries'))
    
    def add_arra15_fertilizers(self, activity):
        """Add ARRA 15 fertilizer schedule"""
        variety = CropVariety.objects.get(name='ARRA 15')
        self.stdout.write(f'\nAdding fertilizers for {variety.name}...')
        
        products = self._create_fertilizer_products()
        
        # Similar schedule structure - simplified for brevity
        schedule = [
            {'day': 0, 'activity': 'छाटणी', 'fertilizers': [
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 9, 'activity': 'फेल फुट काढल्या नंतर', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3}
            ], 'info': ''},
            {'day': 15, 'activity': '१० ऑक्टो नंतर छाटणीसाठीच', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'धनिष्ठा', 'dosage': 0.2},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 22, 'activity': '९-१० पान अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'डी. एफ. १', 'dosage': 20}
            ], 'info': ''},
            {'day': 29, 'activity': 'दोडा अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 3},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 36, 'activity': 'फ्लॉवरिंग', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 43, 'activity': '२-४ एम एम', 'fertilizers': [
                {'name': '१२:६१:००', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 50, 'activity': '६-७ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 4},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 57, 'activity': '८-१० एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 7},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 64, 'activity': '११-१२ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 72, 'activity': '१२-१४ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 80, 'activity': '१४-१६ एम एम', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 87, 'activity': 'पाणी उतरणे', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 94, 'activity': 'काढणीअगोदर', 'fertilizers': [
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''}
        ]
        
        self._insert_fertilizer_schedule(variety, activity, products, schedule)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(schedule)} fertilizer entries'))
    
    def add_crimson_fertilizers(self, activity):
        """Add Crimson fertilizer schedule"""
        variety = CropVariety.objects.get(name='Crimson')
        self.stdout.write(f'\nAdding fertilizers for {variety.name}...')
        
        products = self._create_fertilizer_products()
        
        schedule = [
            {'day': 0, 'activity': 'छाटणी', 'fertilizers': [
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 9, 'activity': 'फेल फुट काढल्या नंतर', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3}
            ], 'info': ''},
            {'day': 15, 'activity': '१० ऑक्टो नंतर छाटणीसाठीच', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'धनिष्ठा', 'dosage': 0.2},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 22, 'activity': '९-१० पान अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'डी. एफ. १', 'dosage': 20}
            ], 'info': ''},
            {'day': 29, 'activity': 'दोडा अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 3},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 36, 'activity': 'फ्लॉवरिंग', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 43, 'activity': '२-४ एम एम', 'fertilizers': [
                {'name': '१२:६१:००', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 50, 'activity': '६-७ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 4},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 57, 'activity': '८-१० एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 7},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 64, 'activity': '११-१२ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 72, 'activity': '१२-१४ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 80, 'activity': '१४-१६ एम एम', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 87, 'activity': 'पाणी उतरणे', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 94, 'activity': 'काढणीअगोदर', 'fertilizers': [
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''}
        ]
        
        self._insert_fertilizer_schedule(variety, activity, products, schedule)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(schedule)} fertilizer entries'))
    
    def add_ard35_fertilizers(self, activity):
        """Add ARD 35 fertilizer schedule"""
        variety = CropVariety.objects.get(name='ARD 35')
        self.stdout.write(f'\nAdding fertilizers for {variety.name}...')
        
        products = self._create_fertilizer_products()
        
        schedule = [
            {'day': 0, 'activity': 'छाटणी', 'fertilizers': [
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 9, 'activity': 'फेल फुट काढल्या नंतर', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3}
            ], 'info': ''},
            {'day': 15, 'activity': '१० ऑक्टो नंतर छाटणीसाठीच', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'धनिष्ठा', 'dosage': 0.2},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 22, 'activity': '९-१० पान अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'डी. एफ. १', 'dosage': 20}
            ], 'info': ''},
            {'day': 29, 'activity': 'दोडा अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 3},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 36, 'activity': 'फ्लॉवरिंग', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 43, 'activity': '२-४ एम एम', 'fertilizers': [
                {'name': '१२:६१:००', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 50, 'activity': '६-७ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 4},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 57, 'activity': '८-१० एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 7},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 64, 'activity': '११-१२ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 72, 'activity': '१२-१४ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 80, 'activity': '१४-१६ एम एम', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 87, 'activity': 'पाणी उतरणे', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 94, 'activity': 'काढणीअगोदर', 'fertilizers': [
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''}
        ]
        
        self._insert_fertilizer_schedule(variety, activity, products, schedule)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(schedule)} fertilizer entries'))
    
    def add_ard36_fertilizers(self, activity):
        """Add ARD 36 fertilizer schedule"""
        variety = CropVariety.objects.get(name='ARD 36')
        self.stdout.write(f'\nAdding fertilizers for {variety.name}...')
        
        products = self._create_fertilizer_products()
        
        schedule = [
            {'day': 0, 'activity': 'छाटणी', 'fertilizers': [
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 9, 'activity': 'फेल फुट काढल्या नंतर', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3}
            ], 'info': ''},
            {'day': 15, 'activity': '१० ऑक्टो नंतर छाटणीसाठीच', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'धनिष्ठा', 'dosage': 0.2},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 22, 'activity': '९-१० पान अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 4},
                {'name': 'डी. एफ. १', 'dosage': 20}
            ], 'info': ''},
            {'day': 29, 'activity': 'दोडा अवस्था', 'fertilizers': [
                {'name': '००:५२:३४', 'dosage': 3},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 36, 'activity': 'फ्लॉवरिंग', 'fertilizers': [
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5},
                {'name': 'सह्याद्री Ca थायोसल्फेट', 'dosage': 10}
            ], 'info': ''},
            {'day': 43, 'activity': '२-४ एम एम', 'fertilizers': [
                {'name': '१२:६१:००', 'dosage': 5},
                {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 5},
                {'name': '००:००:५०', 'dosage': 5}
            ], 'info': ''},
            {'day': 50, 'activity': '६-७ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 4},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 57, 'activity': '८-१० एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 7},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 64, 'activity': '११-१२ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': 'मॅग्नेशियम नाइट्रेट', 'dosage': 3},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 72, 'activity': '१२-१४ एम एम', 'fertilizers': [
                {'name': 'कॅल्शियम नाइट्रेट', 'dosage': 5},
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 80, 'activity': '१४-१६ एम एम', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'क्षीरवॅम + आद्रा', 'dosage_str': '.२+.२'},
                {'name': 'व्हिटाफ्लोरा', 'dosage': 3},
                {'name': 'बॅटलोन', 'dosage': 1},
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''},
            {'day': 87, 'activity': 'पाणी उतरणे', 'fertilizers': [
                {'name': '१३:००:४५', 'dosage': 5},
                {'name': 'पोटॅशियम सल्फेट', 'dosage': 5}
            ], 'info': ''},
            {'day': 94, 'activity': 'काढणीअगोदर', 'fertilizers': [
                {'name': 'फोस्फोरीक अॅसिड', 'dosage': 3.4}
            ], 'info': ''}
        ]
        
        self._insert_fertilizer_schedule(variety, activity, products, schedule)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added {len(schedule)} fertilizer entries'))
    
    def _create_fertilizer_products(self):
        """Create all fertilizer products"""
        products = {}
        product_list = [
            ('Calcium Nitrate', 'कॅल्शियम नाइट्रेट', 'Fertilizer'),
            ('Magnesium Nitrate', 'मॅग्नेशियम नाइट्रेट', 'Fertilizer'),
            ('Magnesium Sulphate', 'मॅग्नेशियम सल्फेट', 'Fertilizer'),
            ('Kshirvam + Ardra', 'क्षीरवॅम + आद्रा', 'Bio Stimulant'),
            ('Vitaflora', 'व्हिटाफ्लोरा', 'Bio Stimulant'),
            ('Battalion', 'बॅटलोन', 'Bio Stimulant'),
            ('Phosphoric Acid', 'फोस्फोरीक अॅसिड', 'Fertilizer'),
            ('Potassium Nitrate', 'पोटॅशियम नाइट्रेट', 'Fertilizer'),
            ('Potassium Sulphate', 'पोटॅशियम सल्फेट', 'Fertilizer'),
            ('Dhanishtha', 'धनिष्ठा', 'Micronutrient'),
            ('Sahyadri Ca Thiosulphate', 'सह्याद्री Ca थायोसल्फेट', 'Fertilizer'),
            ('DF 1', 'डी. एफ. १', 'Bio Stimulant'),
            ('Mono Potassium Phosphate', 'मोनो पोटॅशियम फॉस्फेट', 'Fertilizer'),
            ('Borax', 'बोरॅक्स', 'Micronutrient'),
            ('00:52:34', '००:५२:३४', 'Fertilizer'),
            ('00:00:50', '००:००:५०', 'Fertilizer'),
            ('12:61:00', '१२:६१:००', 'Fertilizer'),
            ('19:19:19', '१९:१९:१९', 'Fertilizer'),
            ('00:60:20', '००:६०:२०', 'Fertilizer'),
        ]
        
        for eng_name, mar_name, prod_type in product_list:
            product, _ = Product.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name, 'product_type': prod_type}
            )
            products[mar_name] = product
            products[eng_name] = product
        
        return products
    
    def _insert_fertilizer_schedule(self, variety, activity, products, schedule):
        """Insert fertilizer schedule for a variety"""
        for item in schedule:
            day_range = DayRange.objects.create(
                crop_variety=variety,
                activity=activity,
               
                start_day=item['day'],
                end_day=item['day'],
                info=item.get('info', ''),
                info_marathi=item['activity']
            )
            
            for fert_data in item['fertilizers']:
                product_obj = products.get(fert_data['name'])
                if product_obj:
                    if 'dosage' in fert_data:
                        DayRangeProduct.objects.create(
                            day_range=day_range,
                            product=product_obj,
                            dosage=fert_data['dosage'],
                            dosage_unit='kg/acre'
                        )
                    elif 'dosage_str' in fert_data:
                        # For special dosages like .२+.२, store as 0.4
                        try:
                            dosage_val = 0.4 if fert_data['dosage_str'] == '.२+.२' else 1.0
                            DayRangeProduct.objects.create(
                                day_range=day_range,
                                product=product_obj,
                                dosage=dosage_val,
                                dosage_unit='kg/acre'
                            )
                        except:
                            pass