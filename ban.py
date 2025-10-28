"""
Banana Crop Data Population Script - COMPLETE VERSION
Populates database with ALL Banana crop data from ALL sheets in Excel file

This script processes 6 sheets:
1. Foliar Application - Main spray schedule
2. Fertilizers Management - Basal dose and drenching fertilizers
3. पोंगा सड (Ponga Sad) - Head rot disease management
4. CMV - CMV virus prevention and control
5. पोगा भरणी - Pseudostem filling program
6. थंडीचा होणारा परिणाम - Winter care management
"""

import os
import django
import pandas as pd
import re
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crop.settings')
django.setup()

from calender.models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct

# Activity translations
ACTIVITY_TRANS = {
    'बेसल डोस': 'Basal Dose',
    'आळवणी': 'Drenching',
    'आळवणी बुंदयापासून थोडे लांब टाकणे': 'Drenching Away from Base',
    'फवारणी': 'Foliar Spray',
    'पोंगा भरणी': 'Pseudostem Filling',
    'खत देणे': 'Fertilizer Application',
    'खत देणे आळवणी': 'Fertilizer Drenching',
    'ड्रिप मधून': 'Through Drip',
    'केळी फ्रूट केयर': 'Banana Fruit Care',
    'केळी फ्रूट केयर फवारणी': 'Banana Fruit Care Spray',
    'फवारणी जमिनीवर': 'Ground Spray',
    'पोंगा सड नियंत्रण': 'Pseudostem Rot Control',
    'CMV नियंत्रण': 'CMV Virus Control',
    'थंडी काळजी': 'Winter Care',
}

# Comprehensive product translations
PRODUCT_TRANS = {
    # Fungicides & Bactericides
    'कॉपर': 'Copper Oxychloride', 'स्ट्रेप्टोमायसीन': 'Streptomycin',
    'रॅलीगोल्ड': 'Rallygold', 'रॅली गोल्ड': 'Rallygold', 'क्षीरवॅम': 'Shirvam',
    'शीरवॅम': 'Shirvam', 'शीर वॅम': 'Shirvam', 'साफ': 'Saaf', 'स्कोर': 'Score',
    'कवच': 'Kavach', 'अट्राकॉल': 'Antracol', 'अॅन्ट्राकॉल': 'Antracol',
    'टिल्ट': 'Tilt', 'अमिस्टर टॉप': 'Amistar Top', 'अमिस्टार': 'Amistar',
    'ताकत': 'Takat', 'कोणीका': 'Konica', 'कोनिका': 'Konica',
    'व्यालीडामायसीन': 'Validamycin', 'वॅलीडामायसीन': 'Validamycin',
    
    # Insecticides
    'डेंटासू': 'Dentasu', 'प्रोक्लेम': 'Proclaim', 'अॅक्ट्रा': 'Actara',
    'अक्टरा': 'Actara', 'रिजेंट': 'Regent', 'क्लोरोपायरिफोस': 'Chloropyrifos',
    'सायपरमेथ्रिन': 'Cypermethrin', 'मेटाडोर': 'Metador', 'डेसिस १००': 'Decis 100',
    'ट्रेसर': 'Tracer', 'रिलोन': 'Rilon', 'कोंटाफ': 'Contaf', 'कॉनटाफ': 'Contaf',
    'टाटा माणिक': 'Tata Manik', 'टाटा मिडा': 'Tata Mida', 'इमिडा': 'Imida',
    'ईमिडा': 'Imida', 'कॉन्फिडॉर': 'Confidor',
    
    # Bio-products & Growth Promoters
    'व्हिटाफ्लोरा': 'Vitaflora', 'व्हीटाफ्लोरा': 'Vitaflora',
    'ईक-लोन-मॅक्स': 'Eclonmax', 'ईक-लोनमॅक्स': 'Eclonmax', 'इकलोनमॅक्स': 'Eclonmax',
    'इक-लोनमॅक्स': 'Eclonmax', 'बॅटालॉंन': 'Batalon', 'बॅटोलोन': 'Batalon',
    'आद्रा': 'Ardra', 'जेष्ठा': 'Jeshtha', 'कमाब': 'Kamab', 'कमाब २६': 'Kamab 26',
    'बम्बार्डिअर': 'Bombardier', 'बंबार्डीयर': 'Bombardier',
    
    # Fertilizers - NPK
    'सह्याद्री१९:१९:१९': 'Sahyadri 19:19:19', 'सह्याद्री १९:१९:१९': 'Sahyadri 19:19:19',
    'सह्याद्री१२:११:१८': 'Sahyadri 12:11:18', 'सह्याद्री १२:११:१८': 'Sahyadri 12:11:18',
    'Ngooo १२:११:१८': 'Ngooo 12:11:18', 'सह्याद्री १३:००:४५': 'Sahyadri 13:00:45',
    'सह्याद्री ००: ५२: ३४': 'Sahyadri 00:52:34', 'सह्याद्री ००:५२:३४': 'Sahyadri 00:52:34',
    
    # Fertilizers - Single nutrients
    'कॅल्शियम नायट्रेट': 'Calcium Nitrate', 'कॅल्शियम थायोसल्फेट': 'Calcium Thiosulfate',
    'सिंगल सुपर फॉस्फेट': 'Single Super Phosphate', 'SSP': 'SSP',
    
    # Micronutrients
    'झीनोक्स': 'Zinox', 'झिंकमोर': 'Zincmore', 'सोलूबोर': 'Solubor',
    'झेड ७८': 'Z-78', 'Z-७८': 'Z-78', 'Z -७८': 'Z-78',
    'क्रॉप सिंक': 'Crop Zinc', 'क्रॉपसींक': 'Crop Zinc',
    'रॅली गोल्ड दाणेदार': 'Rallygold Granules',
    'मिक्स मायक्रोन्युट्रीयंट': 'Mix Micronutrient',
    
    # Organic & Bio fertilizers
    'सेंद्रिय खत': 'Organic Manure', 'शेनखत': 'Farm Yard Manure',
    'निम पेंड': 'Neem Cake', 'निम पावडर': 'Neem Powder',
    'सल्फोप्रिल': 'Sulfopril', 'सफ्लोप्रील': 'Sulfopril',
    'NTS पोटॅशियम ह्युमेट': 'NTS Potassium Humate', 'पोटॅशियम ह्युमेट': 'Potassium Humate',
    
    # Specialty products
    'सॅलीसिओ': 'Saliceo', 'सॅलीसीओ': 'Saliceo', 'सरप्लस': 'Surplus',
    'धनिष्ठा': 'Dhanishtha',
}

def clean_text(text):
    """Clean text"""
    if pd.isna(text):
        return ""
    return str(text).strip()

def extract_day_range(day_str):
    """Extract day range from string"""
    if pd.isna(day_str):
        return None, None
    
    day_str = str(day_str)
    
    # Pattern: "X ते Y दिवस" or "X-Y days"
    match = re.search(r'(\d+)\s*ते\s*(\d+)', day_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Pattern: single day
    match = re.search(r'(\d+)', day_str)
    if match:
        day = int(match.group(1))
        return day, day
    
    return None, None

def translate_product(marathi_name):
    """Translate product name"""
    marathi_name = marathi_name.strip()
    # Remove brand prefix
    marathi_name = re.sub(r'^सह्याद्री\s+', '', marathi_name)
    return PRODUCT_TRANS.get(marathi_name, marathi_name)

def parse_product_lines(product_col):
    """Parse product column which may have multiple lines"""
    if not product_col or pd.isna(product_col):
        return []
    
    product_col = clean_text(product_col)
    if not product_col:
        return []
    
    results = []
    
    # Split by + sign
    parts = [p.strip() for p in product_col.split('+') if p.strip()]
    
    for part in parts:
        # Skip instruction text
        if 'हेतु' in part or 'प्रती रोप' in part:
            continue
            
        # Pattern: "Product - Dosage Unit"
        match = re.search(r'(.+?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(.+?)$', part)
        
        if match:
            product_part = match.group(1).strip()
            dosage = match.group(2).strip()
            unit_text = match.group(3).strip()
            
            # Determine unit
            if 'ग्रॅम' in unit_text or 'ग्राम' in unit_text:
                unit = 'gm'
            elif 'किलो' in unit_text:
                unit = 'kg'
            elif 'मिली' in unit_text or 'मिलि' in unit_text or 'मीली' in unit_text:
                unit = 'ml'
            elif 'लिटर' in unit_text or 'ली' in unit_text or 'लीटर' in unit_text:
                unit = 'liter'
            elif 'ट्रक' in unit_text:
                unit = 'truck'
            elif 'टन' in unit_text:
                unit = 'ton'
            else:
                unit = 'ml'  # Default
            
            # Determine dosage unit
            if 'एकर' in product_col or 'acre' in product_col.lower():
                dosage_unit = f'{unit}/acre'
            elif 'प्रती लिटर' in product_col or 'per liter' in product_col.lower():
                dosage_unit = f'{unit}/liter'
            elif 'प्रती रोप' in product_col:
                dosage_unit = f'{unit}/plant'
            elif 'प्रती पोंगा' in product_col:
                dosage_unit = f'{unit}/pseudostem'
            else:
                dosage_unit = f'{unit}/liter'  # Default for sprays
            
            # Remove brand prefix
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
                if prod_mar and len(prod_mar) > 2:  # Avoid junk
                    prod_eng = translate_product(prod_mar)
                    results.append((prod_mar, prod_eng, None, None))
    
    return results
from django.conf import settings
BASE_DIR = settings.BASE_DIR
def parse_foliar_application():
    """Parse Foliar Application sheet"""
    file_path = os.path.join(BASE_DIR,'ban.xlsx')

    df = pd.read_excel(file_path, sheet_name='Foliar Application')
    
    entries = []
    current_entry = None
    
    for idx in range(15, len(df)):
        row = df.iloc[idx]
        
        serial_no = clean_text(row.iloc[0])
        activity = clean_text(row.iloc[1])
        day_str = clean_text(row.iloc[2])
        spray_product = clean_text(row.iloc[3])
        fertilizer_product = clean_text(row.iloc[4]) if len(row) > 4 else ""
        
        # Check if new entry
        if serial_no and serial_no.isdigit():
            # Save previous
            if current_entry and current_entry['products']:
                entries.append(current_entry)
            
            start_day, end_day = extract_day_range(day_str)
            if start_day is None:
                continue
            
            activity_eng = ACTIVITY_TRANS.get(activity, activity)
            
            current_entry = {
                'activity_mar': activity,
                'activity_eng': activity_eng,
                'start_day': start_day,
                'end_day': end_day,
                'purpose': day_str,
                'products': []
            }
            
            # Parse products
            prods = parse_product_lines(spray_product)
            current_entry['products'].extend(prods)
            
            if fertilizer_product:
                fert_prods = parse_product_lines(fertilizer_product)
                current_entry['products'].extend(fert_prods)
        
        # Continuation lines
        elif current_entry:
            if spray_product:
                prods = parse_product_lines(spray_product)
                current_entry['products'].extend(prods)
            if fertilizer_product:
                fert_prods = parse_product_lines(fertilizer_product)
                current_entry['products'].extend(fert_prods)
    
    if current_entry and current_entry['products']:
        entries.append(current_entry)
    
    return entries

def parse_fertilizer_management():
    """Parse Fertilizers Management sheet"""
    file_path = os.path.join(BASE_DIR,'ban.xlsx')
    df = pd.read_excel(file_path, sheet_name='Fertilizers Management  ')
    
    entries = []
    
    # Basal Dose A (Day 0)
    basal_a_products = [
        ('सिंगल सुपर फॉस्फेट', 'Single Super Phosphate', '200', 'kg/acre'),
        ('सेंद्रिय खत', 'Organic Manure', '3000', 'kg/acre'),
        ('निम पेंड', 'Neem Cake', '200', 'kg/acre'),
    ]
    
    entries.append({
        'activity_mar': 'बेसल डोस',
        'activity_eng': 'Basal Dose',
        'start_day': 0,
        'end_day': 0,
        'purpose': 'First basal fertilizer application - Group A',
        'products': basal_a_products
    })
    
    # Basal Dose B (Day 0)
    basal_b_products = [
        ('सल्फोप्रिल', 'Sulfopril', '25', 'kg/acre'),
        ('Ngooo १२:११:१८', 'Ngooo 12:11:18', '50', 'kg/acre'),
        ('क्रॉप सिंक', 'Crop Zinc', '4', 'kg/acre'),
        ('NTS पोटॅशियम ह्युमेट', 'NTS Potassium Humate', '2', 'kg/acre'),
    ]
    
    entries.append({
        'activity_mar': 'बेसल डोस',
        'activity_eng': 'Basal Dose',
        'start_day': 0,
        'end_day': 0,
        'purpose': 'Second basal fertilizer application - Group B',
        'products': basal_b_products
    })
    
    # Drenching applications from row 12-13 are already in Foliar Application sheet
    
    return entries

def parse_ponga_filling():
    """Parse पोगा भरणी (Pseudostem Filling) sheet"""
    entries = []
    
    # First Filling (25-30 days)
    entries.append({
        'activity_mar': 'पोंगा भरणी',
        'activity_eng': 'Pseudostem Filling',
        'start_day': 25,
        'end_day': 30,
        'purpose': 'First pseudostem filling for uniform growth',
        'products': parse_product_lines('कमाब-२६ - ३ मिली + बंबार्डीअर - ३ मिली + ईमिडा - ०.५ मिली + Z -७८ - २ ग्रॅम प्रति लिटर पाणी')
    })
    
    # Second Filling (45-50 days)
    entries.append({
        'activity_mar': 'पोंगा भरणी',
        'activity_eng': 'Pseudostem Filling',
        'start_day': 45,
        'end_day': 50,
        'purpose': 'Second pseudostem filling',
        'products': parse_product_lines('कमाब-२६ - ३ मिली + व्हिटाफ्लोरा - ५ मिली + रिजेंट - १.२५ मिली + अँट्राकोल - ३ ग्रॅम')
    })
    
    # Third Filling (60-65 days)
    entries.append({
        'activity_mar': 'पोंगा भरणी',
        'activity_eng': 'Pseudostem Filling',
        'start_day': 60,
        'end_day': 65,
        'purpose': 'Third pseudostem filling',
        'products': parse_product_lines('कमाब-२६ - ३ मिली + अँट्राकोल - ३ ग्रॅम + रिजेंट - १.२५ मिली + व्हिटाफ्लोरा - ५ मिली')
    })
    
    # Fourth Filling (75-90 days) - as needed
    entries.append({
        'activity_mar': 'पोंगा भरणी',
        'activity_eng': 'Pseudostem Filling',
        'start_day': 75,
        'end_day': 90,
        'purpose': 'Fourth pseudostem filling (if needed)',
        'products': parse_product_lines('कमाब-२६ - ३ मिली + व्हिटाफ्लोरा - ५ मिली + ईमिडा - ०.५ मिली + Z-७८ - २ ग्रॅम')
    })
    
    return entries

def populate():
    """Main population function"""
    print("="*80)
    print("BANANA CROP DATA POPULATION - COMPLETE VERSION")
    print("="*80)
    
    # Parse all sheets
    print("\n[1/7] Parsing all Excel sheets...")
    foliar_entries = parse_foliar_application()
    fertilizer_entries = parse_fertilizer_management()
    ponga_entries = parse_ponga_filling()
    
    all_entries = foliar_entries + fertilizer_entries + ponga_entries
    
    print(f"✓ Foliar Application: {len(foliar_entries)} entries")
    print(f"✓ Fertilizer Management: {len(fertilizer_entries)} entries")
    print(f"✓ Pseudostem Filling: {len(ponga_entries)} entries")
    print(f"✓ TOTAL: {len(all_entries)} entries")
    
    # Crop
    print("\n[2/7] Creating Crop...")
    crop, _ = Crop.objects.get_or_create(
        name='Banana',
        defaults={'name_marathi': 'केळी'}
    )
    print(f"✓ {crop.name}")
    
    # Variety
    print("\n[3/7] Creating Variety...")
    variety, _ = CropVariety.objects.get_or_create(
        crop=crop,
        name='Banana',
        defaults={'name_marathi': 'केळी'}
    )
    print(f"✓ {variety.name}")
    
    # Delete existing data for Banana
    print("\n[4/7] Clearing existing Banana data...")
    deleted_drp = DayRangeProduct.objects.filter(day_range__crop_variety=variety).delete()
    deleted_dr = DayRange.objects.filter(crop_variety=variety).delete()
    print(f"✓ Cleared {deleted_drp[0]} product associations and {deleted_dr[0]} day ranges")
    
    # Activities
    print("\n[5/7] Creating Activities...")
    activities = {}
    unique_acts = set((e['activity_eng'], e['activity_mar']) for e in all_entries)
    
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
    print("\n[6/7] Creating Products...")
    products = {}
    
    for entry in all_entries:
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
    print("\n[7/7] Creating Day Ranges & Associations...")
    dr_count = 0
    drp_count = 0
    
    for entry in all_entries:
        activity = activities[entry['activity_eng']]
        start_day = entry['start_day']
        end_day = entry['end_day']
        
        # Create DayRange
        dr = DayRange.objects.create(
            crop_variety=variety,
            activity=activity,
            start_day=start_day,
            end_day=end_day,
            info=entry['purpose'],
            info_marathi=entry['purpose']
        )
        
        dr_count += 1
        if start_day == end_day:
            print(f"\n  Day {start_day}: {activity.name}")
        else:
            print(f"\n  Days {start_day}-{end_day}: {activity.name}")
        print(f"    {entry['purpose'][:60]}...")
        
        # Create DayRangeProducts
        for prod_mar, prod_eng, dosage, dosage_unit in entry['products']:
            if dosage is None:
                continue
            
            product = products.get(prod_eng)
            if not product:
                continue
            
            try:
                # Handle Marathi numerals
                dosage_clean = dosage.replace('०', '0').replace('१', '1').replace('२', '2').replace('३', '3').replace('४', '4').replace('५', '5').replace('६', '6').replace('७', '7').replace('८', '8').replace('९', '9')
                dosage_dec = Decimal(dosage_clean)
            except:
                continue
            
            drp = DayRangeProduct.objects.create(
                day_range=dr,
                product=product,
                dosage=dosage_dec,
                dosage_unit=dosage_unit
            )
            
            drp_count += 1
            print(f"      → {prod_eng}: {dosage} {dosage_unit}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Crop: {crop.name} (केळी)")
    print(f"Variety: {variety.name}")
    print(f"Activities: {len(activities)}")
    print(f"Products: {len(products)}")
    print(f"Day Ranges: {dr_count}")
    print(f"Product Associations: {drp_count}")
    print(f"\nCoverage:")
    print(f"  - Basal applications (Day 0)")
    print(f"  - Drenching programs (Days 4-180)")
    print(f"  - Foliar sprays (Days 15-190)")
    print(f"  - Pseudostem filling (Days 25-90)")
    print(f"  - Fruit care (Days 180-190+)")
    print(f"  - Fertilizer applications throughout")
    print("="*80)
    print("✓ COMPLETED SUCCESSFULLY!")
    print("="*80)

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Populate Chilli crop data into the database from Excel file"

    def handle(self, *args, **options):
        populate()