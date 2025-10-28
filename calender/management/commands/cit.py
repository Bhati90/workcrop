"""
Citrus/Orange Crop Data Population Script
Populates database with Citrus crop management schedule from Excel file

Note: This file has a different structure than Chilli/Tomato files.
It provides fertilizer and spray programs rather than day-by-day schedules.
"""

from django.core.management.base import BaseCommand

from django.conf import settings
BASE_DIR = settings.BASE_DIR
import os
import django
import pandas as pd
import re
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crop.settings')
django.setup()

from calender.models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct

# Activity translations - for this file, we'll use fertilizer management activities
ACTIVITY_TRANS = {
    'ड्रीप नसलेले प्लॉट': 'Non-Drip Plot Management',
    'ड्रीप असलेले प्लॉट': 'Drip Plot Management',
    'फवारणी': 'Foliar Spray',
}

# Product translations
PRODUCT_TRANS = {
    'सह्याद्री १२:११:१८': 'Sahyadri 12:11:18',
    'सह्याद्री १६:०८:१२': 'Sahyadri 16:08:12',
    'सल्फोप्रिल': 'Sulfopril',
    'SSP': 'SSP',
    'युरीया': 'Urea',
    'NTS पो. ह्युमेट': 'NTS Potassium Humate',
    'पो.ह्युमेट': 'Potassium Humate',
    'व्हीटाफ्लोरा': 'Vitaflora',
    'व्हिटाफ्लोरा': 'Vitaflora',
    'शीरवॅम': 'Shirvam',
    'आद्रा': 'Ardra',
    'बॅटेलोन': 'Batalon',
    'बॅटोलोन': 'Batalon',
    'ईकलोनमॅक्स': 'Eclonmax',
    'इकलोनमॅक्स': 'Eclonmax',
    'कॅल्शियम नायट्रेट': 'Calcium Nitrate',
    'मॅग्नेशियम नायट्रेट': 'Magnesium Nitrate',
    'सह्याद्री १३:००:४५': 'Sahyadri 13:00:45',
    'फॉस्फेरीक ॲसिड': 'Phosphoric Acid',
    'फर्टीका': 'Fertica',
    'मेटाझिंक': 'Metazinc',
    'सह्याद्री ००.६०.२०': 'Sahyadri 00:60:20',
    'धनिष्ठा': 'Dhanishtha',
    'मॅग्नेशियम सल्फेट': 'Magnesium Sulfate',
    'सह्याद्री SOP': 'Sahyadri SOP',
    'SOP': 'SOP',
    'कमाब': 'Kamab',
    'झिंकमोर': 'Zincmore',
    'सॅलीसिओ': 'Saliceo',
    'सरप्लस': 'Surplus',
}

def clean_text(text):
    """Clean text"""
    if pd.isna(text):
        return ""
    return str(text).strip()

def translate_product(marathi_name):
    """Translate product name"""
    marathi_name = marathi_name.strip()
    # Remove brand prefix
    marathi_name = re.sub(r'^सह्याद्री\s+', '', marathi_name)
    return PRODUCT_TRANS.get(marathi_name, marathi_name)

def parse_product_line(line):
    """
    Parse product string to extract products with dosages
    Returns list of tuples: [(marathi_name, english_name, dosage, unit), ...]
    """
    if not line or pd.isna(line):
        return []
    
    line = clean_text(line)
    if not line:
        return []
    
    results = []
    
    # Split by + sign
    parts = [p.strip() for p in line.split('+') if p.strip()]
    
    for part in parts:
        # Pattern: "Product - Dosage Unit"
        # Can be per tree (झाड) or per acre (एकर) or per 200 liter (२०० लीटर)
        match = re.search(r'(.+?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(.+?)$', part)
        
        if match:
            product_part = match.group(1).strip()
            dosage = match.group(2).strip()
            unit_text = match.group(3).strip()
            
            # Determine unit based on text
            if 'ग्रॅम' in unit_text or 'ग्राम' in unit_text:
                unit = 'gm'
            elif 'किलो' in unit_text:
                unit = 'kg'
            elif 'मिली' in unit_text or 'मिलि' in unit_text or 'मीली' in unit_text:
                unit = 'ml'
            elif 'लिटर' in unit_text or 'ली' in unit_text or 'लीटर' in unit_text:
                unit = 'liter'
            else:
                unit = 'gm'
            
            # Determine application unit
            if 'झाड' in unit_text:
                dosage_unit = f'{unit}/plant'
            elif 'एकर' in unit_text:
                dosage_unit = f'{unit}/acre'
            elif '२०० लीटर' in unit_text or '२०० ली' in unit_text:
                dosage_unit = f'{unit}/liter'
            else:
                dosage_unit = f'{unit}/acre'  # Default
            
            # Remove brand prefix from product name
            product_part = re.sub(r'^सह्याद्री\s+', '', product_part)
            
            # Handle alternatives with "/"
            products = [p.strip() for p in product_part.split('/')]
            for prod_mar in products:
                prod_eng = translate_product(prod_mar)
                results.append((prod_mar, prod_eng, dosage, dosage_unit))
        else:
            # No dosage - just product name
            product_part = re.sub(r'^सह्याद्री\s+', '', part)
            products = [p.strip() for p in product_part.split('/')]
            for prod_mar in products:
                if prod_mar:
                    prod_eng = translate_product(prod_mar)
                    results.append((prod_mar, prod_eng, None, None))
    
    return results

def parse_excel():
    """Parse Excel file and create structured data"""
    file_path = os.path.join(BASE_DIR,'cit.xlsx')
    df = pd.read_excel(file_path, sheet_name=0)
    
    entries = []
    
    # Manual parsing based on the file structure
    # Non-Drip Plot - First Application (Day 1)
    entries.append({
        'activity_mar': 'ड्रीप नसलेले प्लॉट',
        'activity_eng': 'Non-Drip Plot Management',
        'day': 1,
        'purpose': 'First fertilizer application for quality production',
        'products': parse_product_line('सह्याद्री १२:११:१८ - ३०० ग्रॅम/झाड + सह्याद्री १६:०८:१२ - १०० ग्रॅम/झाड + सल्फोप्रिल - २०० ग्रॅम/झाड')
    })
    
    # Non-Drip Plot - Second Application (Day 15)
    entries.append({
        'activity_mar': 'ड्रीप नसलेले प्लॉट',
        'activity_eng': 'Non-Drip Plot Management',
        'day': 15,
        'purpose': 'Second fertilizer application after 15 days',
        'products': parse_product_line('सल्फोप्रिल - २०० ग्रॅम/झाड + SSP - ४०० ग्रॅम/झाड + युरीया - १०० ग्रॅम/झाड + NTS पो. ह्युमेट - ०.५० ग्रॅम/झाड')
    })
    
    # Non-Drip Plot - First spray through irrigation (Day 1)
    entries.append({
        'activity_mar': 'फवारणी',
        'activity_eng': 'Foliar Spray',
        'day': 1,
        'purpose': 'Spray through irrigation water for disease control',
        'products': parse_product_line('सह्याद्री व्हीटाफ्लोरा - ५ ली/एकर + शीरवॅम - २०० ग्रॅम/एकर + सह्याद्री आद्रा - ५०० ग्रॅम/एकर')
    })
    
    # Non-Drip Plot - Second spray (Day 15)
    entries.append({
        'activity_mar': 'फवारणी',
        'activity_eng': 'Foliar Spray',
        'day': 15,
        'purpose': 'Second spray after 15 days',
        'products': parse_product_line('बॅटेलोन - १ ली/एकर + सह्याद्री ईकलोनमॅक्स - १ ली/एकर')
    })
    
    # Drip Plot - Soil Application (Day 1)
    entries.append({
        'activity_mar': 'ड्रीप असलेले प्लॉट',
        'activity_eng': 'Drip Plot Management',
        'day': 1,
        'purpose': 'Soil application of fertilizers',
        'products': parse_product_line('सह्याद्री १२:११:१८ - ३०० ग्रॅम/झाड + सह्याद्री १६:०८:१२ - १०० ग्रॅम/झाड + सल्फोप्रिल - २०० ग्रॅम/झाड')
    })
    
    # Drip Plot - Drip applications (5 doses with 10 min interval)
    # Dose 1 (Day 5)
    entries.append({
        'activity_mar': 'ड्रीप असलेले प्लॉट',
        'activity_eng': 'Drip Plot Management',
        'day': 5,
        'purpose': 'Drip fertilizer dose 1 of 5',
        'products': parse_product_line('सह्याद्री कॅल्शियम नायट्रेट - ३ किलो/एकर + सह्याद्री मॅग्नेशियम नायट्रेट - ३ किलो/एकर + सह्याद्री १३:००:४५ - १ किलो/एकर')
    })
    
    # Dose 2 (Day 10)
    entries.append({
        'activity_mar': 'ड्रीप असलेले प्लॉट',
        'activity_eng': 'Drip Plot Management',
        'day': 10,
        'purpose': 'Drip fertilizer dose 2 of 5',
        'products': parse_product_line('फॉस्फेरीक ॲसिड - ३ लिटर/एकर + फर्टीका - १ लिटर/एकर + मेटाझिंक - १.५ किलो/एकर')
    })
    
    # Dose 3 (Day 15)
    entries.append({
        'activity_mar': 'ड्रीप असलेले प्लॉट',
        'activity_eng': 'Drip Plot Management',
        'day': 15,
        'purpose': 'Drip fertilizer dose 3 of 5',
        'products': parse_product_line('सह्याद्री ००.६०.२० - २ किलो/एकर + सह्याद्री धनिष्ठा - २०० ग्रॅम/एकर')
    })
    
    # Dose 4 (Day 20)
    entries.append({
        'activity_mar': 'ड्रीप असलेले प्लॉट',
        'activity_eng': 'Drip Plot Management',
        'day': 20,
        'purpose': 'Drip fertilizer dose 4 of 5',
        'products': parse_product_line('मॅग्नेशियम सल्फेट - ५ किलो/एकर + सह्याद्री SOP - ३ किलो/एकर + पो.ह्युमेट - १ किलो/एकर')
    })
    
    # Foliar Spray 1 (Day 7)
    entries.append({
        'activity_mar': 'फवारणी',
        'activity_eng': 'Foliar Spray',
        'day': 7,
        'purpose': 'Foliar spray for growth and quality',
        'products': parse_product_line('कमाब - ७५० मिली + ईकलोनमॅक्स - १ लिटर + सह्याद्री व्हिटाफ्लोरा - १ लिटर')
    })
    
    # Foliar Spray 2 (Day 14)
    entries.append({
        'activity_mar': 'फवारणी',
        'activity_eng': 'Foliar Spray',
        'day': 14,
        'purpose': 'Foliar spray for nutrient uptake',
        'products': parse_product_line('सह्याद्री व्हिटाफ्लोरा - १ लिटर + झिंकमोर - २०० मिली + सॅलीसिओ - ३०० मिली + सरप्लस - २०० मिली')
    })
    
    return entries

def populate():
    """Main population function"""
    print("="*80)
    print("CITRUS/ORANGE CROP DATA POPULATION")
    print("="*80)
    
    # Parse
    print("\n[1/6] Parsing data...")
    entries = parse_excel()
    print(f"✓ {len(entries)} entries created")
    
    # Crop
    print("\n[2/6] Creating Crop...")
    crop, _ = Crop.objects.get_or_create(
        name='Citrus',
        defaults={'name_marathi': 'संत्रा'}
    )
    print(f"✓ {crop.name}")
    
    # Variety
    print("\n[3/6] Creating Variety...")
    variety, _ = CropVariety.objects.get_or_create(
        crop=crop,
        name='Citrus',
        defaults={'name_marathi': 'संत्रा'}
    )
    print(f"✓ {variety.name}")
    
    # Activities
    print("\n[4/6] Creating Activities...")
    activities = {}
    unique_acts = set((e['activity_eng'], e['activity_mar']) for e in entries)
    
    for act_eng, act_mar in unique_acts:
        act, created = Activity.objects.get_or_create(
            name=act_eng,
            defaults={'name_marathi': act_mar}
        )
        activities[act_eng] = act
        if created:
            print(f"  + {act.name}")
    print(f"✓ {len(activities)} activities")
    
    # Products
    print("\n[5/6] Creating Products...")
    products = {}
    
    for entry in entries:
        for prod_mar, prod_eng, dosage, unit in entry['products']:
            if prod_eng not in products:
                prod, created = Product.objects.get_or_create(
                    name=prod_eng,
                    defaults={
                        'name_marathi': prod_mar,
                        'product_type': 'Agricultural Input'
                    }
                )
                products[prod_eng] = prod
                if created:
                    print(f"  + {prod_eng} ({prod_mar})")
    
    print(f"✓ {len(products)} products")
    
    # DayRanges & DayRangeProducts
    print("\n[6/6] Creating Day Ranges & Associations...")
    dr_count = 0
    drp_count = 0
    
    for entry in entries:
        activity = activities[entry['activity_eng']]
        day = entry['day']
        
        # Create DayRange
        dr, created = DayRange.objects.get_or_create(
            crop_variety=variety,
            activity=activity,
            start_day=day,
            end_day=day,
            defaults={
                'info': entry['purpose'],
                'info_marathi': entry['purpose']
            }
        )
        
        if created:
            dr_count += 1
            print(f"\n  Day {day}: {activity.name}")
            print(f"    {entry['purpose'][:60]}...")
        
        # Create DayRangeProducts
        for prod_mar, prod_eng, dosage, dosage_unit in entry['products']:
            if dosage is None:
                continue
            
            product = products.get(prod_eng)
            if not product:
                continue
            
            try:
                dosage_dec = Decimal(dosage.replace('०', '0').replace('१', '1').replace('२', '2').replace('३', '3').replace('४', '4').replace('५', '5').replace('६', '6').replace('७', '7').replace('८', '8').replace('९', '9'))
            except:
                continue
            
            drp, created = DayRangeProduct.objects.get_or_create(
                day_range=dr,
                product=product,
                defaults={
                    'dosage': dosage_dec,
                    'dosage_unit': dosage_unit
                }
            )
            
            if created:
                drp_count += 1
                print(f"      → {prod_eng}: {dosage} {dosage_unit}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Crop: {crop.name} (संत्रा)")
    print(f"Variety: {variety.name}")
    print(f"Activities: {len(activities)}")
    print(f"Products: {len(products)}")
    print(f"Day Ranges: {dr_count}")
    print(f"Product Associations: {drp_count}")
    print("\nNote: This is a fertilizer management program, not a day-by-day")
    print("pest/disease schedule. Days represent application sequence.")
    print("="*80)
    print("✓ COMPLETED SUCCESSFULLY!")
    print("="*80)

class Command(BaseCommand):
    help = "Populate Chilli crop data into the database from Excel file"

    def handle(self, *args, **options):
        populate()
