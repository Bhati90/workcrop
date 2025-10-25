"""
Django management command to import ALL Grape Varieties Crop Protection Schedules
Place this file in: your_app/management/commands/import_all_grape_varieties.py

Usage: python manage.py import_all_grape_varieties
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from calender.models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct


class Command(BaseCommand):
    help = 'Import All Grape Varieties (ARD 35, ARD 36, ARRA 15, Crimson, Thompson) Crop Protection Schedules'

    def __init__(self):
        super().__init__()
        self.product_name_mapping = {
    'युरिया': 'Urea',
    'यूरिया': 'Urea',
    'दशपर्णी अर्क': 'Dashparni Ark',
    'सल्फर': 'Sulphur',
    'हस्ता': 'Hasta',
    'अॅप्लॉड': 'Applaud',
    'अमिल': 'Amil',
    'सुनामि': 'Sunami',
    'मोरचूद': 'Morchud',
    'चुना': 'Lime',
    'इन्स्टंट चुना': 'Instant Lime',
    'ब्लायटॉक्स': 'Blitox',
    'इमिडा': 'Imida',
    'कॅराथेन गोल्ड': 'Karathane Gold',
    'वेमिल': 'Vemil Ark',
    'सिटोऑक्स (सीपीपीयू)': 'Citox (CPPU)',
    '००:४९:३२': '00:49:32',
    'कुमान एल': 'Cuman L',
    'टिल्ट': 'Tilt',
    'कॅपटाफ': 'Captaf',
    'पॉलीवाईन': 'Polyvine',
    'मेटाडोर': 'Metador',
    'अॅक्रोबॅट': 'Acrobat',
    'बड बिल्डर': 'Bud Builder',
    'बड प्रो': 'Bud Pro',
    'स्पिंटॉर': 'Spintor',
    'पोटॅशियम शोनाइट': 'Potassium Schoenite',
    'सॅलीसिओ': 'Salicio',
    'बोरोन': 'Boron',
    'जेष्ठा': 'Jeshta',
    'मॅग्नेशियम सल्फेट': 'Magnesium Sulphate',
    'सरप्लस': 'Surplus',
    'झोर्वेक एन्टेक्टा': 'Zorvec Entecta',
    'प्रोजीब इजी जीए': 'Projib Easy GA',
    'अॅबॅसिन': 'Abasin',
    'झिंकमोर': 'Zincmore',
    'व्हिटाफ्लोरा': 'Vitaflora',
    'एल बी युरिया': 'LB Urea',
    'कोसूट': 'Kosut',
    'कोसाईड': 'Koside',
    'कासुगामाइसिन': 'Kasugamycin',
    'अॅन्ट्राकॉल': 'Antracol',
    'पॉलीकार्ब Ca': 'Polycarb Ca',
    'इनोव्हाकॅल': 'Innovacal',
    'प्रोफाइलर': 'Profiler',
    'स्कोर': 'Score',
    'प्रोक्लेम': 'Proclaim',
    'वेल्झो': 'Velzo',
    'मेरीवॉन': 'Merivon',
    'एक्स्पोनस': 'Exponus',
    'लुना एक्सपिरियन्स': 'Luna Experience',
    'कमाब २६': 'Kumab 26',
    'अर्द्रा': 'Ardra',
    'अॅक्रिसीओ': 'Acrisio',
    'रॅनमॅन': 'Ranman',
    'मोव्हेंटो ओडी': 'Movento OD',
    'मोव्हेंटो': 'Movento OD',
    'एलियट': 'Eliot',
    'स्टॉपिट': 'Stopit',
    'ईक्लोन मॅक्स': 'Eclon Max',
    'बंबार्डीयर': 'Bombardier',
    'आरमाचुरा': 'Armachura',
    'फार्मामीन': 'Farmamin',
    'चि. फेरस १२ %': 'Chelated Ferrous 12%',
    'सल्फर डस्ट': 'Sulphur Dust',
    'एम ४५': 'M-45',
    'डॉर्मेक्स': 'Dormex',
    'ईथ्रेल': 'Ethrel',
    '१३:००:४५': '13:00:45',
    '००:५२:३४': '00:52:34',
    'अमोनियम सल्फेट': 'Ammonium Sulphate',
    'एस बी': 'SB',
    'नोवा': 'Nova',
    'गिबरिन': 'Gibrin',
    'कुमाब': 'Kumab'
}

    
    def get_english_product_name(self, marathi_name):
        """Get English product name from Marathi"""
        return self.product_name_mapping.get(marathi_name, marathi_name)
    
    def normalize_unit(self, marathi_unit):
        """Convert Marathi units to standard units"""
        unit_mapping = {
            'ग्रॅम': 'gm/liter',
            'मिली': 'ml/liter',
            'किलो': 'kg/acre',
            'लिटर': 'liter/acre',
        }
        return unit_mapping.get(marathi_unit, 'gm/liter')
    
    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write('Starting import of all grape varieties...')
        
        # Create Crop
        crop, _ = Crop.objects.get_or_create(
            name='Grapes',
            defaults={'name_marathi': 'द्राक्ष'}
        )
        self.stdout.write(f'Crop: {crop.name}')
        
        # Import each variety

        self.stdout.write('\nImporting ARRA 15...')
        self.import_arra_15(crop)

        self.stdout.write('\nImporting Crimson...')
        self.import_crimson(crop)

        self.stdout.write('\nImporting Thompson Seedless...')
        self.import_thompson_seedless(crop)

        self.stdout.write('\nImporting ARD 35...')
        self.import_ard_35(crop)

    def import_arra_15(self, crop):
        """Import ARRA 15 variety schedule"""
        variety, _ = CropVariety.objects.get_or_create(
            crop=crop,
            name='ARRA 15',
            defaults={'name_marathi': 'एआरआरए १५'}
        )
        
        # Activities
        activities = {}
        activity_names = [
            ('Cotton Boll Stage', 'कापसलेली'),
            ('Green Point', 'ग्रीन पॉइंट'),
            ('Bead Stage', 'दोडा अवस्था'),
            ('Leaf Fall', 'पानगळ'),
            ('Pasting', 'पेस्टिंग'),
            ('Groundnut Stage', 'शेंगदाणा'),
            ('1 MM Berry', '१ एम एम'),
            ('10% Water Recession', '१०% पाणी उतरणे'),
            ('10-12 MM Berry', '१०-१२ एमएम'),
            ('100% Bud Burst', '१००% पोंगा'),
            ('15-16 MM Berry', '१५-१६ एम एम'),
            ('2-3 MM Berry', '२-३ एम एम'),
            ('३ – ५ एमएम', '३ – ५ एमएम'),
            ('४- ५ पानअवस्था', '४- ५ पानअवस्था'),
            ('4-6 MM Berry', '४-६ एम एम'),
            ('5 cm Shoot', '५ सेमी. शूट'),
            ('5% Flowering', '५% फ्लॉवरिंग'),
            ('50% Bud Burst', '५०% पोंगा'),
            ('6-8 MM Berry', '६ -८ एम एम'),
            ('६-७ पान अवस्था', '६-७ पान अवस्था'),
            ('70% Flowering', '७०% फ्लॉवरिंग'),
            ('8-10 MM Berry', '८-१० एम एम'),
            ('Foliar Spray', 'फवारणी'),
        ]
        
        for eng_name, mar_name in activity_names:
            activity, _ = Activity.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name}
            )
            activities[mar_name if mar_name else eng_name] = activity
        
        # Default activity for empty
        default_activity = activities.get('फवारणी', list(activities.values())[0])
        
        # Products (collect all unique)
        products = {}
        product_list = [
            ('Amil', 'अमिल', 'Fertilizer'),
            ('Ammonium Sulphate', 'अमोनियम सल्फेट', 'Fertilizer'),
            ('Ardra', 'अर्द्रा', 'Fertilizer'),
            ('Acrisio', 'अॅक्रिसीओ', 'Fertilizer'),
            ('Acrobat', 'अॅक्रोबॅट', 'Fertilizer'),
            ('Antracol', 'अॅन्ट्राकॉल', 'Fertilizer'),
            ('Applaud', 'अॅप्लॉड', 'Fertilizer'),
            ('अॅबॅसिन ०.७५ मिलि', 'अॅबॅसिन ०.७५ मिलि', 'Fungicide'),
            ('आद्रा', 'आद्रा', 'Fertilizer'),
            ('आद्रा ०.५ ग्रॅम', 'आद्रा ०.५ ग्रॅम', 'Fungicide'),
            ('Armachura', 'आरमाचुरा', 'Fertilizer'),
            ('Imida', 'इमिडा', 'Fertilizer'),
            ('Eclon Max', 'ईक्लोन मॅक्स', 'Fertilizer'),
            ('Ethrel', 'ईथ्रेल', 'Fertilizer'),
            ('Exponus', 'एक्स्पोनस', 'Fertilizer'),
            ('M-45', 'एम ४५', 'Fertilizer'),
            ('LB Urea', 'एल बी युरिया', 'Fertilizer'),
            ('Eliot', 'एलियट', 'Fertilizer'),
            ('Kumab 26', 'कमाब २६', 'Fertilizer'),
            ('Kasugamycin', 'कासुगामाइसिन', 'Fertilizer'),
            ('Cuman L', 'कुमान एल', 'Fertilizer'),
            ('Captaf', 'कॅपटाफ', 'Fertilizer'),
            ('कॅराथेन  गोल्ड', 'कॅराथेन  गोल्ड', 'Fertilizer'),
            ('कोसूट / कोसाईड', 'कोसूट / कोसाईड', 'Fertilizer'),
            ('Lime', 'चुना', 'Fertilizer'),
            ('जेष्टा ०.५ ग्रॅम', 'जेष्टा ०.५ ग्रॅम', 'Fungicide'),
            ('Jeshta', 'जेष्ठा', 'Fertilizer'),
            ('Zincmore', 'झिंकमोर', 'Fertilizer'),
            ('झोर्वेक एन्टेक्टा  १२५ मिली (प्रति एकर)', 'झोर्वेक एन्टेक्टा  १२५ मिली (प्रति एकर)', 'Fungicide'),
            ('Dormex', 'डॉर्मेक्स', 'Plant Growth Regulator'),
            ('Dashparni Ark', 'दशपर्णी अर्क', 'Bio Stimulant'),
            ('पॉलीकार्ब कॅल्शिअम', 'पॉलीकार्ब कॅल्शिअम', 'Fungicide'),
            ('Polyvine', 'पॉलीवाईन', 'Fertilizer'),
            ('पो. बायकार्बोनेट', 'पो. बायकार्बोनेट', 'Fertilizer'),
            ('Proclaim', 'प्रोक्लेम', 'Fertilizer'),
            ('प्रोजीब  इजी जीए', 'प्रोजीब  इजी जीए', 'Fertilizer'),
            ('Profiler', 'प्रोफाइलर', 'Fertilizer'),
            ('Farmamin', 'फार्मामीन', 'Fertilizer'),
            ('Bombardier', 'बंबार्डीयर', 'Fertilizer'),
            ('बड बिल्डर / बड', 'बड बिल्डर / बड', 'Fertilizer'),
            ('मॅग्नेशियम  सल्फेट', 'मॅग्नेशियम  सल्फेट', 'Fungicide'),
            ('Magnesium Sulphate', 'मॅग्नेशियम सल्फेट', 'Fertilizer'),
            ('Metador', 'मेटाडोर', 'Fertilizer'),
            ('Merivon', 'मेरीवॉन', 'Fertilizer'),
            ('Morchud', 'मोरचूद', 'Fertilizer'),
            ('Movento OD', 'मोव्हेंटो ओडी', 'Fertilizer'),
            ('Urea', 'युरिया', 'Fertilizer'),
            ('Ranman', 'रॅनमॅन', 'Fertilizer'),
            ('Luna Experience', 'लुना एक्सपिरियन्स', 'Fertilizer'),
            ('Vemil Ark', 'वेमिल', 'Bio Stimulant'),
            ('वेमिल अर्क १० मिलि', 'वेमिल अर्क १० मिलि', 'Fungicide'),
            ('Velzo', 'वेल्झो', 'Fertilizer'),
            ('Vitaflora', 'व्हिटाफ्लोरा', 'Fertilizer'),
            ('Surplus', 'सरप्लस', 'Fertilizer'),
            ('सरप्लस १ मिली', 'सरप्लस १ मिली', 'Fungicide'),
            ('Sulphur', 'सल्फर', 'Fertilizer'),
            ('Sulphur Dust', 'सल्फर डस्ट', 'Fertilizer'),
            ('Sunami', 'सुनामि', 'Fertilizer'),
            ('Salicio', 'सॅलीसिओ', 'Fertilizer'),
            ('Score', 'स्कोर', 'Fertilizer'),
            ('Stopit', 'स्टॉपिट', 'Fertilizer'),
            ('Spintor', 'स्पिंटॉर', 'Fertilizer'),
            ('Hasta', 'हस्ता', 'Fertilizer'),
            ('००:००:५०', '००:००:५०', 'Fertilizer'),
            ('00:49:32', '००:४९:३२', 'Fertilizer'),
            ('13:00:45', '१३:००:४५', 'Fertilizer'),
        ]
        
        for eng_name, mar_name, prod_type in product_list:
            product, _ = Product.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name, 'product_type': prod_type}
            )
            products[mar_name] = product
            products[eng_name] = product
        
        # Schedule data
        schedule = [
            {
                'day': 15,
                'activity': 'पानगळ',
                'info': '६०० ली. पाणी फवारणे व उलटा पालटा स्प्रे घेणे. सकाळी लवकर स्प्रे घेणे.',
                'products': [{'name': 'अमोनियम सल्फेट', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'ईथ्रेल', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 0,
                'activity': 'पेस्टिंग',
                'info': 'पेस्टमध्ये गेरू घेतल्यास एकसारखी फुट मिळते. एकरी ६० ते ८० लि. पाणी वापरणे.',
                'products': [{'name': '१३:००:४५', 'dosage': 50.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'डॉर्मेक्स', 'dosage': 50.0, 'unit': 'मिली'}]
            },
            {
                'day': 3,
                'activity': 'Foliar Spray',
                'info': 'एकसारखी फुट मिळण्यासाठी ५००  ली. पाणी फवारणे.',
                'products': [{'name': 'युरिया', 'dosage': 10.0, 'unit': 'ग्रॅम'}, {'name': 'दशपर्णी अर्क', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सल्फर', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 6,
                'activity': 'Foliar Spray',
                'info': 'एकरी   १६०० - २०००  ली. पाणी वापरणे.',
                'products': [{'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अॅप्लॉड', 'dosage': 0.75, 'unit': 'मिली'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सुनामि', 'dosage': 0.125, 'unit': 'मिली'}]
            },
            {
                'day': 7,
                'activity': 'शेंगदाणा',
                'info': 'गच्च फवारा घेणे.',
                'products': [{'name': 'मोरचूद', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'चुना', 'dosage': 1.75, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 8,
                'activity': 'कापसलेली',
                'info': 'उडद्या साठी संध्याकाळी स्प्रे घेणे.',
                'products': [{'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'कॅराथेन  गोल्ड', 'dosage': 0.3, 'unit': 'मिली'}, {'name': 'एम ४५', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'वेमिल अर्क १० मिलि', 'dosage_str': 'as needed'}]
            },
            {
                'day': 9,
                'activity': 'ग्रीन पॉइंट',
                'info': '',
                'products': [{'name': '००:४९:३२', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'कुमान एल', 'dosage': 3.0, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 10,
                'activity': '५०% पोंगा',
                'info': '',
                'products': [{'name': 'मेटाडोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'कॅपटाफ', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'पॉलीवाईन', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 11,
                'activity': '१००% पोंगा',
                'info': '',
                'products': [{'name': '००:००:५०', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'बड बिल्डर / बड', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'सरप्लस १ मिली', 'dosage_str': 'as needed'}]
            },
            {
                'day': 12,
                'activity': 'Foliar Spray',
                'info': 'उडद्या अति जास्त प्रमाणात असेल तर स्पिंटोर – ०.२५ मिलि / लिटर स्प्रे घ्यावा.',
                'products': [{'name': '००:४९:३२', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}]
            },
            {
                'day': 13,
                'activity': '५ सेमी. शूट',
                'info': 'एकरी ४०० ली. पाणी लिटर  फवारणे',
                'products': [{'name': 'झोर्वेक एन्टेक्टा  १२५ मिली (प्रति एकर)', 'dosage_str': 'as needed'}, {'name': 'प्रोजीब  इजी जीए', 'dosage': 0.25, 'unit': 'पीपीएम'}]
            },
            {
                'day': 14,
                'activity': 'Foliar Spray',
                'info': 'फेल फुट काढणे.',
                'products': [{'name': 'कोसूट / कोसाईड', 'dosage': 1.25, 'unit': 'ग्रॅम'}, {'name': 'कासुगामाइसिन', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 15,
                'activity': '४- ५ पानअवस्था',
                'info': 'पहिल्या  जीए  चा रिजल्ट कमी वाटल्यास पुन्हा जीए द्यायचा असेल तर अग्रोनोमिस्ट सोबत संपर्क करणे.',
                'products': [{'name': 'अॅन्ट्राकॉल', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'दशपर्णी अर्क', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 16,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅबॅसिन ०.७५ मिलि', 'dosage_str': 'as needed'}, {'name': 'पॉलीकार्ब कॅल्शिअम', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 18,
                'activity': '६-७ पान अवस्था',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 20,
                'activity': 'Foliar Spray',
                'info': '२० ते २३ दिवसात पानदेठ परीक्षण करून घेणे.',
                'products': [{'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'कॅपटाफ', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 21,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'पॉलीकार्ब कॅल्शिअम', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 23,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'वेल्झो', 'dosage': 800.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 24,
                'activity': 'Foliar Spray',
                'info': 'शेंडा  वाढीच्या वेगानुसार नत्राचे नियोजन करने.',
                'products': [{'name': '००:४९:३२', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'अॅन्ट्राकॉल', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिली'}, {'name': 'सरप्लस १ मिली', 'dosage_str': 'as needed'}]
            },
            {
                'day': 25,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'पॉलीकार्ब कॅल्शिअम', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 26,
                'activity': 'दोडा अवस्था',
                'info': '',
                'products': [{'name': 'मेरीवॉन', 'dosage': 80.0, 'unit': 'मिलि'}, {'name': 'एक्स्पोनस', 'dosage': 34.0, 'unit': 'ग्रॅम'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 28,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 30,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'लुना एक्सपिरियन्स', 'dosage': 200.0, 'unit': 'मिली'}]
            },
            {
                'day': 31,
                'activity': '५% फ्लॉवरिंग',
                'info': 'अमोनिकल नत्राची लेवल कमी असल्यास किंवा विगर नसल्यास हा स्प्रे घेऊ नये.',
                'products': [{'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'अर्द्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 32,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 34,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 36,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅक्रिसीओ', 'dosage': 100.0, 'unit': 'मिली'}]
            },
            {
                'day': 37,
                'activity': '७०% फ्लॉवरिंग',
                'info': '',
                'products': [{'name': 'रॅनमॅन', 'dosage': 80.0, 'unit': 'मिली'}]
            },
            {
                'day': 38,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्पिंटॉर', 'dosage': 75.0, 'unit': 'मिलि'}]
            },
            {
                'day': 40,
                'activity': '१ एम एम',
                'info': 'गळ होत असल्यास  ईक-लोन मॅक्स एकरी १ लिटर  घेणे.',
                'products': [{'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'स्टॉपिट', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 42,
                'activity': '२-३ एम एम',
                'info': 'एकरी ४०० ते ५००  ली. पाणी फवारणे. / पान देठ परीक्षण करणे.',
                'products': [{'name': 'प्रोजीब  इजी जीए', 'dosage': 1.0, 'unit': 'पीपीएम'}, {'name': 'एलियट', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 44,
                'activity': '३ – ५ एमएम',
                'info': 'पहिल्या  जीए  चा रिजल्ट कमी वाटल्यास पुन्हा जीए द्यायचा असेल तर अग्रोनोमिस्ट सोबत संपर्क करणे.',
                'products': [{'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 45,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 47,
                'activity': '४-६ एम एम',
                'info': '',
                'products': [{'name': 'एल बी युरिया', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'बंबार्डीयर', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 49,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'आरमाचुरा', 'dosage': 250.0, 'unit': 'मिली'}]
            },
            {
                'day': 50,
                'activity': '६ -८ एम एम',
                'info': 'एकरी ४०० ली. पाणी फवारणे. / जीए फवारून थिनिंग करणे.',
                'products': [{'name': 'एल बी युरिया', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'प्रोजीब  इजी जीए', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'ईक्लोन मॅक्स', 'dosage': 1.0, 'unit': 'लीटर'}]
            },
            {
                'day': 52,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'स्टॉपिट', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम  सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 56,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'आद्रा ०.५ ग्रॅम', 'dosage_str': 'as needed'}, {'name': 'जेष्टा ०.५ ग्रॅम', 'dosage_str': 'as needed'}, {'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 58,
                'activity': '८-१० एम एम',
                'info': '',
                'products': [{'name': 'आरमाचुरा', 'dosage': 250.0, 'unit': 'मिली'}]
            },
            {
                'day': 63,
                'activity': '१०-१२ एमएम',
                'info': '',
                'products': [{'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 66,
                'activity': 'Foliar Spray',
                'info': 'फवारणी साठी ०.८ ची चक्ती वापरने.',
                'products': [{'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 67,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'मॅग्नेशियम  सल्फेट', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 71,
                'activity': 'Foliar Spray',
                'info': 'पाणी उतरण्यापूर्वी दहा दिवस आधी फवारणे.पान देठ परीक्षण करणे',
                'products': [{'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'फार्मामीन', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 77,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 82,
                'activity': '१५-१६ एम एम',
                'info': 'पाणी  उतरण्यास सुरवात झाल्यावर स्प्रे घेणे.',
                'products': [{'name': 'हस्ता', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'फार्मामीन', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 85,
                'activity': '१०% पाणी उतरणे',
                'info': 'डस्टिंग नंतर पेपर लावणे',
                'products': [{'name': 'सल्फर डस्ट', 'dosage': 5.0, 'unit': 'किलो'}]
            },
            {
                'day': 100,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'पो. बायकार्बोनेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 110,
                'activity': 'Foliar Spray',
                'info': 'भुरी असल्यास जमिनीवर ड्स्टिंग करणे.',
                'products': [{'name': 'पो. बायकार्बोनेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
        ]
        
        # Insert schedule
        for item in schedule:
            activity_obj = activities.get(item['activity'], default_activity)
            
            day_range = DayRange.objects.create(
                crop_variety=variety,
                activity=activity_obj,
                start_day=item['day'],
                end_day=item['day'],
                info=item['info'],
                info_marathi=item['info']
            )
            
            for prod_data in item['products']:
                product_obj = products.get(prod_data['name'])
                if product_obj:
                    if 'dosage' in prod_data:
                        unit = self.normalize_unit(prod_data['unit'])
                        DayRangeProduct.objects.create(
                            day_range=day_range,
                            product=product_obj,
                            dosage=prod_data['dosage'],
                            dosage_unit=unit
                        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {variety.name}'))

    def import_crimson(self, crop):
        """Import Crimson variety schedule"""
        variety, _ = CropVariety.objects.get_or_create(
            crop=crop,
            name='Crimson',
            defaults={'name_marathi': 'क्रिमसन'}
        )
        
        # Activities
        activities = {}
        activity_names = [
            ('Cotton Boll Stage', 'कापसलेली'),
            ('Green Point', 'ग्रीन पॉइंट'),
            ('Bead Stage', 'दोडा अवस्था'),
            ('Leaf Fall', 'पानगळ'),
            ('Pasting', 'पेस्टिंग'),
            ('फेल फुट काढणे', 'फेल फुट काढणे'),
            ('Groundnut Stage', 'शेंगदाणा'),
            ('1 MM Berry', '१ एम एम'),
            ('10-12 MM Berry', '१०-१२ एमएम'),
            ('100% Bud Burst', '१००% पोंगा'),
            ('15-16 MM Berry', '१५-१६ एम एम'),
            ('२ एम एम', '२ एम एम'),
            ('2-3 MM Berry', '२-३ एम एम'),
            ('२५ %  पाणी उतरणे', '२५ %  पाणी उतरणे'),
            ('३-४ पान अवस्था', '३-४ पान अवस्था'),
            ('४-५ एम एम', '४-५ एम एम'),
            ('5% Flowering', '५% फ्लॉवरिंग'),
            ('५० %  पाणी उतरणे', '५० %  पाणी उतरणे'),
            ('50% Bud Burst', '५०% पोंगा'),
            ('६-७ एम एम', '६-७ एम एम'),
            ('६-७ पान अवस्था', '६-७ पान अवस्था'),
            ('७-८ एमएम', '७-८ एमएम'),
            ('७० %  फ्लॉवरिंग', '७० %  फ्लॉवरिंग'),
            ('९-१० एम एम', '९-१० एम एम'),
            ('9-10 Leaf Stage', '९-१० पान अवस्था'),
            ('Foliar Spray', 'फवारणी'),
        ]
        
        for eng_name, mar_name in activity_names:
            activity, _ = Activity.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name}
            )
            activities[mar_name if mar_name else eng_name] = activity
        
        # Default activity for empty
        default_activity = activities.get('फवारणी', list(activities.values())[0])
        
        # Products (collect all unique)
        products = {}
        product_list = [
            ('Amil', 'अमिल', 'Fertilizer'),
            ('अमिल अर्क', 'अमिल अर्क', 'Fungicide'),
            ('Acrisio', 'अॅक्रिसीओ', 'Fertilizer'),
            ('Acrobat', 'अॅक्रोबॅट', 'Fertilizer'),
            ('Applaud', 'अॅप्लॉड', 'Fertilizer'),
            ('Abasin', 'अॅबॅसिन', 'Fertilizer'),
            ('आद्रा', 'आद्रा', 'Fertilizer'),
            ('Instant Lime', 'इन्स्टंट चुना', 'Fertilizer'),
            ('Imida', 'इमिडा', 'Fertilizer'),
            ('ईक्लोन', 'ईक्लोन', 'Fertilizer'),
            ('Ethrel', 'ईथ्रेल', 'Fertilizer'),
            ('ईथ्रेल ४० मिली (प्रति एकर)', 'ईथ्रेल ४० मिली (प्रति एकर)', 'Fungicide'),
            ('ईथ्रेल ८० मिली (प्रति एकर)', 'ईथ्रेल ८० मिली (प्रति एकर)', 'Fungicide'),
            ('ईनोव्हा कॅल/ काल्शियम', 'ईनोव्हा कॅल/ काल्शियम', 'Fungicide'),
            ('एक्स्पोनस ३४  ग्रॅम (प्रति एकर)', 'एक्स्पोनस ३४  ग्रॅम (प्रति एकर)', 'Fungicide'),
            ('M-45', 'एम ४५', 'Fertilizer'),
            ('LB Urea', 'एल बी युरिया', 'Fertilizer'),
            ('एलबी युरिया', 'एलबी युरिया', 'Fertilizer'),
            ('Eliot', 'एलियट', 'Fertilizer'),
            ('कमाब', 'कमाब', 'Fungicide'),
            ('Kumab 26', 'कमाब २६', 'Fertilizer'),
            ('Kasugamycin', 'कासुगामाइसिन', 'Fertilizer'),
            ('कुप्रोफिक्स', 'कुप्रोफिक्स', 'Fertilizer'),
            ('Cuman L', 'कुमान एल', 'Fertilizer'),
            ('Captaf', 'कॅपटाफ', 'Fertilizer'),
            ('Karathane Gold', 'कॅराथेन गोल्ड', 'Fertilizer'),
            ('Kosut', 'कोसूट', 'Fertilizer'),
            ('चि. फेरस', 'चि. फेरस', 'Fertilizer'),
            ('ची. फेरस', 'ची. फेरस', 'Fertilizer'),
            ('जीए', 'जीए', 'Fertilizer'),
            ('Jeshta', 'जेष्ठा', 'Fertilizer'),
            ('Zincmore', 'झिंकमोर', 'Fertilizer'),
            ('Zorvec Entecta', 'झोर्वेक एन्टेक्टा', 'Fertilizer'),
            ('Dormex', 'डॉर्मेक्स', 'Plant Growth Regulator'),
            ('Dashparni Ark', 'दशपर्णी अर्क', 'Bio Stimulant'),
            ('पॉलीराम', 'पॉलीराम', 'Fungicide'),
            ('पॉलीराम २.५ ग्रॅम', 'पॉलीराम २.५ ग्रॅम', 'Fungicide'),
            ('Polyvine', 'पॉलीवाईन', 'Fertilizer'),
            ('Proclaim', 'प्रोक्लेम', 'Fertilizer'),
            ('Profiler', 'प्रोफाइलर', 'Fertilizer'),
            ('फार्मामिन', 'फार्मामिन', 'Fungicide'),
            ('बम्बार्डियर', 'बम्बार्डियर', 'Fungicide'),
            ('Magnesium Sulphate', 'मॅग्नेशियम सल्फेट', 'Fertilizer'),
            ('Metador', 'मेटाडोर', 'Fertilizer'),
            ('Merivon', 'मेरीवॉन', 'Fertilizer'),
            ('Morchud', 'मोरचूद', 'Fertilizer'),
            ('Movento OD', 'मोव्हेंटो ओडी', 'Fertilizer'),
            ('Ranman', 'रॅनमॅन', 'Fertilizer'),
            ('Vemil Ark', 'वेमिल', 'Bio Stimulant'),
            ('Velzo', 'वेल्झो', 'Fertilizer'),
            ('व्हीटाफ्लोरा', 'व्हीटाफ्लोरा', 'Fertilizer'),
            ('Surplus', 'सरप्लस', 'Fertilizer'),
            ('Sulphur', 'सल्फर', 'Fertilizer'),
            ('Sulphur Dust', 'सल्फर डस्ट', 'Fertilizer'),
            ('Sunami', 'सुनामि', 'Fertilizer'),
            ('सॅलिसिओ', 'सॅलिसिओ', 'Fertilizer'),
            ('Score', 'स्कोर', 'Fertilizer'),
            ('स्टीम्प्लेक्स', 'स्टीम्प्लेक्स', 'Fungicide'),
            ('स्टॉपईट', 'स्टॉपईट', 'Fertilizer'),
            ('Spintor', 'स्पिंटॉर', 'Fertilizer'),
            ('Hasta', 'हस्ता', 'Fertilizer'),
            ('हस्था', 'हस्था', 'Fertilizer'),
            ('००:००:५०', '००:००:५०', 'Fertilizer'),
            ('00:52:34', '००:५२:३४', 'Fertilizer'),
            ('13:00:45', '१३:००:४५', 'Fertilizer'),
        ]
        
        for eng_name, mar_name, prod_type in product_list:
            product, _ = Product.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name, 'product_type': prod_type}
            )
            products[mar_name] = product
            products[eng_name] = product
        
        # Schedule data
        schedule = [
            {
                'day': 15,
                'activity': 'पानगळ',
                'info': '५०० – ६०० लि पाणी फवारणे. सकाळी लवकर स्प्रे घेणे.',
                'products': [{'name': '००:५२:३४', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'ईथ्रेल', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 0,
                'activity': 'पेस्टिंग',
                'info': '',
                'products': [{'name': '१३:००:४५', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'डॉर्मेक्स', 'dosage': 50.0, 'unit': 'मिली'}]
            },
            {
                'day': 6,
                'activity': 'Foliar Spray',
                'info': 'खोड ओलांडे धुण्याकरिता  एकरी १६०० – २००० ली. पाणी वापरणे.',
                'products': [{'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अॅप्लॉड', 'dosage': 0.75, 'unit': 'मिली'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सुनामि', 'dosage': 0.125, 'unit': 'मिली'}]
            },
            {
                'day': 7,
                'activity': 'शेंगदाणा',
                'info': '',
                'products': [{'name': 'मोरचूद', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'इन्स्टंट चुना', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 8,
                'activity': 'कापसलेली',
                'info': '',
                'products': [{'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'कॅराथेन गोल्ड', 'dosage': 0.3, 'unit': 'मिली'}]
            },
            {
                'day': 9,
                'activity': 'ग्रीन पॉइंट',
                'info': '',
                'products': [{'name': 'कुमान एल', 'dosage': 3.0, 'unit': 'मिली'}, {'name': 'पॉलीवाईन', 'dosage': 1.0, 'unit': 'मिलि'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 10,
                'activity': '५०% पोंगा',
                'info': '',
                'products': [{'name': 'एम ४५', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'मेटाडोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': '००:००:५०', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 11,
                'activity': '१००% पोंगा',
                'info': '',
                'products': [{'name': 'कुप्रोफिक्स', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 13,
                'activity': '३-४ पान अवस्था',
                'info': 'उडद्या अति जास्त प्रमाणात असेल तर स्पिंटोर – ०.२५ मिलि / लिटर स्प्रे घ्यावा.',
                'products': [{'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'पॉलीराम २.५ ग्रॅम', 'dosage_str': 'as needed'}, {'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'जीए', 'dosage': 0.25, 'unit': 'पीपीएम'}]
            },
            {
                'day': 15,
                'activity': 'फेल फुट काढणे',
                'info': '',
                'products': [{'name': 'कोसूट', 'dosage': 1.25, 'unit': 'ग्रॅम'}, {'name': 'कासुगामाइसिन', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 17,
                'activity': '६-७ पान अवस्था',
                'info': '',
                'products': [{'name': 'झोर्वेक एन्टेक्टा', 'dosage': 125.0, 'unit': 'मिली'}]
            },
            {
                'day': 18,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'कमाब', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'व्हीटाफ्लोरा', 'dosage': 5.0, 'unit': 'मीली'}]
            },
            {
                'day': 19,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कॅपटाफ', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'अॅबॅसिन', 'dosage': 0.75, 'unit': 'मिली'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 21,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 24,
                'activity': '९-१० पान अवस्था',
                'info': '',
                'products': [{'name': 'ईनोव्हा कॅल/ काल्शियम', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 25,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'वेल्झो', 'dosage': 800.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 26,
                'activity': 'दोडा अवस्था',
                'info': '',
                'products': [{'name': 'मेरीवॉन', 'dosage': 80.0, 'unit': 'मिली'}, {'name': 'एक्स्पोनस ३४  ग्रॅम (प्रति एकर)', 'dosage_str': 'as needed'}]
            },
            {
                'day': 29,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 30,
                'activity': '५% फ्लॉवरिंग',
                'info': '',
                'products': [{'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'दशपर्णी अर्क', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 33,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'रॅनमॅन', 'dosage': 80.0, 'unit': 'मिली'}]
            },
            {
                'day': 35,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅक्रिसीओ', 'dosage': 100.0, 'unit': 'मिली'}]
            },
            {
                'day': 37,
                'activity': '७० %  फ्लॉवरिंग',
                'info': '',
                'products': [{'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'पॉलीराम', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 38,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्पिंटॉर', 'dosage': 75.0, 'unit': 'मिली'}]
            },
            {
                'day': 39,
                'activity': '१ एम एम',
                'info': '',
                'products': [{'name': 'एलबी युरिया', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 41,
                'activity': '२ एम एम',
                'info': '',
                'products': [{'name': 'एलबी युरिया', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'स्टीम्प्लेक्स', 'dosage': 1.5, 'unit': 'ली.'}]
            },
            {
                'day': 42,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'एलियट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 44,
                'activity': '२-३ एम एम',
                'info': '',
                'products': [{'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}]
            },
            {
                'day': 45,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 46,
                'activity': '४-५ एम एम',
                'info': '',
                'products': [{'name': 'एलबी युरिया', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'ली.'}]
            },
            {
                'day': 48,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 1.2, 'unit': 'लि.'}, {'name': 'बम्बार्डियर', 'dosage': 1.0, 'unit': 'ली'}]
            },
            {
                'day': 50,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'एल बी युरिया', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 53,
                'activity': '६-७ एम एम',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 1.2, 'unit': 'लि.'}, {'name': 'बम्बार्डियर', 'dosage': 1.0, 'unit': 'ली'}, {'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'ली.'}]
            },
            {
                'day': 54,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अमिल अर्क', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिली'}, {'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}]
            },
            {
                'day': 55,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 56,
                'activity': '७-८ एमएम',
                'info': '',
                'products': [{'name': 'एलबी युरिया', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'जीए', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'व्हीटाफ्लोरा', 'dosage': 5.0, 'unit': 'मीली'}]
            },
            {
                'day': 58,
                'activity': '९-१० एम एम',
                'info': '',
                'products': [{'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'ली'}, {'name': 'हस्ता', 'dosage': 150.0, 'unit': 'ग्रॅम'}, {'name': 'सॅलिसिओ', 'dosage': 700.0, 'unit': 'मीली'}]
            },
            {
                'day': 60,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्टॉपईट', 'dosage': 1.0, 'unit': 'ली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 1.0, 'unit': 'किलो'}]
            },
            {
                'day': 64,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'स्कोर', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 66,
                'activity': '१०-१२ एमएम',
                'info': '',
                'products': [{'name': 'व्हीटाफ्लोरा', 'dosage': 5.0, 'unit': 'मीली'}, {'name': 'कमाब', 'dosage': 2.5, 'unit': 'मीली'}, {'name': 'हस्था', 'dosage': 100.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 78,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'व्हीटाफ्लोरा', 'dosage': 5.0, 'unit': 'मीली'}, {'name': 'कमाब', 'dosage': 2.5, 'unit': 'मीली'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 80,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'ची. फेरस', 'dosage': 12.0, 'unit': '%'}, {'name': 'सॅलिसिओ', 'dosage': 1.5, 'unit': 'मीली'}]
            },
            {
                'day': 85,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'हस्ता', 'dosage': 100.0, 'unit': 'ग्रॅम'}, {'name': 'फार्मामिन', 'dosage': 1.5, 'unit': 'ली.'}, {'name': 'ईथ्रेल ८० मिली (प्रति एकर)', 'dosage_str': 'as needed'}]
            },
            {
                'day': 90,
                'activity': '१५-१६ एम एम',
                'info': '',
                'products': [{'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'ईक्लोन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'चि. फेरस', 'dosage': 1.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 95,
                'activity': '२५ %  पाणी उतरणे',
                'info': '',
                'products': [{'name': 'हस्ता', 'dosage': 100.0, 'unit': 'ग्रॅम'}, {'name': 'व्हीटाफ्लोरा', 'dosage': 5.0, 'unit': 'मीली'}, {'name': 'फार्मामिन', 'dosage': 1.5, 'unit': 'ली'}, {'name': 'ईथ्रेल ४० मिली (प्रति एकर)', 'dosage_str': 'as needed'}]
            },
            {
                'day': 100,
                'activity': '५० %  पाणी उतरणे',
                'info': 'कलर साठी गरज असेल तर',
                'products': [{'name': 'हस्ता', 'dosage': 100.0, 'unit': '(प्रति'}, {'name': 'व्हीटाफ्लोरा', 'dosage': 5.0, 'unit': 'मीली'}, {'name': 'फार्मामिन', 'dosage': 1.5, 'unit': 'ली'}]
            },
            {
                'day': 110,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सल्फर डस्ट', 'dosage': 8.0, 'unit': 'किलो'}]
            },
        ]
        
        # Insert schedule
        for item in schedule:
            activity_obj = activities.get(item['activity'], default_activity)
            
            day_range = DayRange.objects.create(
                crop_variety=variety,
                activity=activity_obj,
                start_day=item['day'],
                end_day=item['day'],
                info=item['info'],
                info_marathi=item['info']
            )
            
            for prod_data in item['products']:
                product_obj = products.get(prod_data['name'])
                if product_obj:
                    if 'dosage' in prod_data:
                        unit = self.normalize_unit(prod_data['unit'])
                        DayRangeProduct.objects.create(
                            day_range=day_range,
                            product=product_obj,
                            dosage=prod_data['dosage'],
                            dosage_unit=unit
                        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {variety.name}'))

    def import_thompson_seedless(self, crop):
        """Import Thompson Seedless variety schedule"""
        variety, _ = CropVariety.objects.get_or_create(
            crop=crop,
            name='Thompson Seedless',
            defaults={'name_marathi': 'थॉम्पसन सीडलेस'}
        )
        
        # Activities
        activities = {}
        activity_names = [
            ('Cotton Boll Stage', 'कापसलेली'),
            ('Green Point', 'ग्रीन पॉइंट'),
            ('Bead Stage', 'दोडा अवस्था'),
            ('पाणी उतरणे', 'पाणी उतरणे'),
            ('Leaf Fall', 'पानगळ'),
            ('Pasting', 'पेस्टिंग'),
            ('फेल फुट काढणे', 'फेल फुट काढणे'),
            ('Groundnut Stage', 'शेंगदाणा'),
            ('1 MM Berry', '१ एम एम'),
            ('10-12 MM Berry', '१०-१२ एमएम'),
            ('100% Bud Burst', '१००% पोंगा'),
            ('15-16 MM Berry', '१५-१६ एम एम'),
            ('२ एम एम', '२ एम एम'),
            ('2-3 MM Berry', '२-३ एम एम'),
            ('३-४ पान अवस्था', '३-४ पान अवस्था'),
            ('३०% पाणी उतरणे', '३०% पाणी उतरणे'),
            ('४-५ एम एम', '४-५ एम एम'),
            ('5% Flowering', '५% फ्लॉवरिंग'),
            ('50% Bud Burst', '५०% पोंगा'),
            ('६-७ एम एम', '६-७ एम एम'),
            ('६-७ पान अवस्था', '६-७ पान अवस्था'),
            ('७० %  फ्लॉवरिंग', '७० %  फ्लॉवरिंग'),
            ('८-९ एम एम', '८-९ एम एम'),
            ('9-10 Leaf Stage', '९-१० पान अवस्था'),
            ('Foliar Spray', 'फवारणी'),
        ]
        
        for eng_name, mar_name in activity_names:
            activity, _ = Activity.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name}
            )
            activities[mar_name if mar_name else eng_name] = activity
        
        # Default activity for empty
        default_activity = activities.get('फवारणी', list(activities.values())[0])
        
        # Products (collect all unique)
        products = {}
        product_list = [
            ('अक्रिसीओ', 'अक्रिसीओ', 'Fertilizer'),
            ('Amil', 'अमिल', 'Fertilizer'),
            ('अमिल अर्क', 'अमिल अर्क', 'Fungicide'),
            ('Acrobat', 'अॅक्रोबॅट', 'Fertilizer'),
            ('Antracol', 'अॅन्ट्राकॉल', 'Fertilizer'),
            ('Applaud', 'अॅप्लॉड', 'Fertilizer'),
            ('Abasin', 'अॅबॅसिन', 'Fertilizer'),
            ('अ‍ॅलिएट', 'अ‍ॅलिएट', 'Fertilizer'),
            ('आद्रा', 'आद्रा', 'Fertilizer'),
            ('इनोव्हाकॅल/ पॉलिकार्ब Ca', 'इनोव्हाकॅल/ पॉलिकार्ब Ca', 'Fertilizer'),
            ('Instant Lime', 'इन्स्टंट चुना', 'Fertilizer'),
            ('Imida', 'इमिडा', 'Fertilizer'),
            ('ईक्लोन', 'ईक्लोन', 'Fertilizer'),
            ('Ethrel', 'ईथ्रेल', 'Fertilizer'),
            ('ईनोव्हा कॅल', 'ईनोव्हा कॅल', 'Fertilizer'),
            ('Exponus', 'एक्स्पोनस', 'Fertilizer'),
            ('M-45', 'एम ४५', 'Fertilizer'),
            ('LB Urea', 'एल बी युरिया', 'Fertilizer'),
            ('Kumab 26', 'कमाब २६', 'Fertilizer'),
            ('कुप्रोफिक्स', 'कुप्रोफिक्स', 'Fertilizer'),
            ('Cuman L', 'कुमान एल', 'Fertilizer'),
            ('Captaf', 'कॅपटाफ', 'Fertilizer'),
            ('Karathane Gold', 'कॅराथेन गोल्ड', 'Fertilizer'),
            ('कॉन्टाफ', 'कॉन्टाफ', 'Fertilizer'),
            ('जीए', 'जीए', 'Fertilizer'),
            ('Jeshta', 'जेष्ठा', 'Fertilizer'),
            ('Zincmore', 'झिंकमोर', 'Fertilizer'),
            ('Zorvec Entecta', 'झोर्वेक एन्टेक्टा', 'Fertilizer'),
            ('Tilt', 'टिल्ट', 'Fertilizer'),
            ('डायमोर', 'डायमोर', 'Fungicide'),
            ('Dormex', 'डॉर्मेक्स', 'Plant Growth Regulator'),
            ('Dashparni Ark', 'दशपर्णी अर्क', 'Bio Stimulant'),
            ('Polyvine', 'पॉलीवाईन', 'Fertilizer'),
            ('Proclaim', 'प्रोक्लेम', 'Fertilizer'),
            ('Profiler', 'प्रोफाइलर', 'Fertilizer'),
            ('फार्मामिन', 'फार्मामिन', 'Fungicide'),
            ('बंबार्डिअर', 'बंबार्डिअर', 'Fertilizer'),
            ('बड बिल्डर / बड', 'बड बिल्डर / बड', 'Fertilizer'),
            ('बोरॉन', 'बोरॉन', 'Fertilizer'),
            ('मॅग्नेशियम  सल्फेट', 'मॅग्नेशियम  सल्फेट', 'Fungicide'),
            ('Magnesium Sulphate', 'मॅग्नेशियम सल्फेट', 'Fertilizer'),
            ('Metador', 'मेटाडोर', 'Fertilizer'),
            ('मेरीवोन', 'मेरीवोन', 'Fungicide'),
            ('Morchud', 'मोरचूद', 'Fertilizer'),
            ('Movento OD', 'मोव्हेंटो ओडी', 'Fertilizer'),
            ('Ranman', 'रॅनमॅन', 'Fertilizer'),
            ('Vemil Ark', 'वेमिल', 'Bio Stimulant'),
            ('Velzo', 'वेल्झो', 'Fertilizer'),
            ('Vitaflora', 'व्हिटाफ्लोरा', 'Fertilizer'),
            ('Surplus', 'सरप्लस', 'Fertilizer'),
            ('Sulphur', 'सल्फर', 'Fertilizer'),
            ('Sulphur Dust', 'सल्फर डस्ट', 'Fertilizer'),
            ('Citox (CPPU)', 'सिटोऑक्स (सीपीपीयू)', 'Plant Growth Regulator'),
            ('Sunami', 'सुनामि', 'Fertilizer'),
            ('Salicio', 'सॅलीसिओ', 'Fertilizer'),
            ('Score', 'स्कोर', 'Fertilizer'),
            ('स्टीम्प्लेक्स', 'स्टीम्प्लेक्स', 'Fungicide'),
            ('स्टॉपईट', 'स्टॉपईट', 'Fertilizer'),
            ('Spintor', 'स्पिंटॉर', 'Fertilizer'),
            ('Hasta', 'हस्ता', 'Fertilizer'),
            ('००:००:५०', '००:००:५०', 'Fertilizer'),
            ('00:49:32', '००:४९:३२', 'Fertilizer'),
            ('00:52:34', '००:५२:३४', 'Fertilizer'),
            ('13:00:45', '१३:००:४५', 'Fertilizer'),
        ]
        
        for eng_name, mar_name, prod_type in product_list:
            product, _ = Product.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name, 'product_type': prod_type}
            )
            products[mar_name] = product
            products[eng_name] = product
        
        # Schedule data
        schedule = [
            {
                'day': 10,
                'activity': 'पानगळ',
                'info': '५०० – ६०० लि पाणी फवारणे. सकाळी लवकर स्प्रे घेणे.',
                'products': [{'name': '००:५२:३४', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'ईथ्रेल', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 0,
                'activity': 'पेस्टिंग',
                'info': 'पेस्टमध्ये गेरू घेतल्यास एकसारखे कवरेज मिळते.  एकरी ६० ते ८० लीटर पाणी वापरणे .',
                'products': [{'name': '१३:००:४५', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'डॉर्मेक्स', 'dosage': 50.0, 'unit': 'मिली'}]
            },
            {
                'day': 6,
                'activity': 'Foliar Spray',
                'info': 'खोड ओलांडे धुण्याकरिता  एकरी १६०० – २००० ली. पाणी वापरणे.',
                'products': [{'name': 'अॅप्लॉड', 'dosage': 0.75, 'unit': 'मिली'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'सुनामि', 'dosage': 0.125, 'unit': 'मिली'}]
            },
            {
                'day': 7,
                'activity': 'शेंगदाणा',
                'info': '',
                'products': [{'name': 'मोरचूद', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'इन्स्टंट चुना', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 8,
                'activity': 'कापसलेली',
                'info': '',
                'products': [{'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'कॅराथेन गोल्ड', 'dosage': 0.3, 'unit': 'मिली'}, {'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सिटोऑक्स (सीपीपीयू)', 'dosage': 200.0, 'unit': 'मिली'}]
            },
            {
                'day': 9,
                'activity': 'ग्रीन पॉइंट',
                'info': '',
                'products': [{'name': '००:४९:३२', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'कुमान एल', 'dosage': 3.0, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'टिल्ट', 'dosage': 20.0, 'unit': 'मिली'}]
            },
            {
                'day': 10,
                'activity': '५०% पोंगा',
                'info': '',
                'products': [{'name': 'कॅपटाफ', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'पॉलीवाईन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'मेटाडोर', 'dosage': 0.5, 'unit': 'मिली'}]
            },
            {
                'day': 11,
                'activity': 'Foliar Spray',
                'info': 'पाऊस असल्यास एम ४५  अॅड करून घेणे',
                'products': [{'name': '००:००:५०', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'बड बिल्डर / बड', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिलि.'}]
            },
            {
                'day': 12,
                'activity': '१००% पोंगा',
                'info': 'उडद्या अति जास्त प्रमाणात असेल तर  स्पिंटॉर – ०.२५ मिली/लि स्प्रे घ्यावा.',
                'products': [{'name': '००:४९:३२', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}]
            },
            {
                'day': 13,
                'activity': '३-४ पान अवस्था',
                'info': '',
                'products': [{'name': 'कुप्रोफिक्स', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 15,
                'activity': 'फेल फुट काढणे',
                'info': '',
                'products': [{'name': 'झोर्वेक एन्टेक्टा', 'dosage': 125.0, 'unit': 'मिली'}]
            },
            {
                'day': 17,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅबॅसिन', 'dosage': 0.75, 'unit': 'मिली'}, {'name': 'इनोव्हाकॅल/ पॉलिकार्ब Ca', 'dosage': 1.5, 'unit': 'मिलि'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 18,
                'activity': '६-७ पान अवस्था',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'जीए', 'dosage': 5.0, 'unit': 'पीपीएम'}]
            },
            {
                'day': 20,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कॉन्टाफ', 'dosage': 1.0, 'unit': 'मिली'}, {'name': 'कॅपटाफ', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिलि.'}]
            },
            {
                'day': 22,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'वेल्झो', 'dosage': 800.0, 'unit': 'ग्रॅम'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'जीए', 'dosage': 10.0, 'unit': 'पीपीएम'}, {'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 24,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'ईनोव्हा कॅल', 'dosage': 1.5, 'unit': 'मिली'}, {'name': 'बोरॉन', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'हस्ता', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 25,
                'activity': '९-१० पान अवस्था',
                'info': '',
                'products': [{'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': '००:००:५०', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'अॅन्ट्राकॉल', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 26,
                'activity': 'दोडा अवस्था',
                'info': '',
                'products': [{'name': 'मेरीवोन', 'dosage': 80.0, 'unit': 'मिली'}, {'name': 'एक्स्पोनस', 'dosage': 34.0, 'unit': 'ग्रॅम'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 27,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 29,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': '००:४९:३२', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिली'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिलि.'}]
            },
            {
                'day': 30,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 32,
                'activity': '५% फ्लॉवरिंग',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'दशपर्णी अर्क', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 33,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'रॅनमॅन', 'dosage': 80.0, 'unit': 'मिली'}]
            },
            {
                'day': 35,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अक्रिसीओ', 'dosage': 100.0, 'unit': 'मिली'}]
            },
            {
                'day': 36,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 37,
                'activity': '७० %  फ्लॉवरिंग',
                'info': 'रशिया व चीन साठी अ‍ॅलिएट चा स्प्रे घेवू नये. गळ पाहिजे असेल तरच  जीए घेणे.',
                'products': [{'name': 'अ‍ॅलिएट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'जीए', 'dosage': 10.0, 'unit': 'पीपीएम'}]
            },
            {
                'day': 38,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्पिंटॉर', 'dosage': 75.0, 'unit': 'मिली'}]
            },
            {
                'day': 39,
                'activity': '१ एम एम',
                'info': 'गळ पाहिजे असेल तरच हा स्प्रे घेणे.',
                'products': [{'name': 'एल बी युरिया', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'जीए', 'dosage': 10.0, 'unit': 'पीपीएम'}]
            },
            {
                'day': 40,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 41,
                'activity': '२ एम एम',
                'info': 'सेटिंग स्प्रे',
                'products': [{'name': 'एल बी युरिया', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'स्टीम्प्लेक्स', 'dosage': 1.5, 'unit': 'ली.'}, {'name': 'जीए', 'dosage': 9.0, 'unit': '-१२'}]
            },
            {
                'day': 42,
                'activity': '२-३ एम एम',
                'info': '',
                'products': [{'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिलि'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 44,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 46,
                'activity': 'Foliar Spray',
                'info': 'रशिया व चीन साठी हा स्प्रे घेवू नये. आवश्यक असल्यास  रॅनमॅन- ८० मिली (प्रति एकर)  हा स्प्रे घ्यावा.',
                'products': [{'name': 'अ‍ॅलिएट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 48,
                'activity': '४-५ एम एम',
                'info': 'सायझिंग स्प्रे -१',
                'products': [{'name': 'एल बी युरिया', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'जीए', 'dosage': 24.0, 'unit': 'ग्रॅम'}, {'name': 'सिटोऑक्स (सीपीपीयू)', 'dosage': 600.0, 'unit': 'मिली'}, {'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'ली.'}]
            },
            {
                'day': 49,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्टॉपईट', 'dosage': 1.0, 'unit': 'ली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 1.0, 'unit': 'किलो'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 50,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'एल बी युरिया', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'जीए', 'dosage': 20.0, 'unit': 'पीपीएम'}, {'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 51,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 1.0, 'unit': 'लि.'}, {'name': 'बंबार्डिअर', 'dosage': 1.0, 'unit': 'ली'}]
            },
            {
                'day': 52,
                'activity': '६-७ एम एम',
                'info': 'सायझिंग स्प्रे -२',
                'products': [{'name': 'जीए', 'dosage': 24.0, 'unit': 'ग्रॅम'}, {'name': 'डायमोर', 'dosage': 600.0, 'unit': 'मिली'}, {'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'ली.'}]
            },
            {
                'day': 53,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिलि'}, {'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अमिल अर्क', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 55,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'एल बी युरिया', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'जीए', 'dosage': 20.0, 'unit': 'पीपीएम'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 56,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 58,
                'activity': '८-९ एम एम',
                'info': 'सायझिंग स्प्रे -३',
                'products': [{'name': 'जीए', 'dosage': 18.0, 'unit': 'ग्रॅम'}, {'name': 'सिटोऑक्स (सीपीपीयू)', 'dosage': 600.0, 'unit': 'मिली'}, {'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'ली.'}]
            },
            {
                'day': 60,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'कमाब २६', 'dosage': 1.0, 'unit': 'लि.'}]
            },
            {
                'day': 64,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सल्फर', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'स्कोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 66,
                'activity': '१०-१२ एमएम',
                'info': '',
                'products': [{'name': 'मॅग्नेशियम  सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'ईक्लोन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 69,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिलि'}]
            },
            {
                'day': 73,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिलि'}, {'name': 'ईक्लोन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 80,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 85,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'फार्मामिन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 90,
                'activity': '१५-१६ एम एम',
                'info': '',
                'products': [{'name': 'ईक्लोन', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'जीए', 'dosage': 10.0, 'unit': 'पीपीएम'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 95,
                'activity': 'पाणी उतरणे',
                'info': '',
                'products': [{'name': 'फार्मामिन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 100,
                'activity': '३०% पाणी उतरणे',
                'info': 'डस्टिंग करूनच पेपर लावणे.',
                'products': [{'name': 'सल्फर डस्ट', 'dosage': 8.0, 'unit': 'किलो'}]
            },
        ]
        
        # Insert schedule
        for item in schedule:
            activity_obj = activities.get(item['activity'], default_activity)
            
            day_range = DayRange.objects.create(
                crop_variety=variety,
                activity=activity_obj,
                
                start_day=item['day'],
                end_day=item['day'],
                info=item['info'],
                info_marathi=item['info']
            )
            
            for prod_data in item['products']:
                product_obj = products.get(prod_data['name'])
                if product_obj:
                    if 'dosage' in prod_data:
                        unit = self.normalize_unit(prod_data['unit'])
                        DayRangeProduct.objects.create(
                            day_range=day_range,
                            product=product_obj,
                            dosage=prod_data['dosage'],
                            dosage_unit=unit
                        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {variety.name}'))

    def import_ard_35(self, crop):
        """Import ARD 35 variety schedule"""
        variety, _ = CropVariety.objects.get_or_create(
            crop=crop,
            name='ARD 35',
            defaults={'name_marathi': 'एआरडी ३५'}
        )
        
        # Activities
        activities = {}
        activity_names = [
            ('Cotton Boll Stage', 'कापसलेली'),
            ('Green Point', 'ग्रीन पॉइंट'),
            ('Bead Stage', 'दोडा अवस्था'),
            ('Leaf Fall', 'पानगळ'),
            ('Pasting', 'पेस्टिंग'),
            ('Groundnut Stage', 'शेंगदाणा'),
            ('10-12 MM Berry', '१०-१२ एमएम'),
            ('100% Bud Burst', '१००% पोंगा'),
            ('2-3 MM Berry', '२-३ एम एम'),
            ('२-३ मणी कलर', '२-३ मणी कलर'),
            ('३ – ५ एमएम', '३ – ५ एमएम'),
            ('४-५ पानअवस्था', '४-५ पानअवस्था'),
            ('4-6 MM Berry', '४-६ एम एम'),
            ('5 cm Shoot', '५ सेमी. शूट'),
            ('5% Flowering', '५% फ्लॉवरिंग'),
            ('50% Bud Burst', '५०% पोंगा'),
            ('6-8 MM Berry', '६ -८ एम एम'),
            ('7-8 Leaf Stage', '७-८ पान अवस्था'),
            ('70% Flowering', '७०% फ्लॉवरिंग'),
            ('८- १० एम एम', '८- १० एम एम'),
            ('Foliar Spray', 'फवारणी'),
        ]
        
        for eng_name, mar_name in activity_names:
            activity, _ = Activity.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name}
            )
            activities[mar_name if mar_name else eng_name] = activity
        
        # Default activity for empty
        default_activity = activities.get('फवारणी', list(activities.values())[0])
        
        # Products (collect all unique)
        products = {}
        product_list = [
            ('अक्रिसीओ', 'अक्रिसीओ', 'Fertilizer'),
            ('Amil', 'अमिल', 'Fertilizer'),
            ('Ammonium Sulphate', 'अमोनियम सल्फेट', 'Fertilizer'),
            ('अर्द्रा ०.५ ग्रॅम', 'अर्द्रा ०.५ ग्रॅम', 'Fungicide'),
            ('Acrobat', 'अॅक्रोबॅट', 'Fertilizer'),
            ('Antracol', 'अॅन्ट्राकॉल', 'Fertilizer'),
            ('Applaud', 'अॅप्लॉड', 'Fertilizer'),
            ('अॅबॅसिन ०.७५ मिलि', 'अॅबॅसिन ०.७५ मिलि', 'Fungicide'),
            ('आद्रा', 'आद्रा', 'Fertilizer'),
            ('Armachura', 'आरमाचुरा', 'Fertilizer'),
            ('Imida', 'इमिडा', 'Fertilizer'),
            ('Eclon Max', 'ईक्लोन मॅक्स', 'Fertilizer'),
            ('Ethrel', 'ईथ्रेल', 'Fertilizer'),
            ('Exponus', 'एक्स्पोनस', 'Fertilizer'),
            ('M-45', 'एम ४५', 'Fertilizer'),
            ('LB Urea', 'एल बी युरिया', 'Fertilizer'),
            ('Eliot', 'एलियट', 'Fertilizer'),
            ('कमाब  २६', 'कमाब  २६', 'Fungicide'),
            ('Kumab 26', 'कमाब २६', 'Fertilizer'),
            ('Kasugamycin', 'कासुगामाइसिन', 'Fertilizer'),
            ('Cuman L', 'कुमान एल', 'Fertilizer'),
            ('Captaf', 'कॅपटाफ', 'Fertilizer'),
            ('Karathane Gold', 'कॅराथेन गोल्ड', 'Fertilizer'),
            ('कोसूट / कोसाईड', 'कोसूट / कोसाईड', 'Fertilizer'),
            ('चि. फेरस', 'चि. फेरस', 'Fertilizer'),
            ('Lime', 'चुना', 'Fertilizer'),
            ('जेष्टा', 'जेष्टा', 'Fertilizer'),
            ('Jeshta', 'जेष्ठा', 'Fertilizer'),
            ('Zincmore', 'झिंकमोर', 'Fertilizer'),
            ('झिंकमोर  १ मिली', 'झिंकमोर  १ मिली', 'Fungicide'),
            ('Zorvec Entecta', 'झोर्वेक एन्टेक्टा', 'Fertilizer'),
            ('Dormex', 'डॉर्मेक्स', 'Plant Growth Regulator'),
            ('Dashparni Ark', 'दशपर्णी अर्क', 'Bio Stimulant'),
            ('निसोडियम', 'निसोडियम', 'Fungicide'),
            ('Polycarb Ca', 'पॉलीकार्ब Ca', 'Fertilizer'),
            ('Polyvine', 'पॉलीवाईन', 'Fertilizer'),
            ('Proclaim', 'प्रोक्लेम', 'Fertilizer'),
            ('प्रोजीब  इजी जीए', 'प्रोजीब  इजी जीए', 'Fertilizer'),
            ('Profiler', 'प्रोफाइलर', 'Fertilizer'),
            ('Farmamin', 'फार्मामीन', 'Fertilizer'),
            ('Bombardier', 'बंबार्डीयर', 'Fertilizer'),
            ('बड बिल्डर / बड', 'बड बिल्डर / बड', 'Fertilizer'),
            ('बोरॉन', 'बोरॉन', 'Fertilizer'),
            ('Magnesium Sulphate', 'मॅग्नेशियम सल्फेट', 'Fertilizer'),
            ('Metador', 'मेटाडोर', 'Fertilizer'),
            ('Merivon', 'मेरीवॉन', 'Fertilizer'),
            ('Morchud', 'मोरचूद', 'Fertilizer'),
            ('Movento OD', 'मोव्हेंटो ओडी', 'Fertilizer'),
            ('Urea', 'युरिया', 'Fertilizer'),
            ('Ranman', 'रॅनमॅन', 'Fertilizer'),
            ('Vemil Ark', 'वेमिल', 'Bio Stimulant'),
            ('वेमिल अर्क 10 मिलि', 'वेमिल अर्क 10 मिलि', 'Fungicide'),
            ('Velzo', 'वेल्झो', 'Fertilizer'),
            ('Vitaflora', 'व्हिटाफ्लोरा', 'Fertilizer'),
            ('Surplus', 'सरप्लस', 'Fertilizer'),
            ('Sulphur', 'सल्फर', 'Fertilizer'),
            ('Sulphur Dust', 'सल्फर डस्ट', 'Fertilizer'),
            ('Sunami', 'सुनामि', 'Fertilizer'),
            ('Salicio', 'सॅलीसिओ', 'Fertilizer'),
            ('स्टीम्प्लेक्स', 'स्टीम्प्लेक्स', 'Fungicide'),
            ('Stopit', 'स्टॉपिट', 'Fertilizer'),
            ('Spintor', 'स्पिंटॉर', 'Fertilizer'),
            ('Hasta', 'हस्ता', 'Fertilizer'),
            ('००:००:५०', '००:००:५०', 'Fertilizer'),
            ('00:49:32', '००:४९:३२', 'Fertilizer'),
            ('13:00:45', '१३:००:४५', 'Fertilizer'),
        ]
        
        for eng_name, mar_name, prod_type in product_list:
            product, _ = Product.objects.get_or_create(
                name=eng_name,
                defaults={'name_marathi': mar_name, 'product_type': prod_type}
            )
            products[mar_name] = product
            products[eng_name] = product
        
        # Schedule data
        schedule = [
            {
                'day': 15,
                'activity': 'पानगळ',
                'info': '६०० ली. पाणी फवारणे व उलटा पालटा स्प्रे घेणे. सकाळी लवकर स्प्रे घेणे.',
                'products': [{'name': 'अमोनियम सल्फेट', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'ईथ्रेल', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 0,
                'activity': 'पेस्टिंग',
                'info': 'पेस्टमध्ये गेरू घेतल्यास एकसारखी फुट मिळते. एकरी ६० ते ८० लीटर पाणी वापरणे .',
                'products': [{'name': '१३:००:४५', 'dosage': 50.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'डॉर्मेक्स', 'dosage': 50.0, 'unit': 'मिली'}]
            },
            {
                'day': 3,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'युरिया', 'dosage': 10.0, 'unit': 'ग्रॅम'}, {'name': 'दशपर्णी अर्क', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सल्फर', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 6,
                'activity': 'Foliar Spray',
                'info': 'एकरी   १६०० - २०००  ली. पाणी वापरणे.',
                'products': [{'name': 'हस्ता', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'अॅप्लॉड', 'dosage': 0.75, 'unit': 'मिली'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'सुनामि', 'dosage': 0.125, 'unit': 'मिली'}]
            },
            {
                'day': 7,
                'activity': 'शेंगदाणा',
                'info': 'गच्च फवारा घेणे.',
                'products': [{'name': 'मोरचूद', 'dosage': 5.0, 'unit': 'ग्रॅम'}, {'name': 'चुना', 'dosage': 1.75, 'unit': 'ग्रॅम'}, {'name': 'सल्फर', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 8,
                'activity': 'कापसलेली',
                'info': 'उडद्यासाठी संध्याकाळी स्प्रे घेणे.',
                'products': [{'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'कॅराथेन गोल्ड', 'dosage': 0.3, 'unit': 'मिली'}, {'name': 'एम ४५', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'वेमिल अर्क 10 मिलि', 'dosage_str': 'as needed'}]
            },
            {
                'day': 9,
                'activity': 'ग्रीन पॉइंट',
                'info': '',
                'products': [{'name': '००:४९:३२', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'कुमान एल', 'dosage': 3.0, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 10,
                'activity': '५०% पोंगा',
                'info': '',
                'products': [{'name': 'मेटाडोर', 'dosage': 0.5, 'unit': 'मिली'}, {'name': 'कॅपटाफ', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'पॉलीवाईन', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 11,
                'activity': '१००% पोंगा',
                'info': '',
                'products': [{'name': '००:००:५०', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'बड बिल्डर / बड', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 12,
                'activity': 'Foliar Spray',
                'info': 'उडद्या अति जास्त प्रमाणात असेल तर स्पिंटोर – ०.२५ मिलि / लीटर स्प्रे घ्यावा.',
                'products': [{'name': '००:४९:३२', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'एम ४५', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'इमिडा', 'dosage': 0.5, 'unit': 'मिली'}]
            },
            {
                'day': 13,
                'activity': '५ सेमी. शूट',
                'info': '',
                'products': [{'name': 'झोर्वेक एन्टेक्टा', 'dosage': 125.0, 'unit': 'मिली'}]
            },
            {
                'day': 14,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅन्ट्राकॉल', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'एल बी युरिया', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 15,
                'activity': '४-५ पानअवस्था',
                'info': '',
                'products': [{'name': 'कोसूट / कोसाईड', 'dosage': 1.25, 'unit': 'ग्रॅम'}, {'name': 'कासुगामाइसिन', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 16,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'पॉलीकार्ब Ca', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 17,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अॅबॅसिन ०.७५ मिलि', 'dosage_str': 'as needed'}, {'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिली'}, {'name': 'स्टीम्प्लेक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 18,
                'activity': '७-८ पान अवस्था',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 20,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सल्फर', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'कॅपटाफ', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'वेमिल', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 22,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'पॉलीकार्ब Ca', 'dosage': 2.0, 'unit': 'मिली'}, {'name': 'बोरॉन', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'हस्ता', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}]
            },
            {
                'day': 23,
                'activity': 'Foliar Spray',
                'info': 'शेंडा  वाढीच्या वेगानुसार नत्राचे नियोजन करने.',
                'products': [{'name': 'वेल्झो', 'dosage': 800.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 24,
                'activity': 'Foliar Spray',
                'info': '२५ ते ३० दिवसात पानदेठ परीक्षण करून घेणे.',
                'products': [{'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': '००:४९:३२', 'dosage': 2.0, 'unit': 'ग्रॅम'}, {'name': 'अॅन्ट्राकॉल', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 25,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सरप्लस', 'dosage': 1.0, 'unit': 'मिली'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}, {'name': 'झिंकमोर', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 26,
                'activity': 'दोडा अवस्था',
                'info': '',
                'products': [{'name': 'मेरीवॉन', 'dosage': 80.0, 'unit': 'मिलि'}, {'name': 'एक्स्पोनस', 'dosage': 34.0, 'unit': 'ग्रॅम'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 28,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'प्रोफाइलर', 'dosage': 3.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 30,
                'activity': '५% फ्लॉवरिंग',
                'info': '',
                'products': [{'name': 'अॅक्रोबॅट', 'dosage': 1.0, 'unit': 'ग्रॅम'}, {'name': 'जेष्ठा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'अर्द्रा ०.५ ग्रॅम', 'dosage_str': 'as needed'}]
            },
            {
                'day': 31,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'अक्रिसीओ', 'dosage': 100.0, 'unit': 'मिली'}]
            },
            {
                'day': 33,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'रॅनमॅन', 'dosage': 80.0, 'unit': 'मिली'}]
            },
            {
                'day': 35,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये यासाठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 37,
                'activity': '७०% फ्लॉवरिंग',
                'info': '',
                'products': [{'name': 'एलियट', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 38,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्पिंटॉर', 'dosage': 75.0, 'unit': 'मिलि'}]
            },
            {
                'day': 39,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'निसोडियम', 'dosage': 200.0, 'unit': 'मिली'}]
            },
            {
                'day': 42,
                'activity': '२-३ एम एम',
                'info': 'पान देठ परीक्षण करणे.',
                'products': [{'name': 'एलियट', 'dosage': 2.0, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 44,
                'activity': '३ – ५ एमएम',
                'info': '',
                'products': [{'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'झिंकमोर  १ मिली', 'dosage_str': 'as needed'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 45,
                'activity': 'Foliar Spray',
                'info': 'स्कॉर्चिंग येवू नये या साठी मागील पुढील स्प्रे तपासून घेणे.',
                'products': [{'name': 'मोव्हेंटो ओडी', 'dosage': 1.0, 'unit': 'मिली'}]
            },
            {
                'day': 47,
                'activity': '४-६ एम एम',
                'info': '',
                'products': [{'name': 'एल बी युरिया', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'बंबार्डीयर', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 49,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'स्टॉपिट', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 51,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'आरमाचुरा', 'dosage': 250.0, 'unit': 'मिली'}]
            },
            {
                'day': 53,
                'activity': '६ -८ एम एम',
                'info': '',
                'products': [{'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 56,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'जेष्टा', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 58,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'आरमाचुरा', 'dosage': 250.0, 'unit': 'मिली'}]
            },
            {
                'day': 60,
                'activity': '८- १० एम एम',
                'info': 'सरासरी ८० % पेक्षा जास्त मणी ८ एम एम चे असावे.',
                'products': [{'name': 'एल बी युरिया', 'dosage': 3.0, 'unit': 'ग्रॅम'}, {'name': 'प्रोजीब  इजी जीए', 'dosage': 2.5, 'unit': 'पीपीएम'}, {'name': 'ईक्लोन मॅक्स', 'dosage': 1.0, 'unit': 'लि'}]
            },
            {
                'day': 63,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'कमाब  २६', 'dosage': 2.5, 'unit': 'मिली'}]
            },
            {
                'day': 65,
                'activity': '१०-१२ एमएम',
                'info': '',
                'products': [{'name': 'प्रोक्लेम', 'dosage': 0.25, 'unit': 'ग्रॅम'}, {'name': 'हस्ता', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 67,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'मॅग्नेशियम सल्फेट', 'dosage': 2.5, 'unit': 'ग्रॅम'}, {'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'आद्रा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 72,
                'activity': 'Foliar Spray',
                'info': 'पान देठ परीक्षण करणे',
                'products': [{'name': 'ईक्लोन मॅक्स', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'कमाब २६', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'जेष्ठा', 'dosage': 0.25, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 76,
                'activity': 'Foliar Spray',
                'info': 'पाणी उतरण्यापूर्वी दहा दिवस आधी फवारणे',
                'products': [{'name': 'आद्रा', 'dosage': 0.5, 'unit': 'ग्रॅम'}, {'name': 'फार्मामीन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}]
            },
            {
                'day': 78,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'चि. फेरस', 'dosage': 12.0, 'unit': '%'}]
            },
            {
                'day': 85,
                'activity': '२-३ मणी कलर',
                'info': 'घडामध्ये २-३ मणी कलर आल्यावर फवारणी घेणे',
                'products': [{'name': 'ईथ्रेल', 'dosage': 70.0, 'unit': 'मिली'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 87,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'फार्मामीन', 'dosage': 2.5, 'unit': 'मिली'}, {'name': 'अमिल', 'dosage': 10.0, 'unit': 'मिली'}, {'name': 'व्हिटाफ्लोरा', 'dosage': 5.0, 'unit': 'मिलि'}, {'name': 'हस्ता', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
            {
                'day': 88,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'चि. फेरस', 'dosage': 12.0, 'unit': '%'}]
            },
            {
                'day': 90,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'सल्फर डस्ट', 'dosage': 5.0, 'unit': 'किलो'}]
            },
            {
                'day': 95,
                'activity': 'Foliar Spray',
                'info': '',
                'products': [{'name': 'ईथ्रेल', 'dosage': 40.0, 'unit': 'मिली'}, {'name': 'सॅलीसिओ', 'dosage': 1.5, 'unit': 'मिलि'}]
            },
            {
                'day': 100,
                'activity': 'Foliar Spray',
                'info': 'फवारणी साठी ०.८ ची चक्ती वापरने.',
                'products': [{'name': 'सल्फर', 'dosage': 0.5, 'unit': 'ग्रॅम'}]
            },
        ]
        
        # Insert schedule
        for item in schedule:
            activity_obj = activities.get(item['activity'], default_activity)
            
            day_range = DayRange.objects.create(
                crop_variety=variety,
                activity=activity_obj,
               
                start_day=item['day'],
                end_day=item['day'],
                info=item['info'],
                info_marathi=item['info']
            )
            
            for prod_data in item['products']:
                product_obj = products.get(prod_data['name'])
                if product_obj:
                    if 'dosage' in prod_data:
                        unit = self.normalize_unit(prod_data['unit'])
                        DayRangeProduct.objects.create(
                            day_range=day_range,
                            product=product_obj,
                            dosage=prod_data['dosage'],
                            dosage_unit=unit
                        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {variety.name}'))

        self.stdout.write(self.style.SUCCESS('All varieties imported successfully!'))