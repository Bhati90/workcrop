"""
Tomato Crop Data Population Script
Populates database with Tomato crop schedule from Excel file
"""

import os
import django
import pandas as pd
import re
from decimal import Decimal
from django.conf import settings
BASE_DIR = settings.BASE_DIR
# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crop.settings')
django.setup()

from calender.models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct

# Activity translations
ACTIVITY_TRANS = {
    'ड्रेंचिंग': 'Drenching',
    'वाढीचा काळ': 'Growth Period',
    'वाढीचा काळ व फुलोरा': 'Growth Period and Flowering',
    'फुलोरा ते फळतोडणी': 'Flowering to Fruit Picking',
    'फुलोरा ते फळधारणा': 'Flowering to Fruit Setting',
    'फुलोरा ते फळधारणा ते तोडणी': 'Flowering to Fruit Setting to Picking',
    'फळधारणा ते तोडणी': 'Fruit Setting to Picking',
    'तणनाशक फवारणी': 'Weed Spray',
}

# Comprehensive product translations
PRODUCT_TRANS = {
    'शीरवॅम': 'Shirvam', 'रॅलीगोल्ड': 'Rallygold', 'आर्द्रा': 'Ardra',
    'बॅटोलोन': 'Batalon', 'व्हिटाफ्लोरा': 'Vitaflora', 'इकलोनमॅक्स': 'Eclonmax',
    'व्हॉलियम फ्लेक्सी': 'Volium Flexi', 'एलिएट': 'Aliet', 'अक्टरा': 'Actara',
    'स्पाईक': 'Spike', 'साफ': 'Saaf', 'उलाला': 'Ulala', 'ताक': 'Buttermilk',
    'फोलिओ गोल्ड': 'Folio Gold', 'डेंटासू': 'Dentasu', 'अॅन्ट्राकॉल': 'Antracol',
    'अॅक्रोली': 'Acroli', 'नगाटा': 'Nagata', 'इम्युनिट': 'Immunyt',
    'सॅलीसीओ': 'Saliceo', 'झिंकमोर': 'Zincmore', 'झीनॉक्स': 'Zinox',
    'सरप्लस': 'Surplus', 'हस्ता': 'Hasta', 'बेनीविया': 'Benevia',
    'ग्रासिया': 'Gracia', 'झेलोरा': 'Zelora', 'धनिष्ठा': 'Dhanishtha',
    'टाटा मेट्रि': 'Tata Metri', 'सेंकोर': 'Sencor', 'डिजायर': 'Desire',
    'एवर्ट': 'Evert', 'अँड्रिनो': 'Andrino', 'फुलविक असिड': 'Fulvic Acid',
    'फुलविक अॅसिड': 'Fulvic Acid', 'रिडोमिल गोल्ड': 'Ridomil Gold',
    'टाटा मास्टर': 'Tata Master', 'डेलिगेट': 'Delegate', 'समिट': 'Summit',
    'कमाब २६': 'Kamab 26', 'जेष्ठा': 'Jeshtha', 'कवच फ्लो': 'Kavach Flow',
    'कवच': 'Kavach', 'एक्स्पोनस': 'Exponus', 'कीटजिन': 'Kitazin',
    'कीटाजिन': 'Kitazin', 'झेड ७८': 'Z-78', 'Z-७८': 'Z-78',
    'अमिल अर्क': 'Amil Extract', 'कॅब्रिओटॉप': 'Cabriotop', 'सेफीना': 'Sefina',
    'वॅलीडामायसीन': 'Validamycin', 'बंबार्डीयर': 'Bombardier',
    'मेलीडीडिओ': 'Melideo', 'कोराजन': 'Coragen', 'सीमोडीस': 'Simodis',
    'अमिस्टर टॉप': 'Amistar Top', 'एलियट': 'Aliet', 'ओबेरॉन': 'Oberon',
    'अॅक्रोबॅट कम्प्लिट': 'Acrobat Complete', 'अॅक्रोबॅट कंप्लीट': 'Acrobat Complete',
    'मेरीवोन': 'Merivon', 'अम्प्लिगो': 'Ampligo', 'कारबेन': 'Carben',
    'कॅमरी': 'Camry', 'सल्फर': 'Sulphur', 'बाविस्टीन': 'Bavistin',
    'स्ट्रेप्टोसायक्लिन': 'Streptocycline', 'कस्टोडिया': 'Custodia',
    'पेगासस': 'Pegasus', 'मेलोडी डुओ': 'Melody Duo', 'मेलोडी ड्युओ': 'Melody Duo',
    'कोनिका': 'Konica', 'व्होलीमय टर्गो': 'Volimay Turgo',
    'परफोशिल्ड ४५%': 'Perfoshield 45%', 'सुमिप्रिंट': 'Sumiprint',
    'NTS  ट्रायकंटेनॉल': 'NTS Triacontanol', 'NTS ट्रायकंटेनॉल': 'NTS Triacontanol',
    'कॉँन्टाफ': 'Contaf', 'कॉनटाफ': 'Contaf', 'टाटा सार्थक': 'Tata Sarthak',
    'फेम': 'Fame', 'टाकुमी': 'Takumi', 'रिजेंट': 'Regent', 'शिनवा': 'Shinwa',
    'वेमिल अर्क': 'Vemil Extract', 'अबासिन': 'Abasin', 'अबासीन': 'Abasin',
    'एम-४५': 'M-45', 'मोवेंटो एनर्जि': 'Movento Energy', 'फ्लोरामाइट': 'Floramite',
    'अनंत': 'Anant', 'अॅक्टारा': 'Actara', 'रिवस': 'Rivis',
    'प्रोक्लेम': 'Proclaim', 'लाल कोळी': 'Red Spider Mites', 'पॉलीवाईन': 'Polyvin',
    'संचार ४०': 'Sanchar 40',
}

def clean_text(text):
    """Clean text"""
    if pd.isna(text):
        return ""
    return str(text).strip()

def extract_day(day_str):
    """Extract day number from string"""
    if pd.isna(day_str):
        return None
    match = re.search(r'(\d+)', str(day_str))
    return int(match.group(1)) if match else None

def translate_product(marathi_name):
    """Translate product name"""
    marathi_name = marathi_name.strip()
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
    
    # Remove brand prefix
    line = re.sub(r'^सह्याद्री\s*', '', line)
    
    results = []
    
    # Split by + sign
    parts = [p.strip() for p in line.split('+') if p.strip()]
    
    for part in parts:
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
            else:
                unit = 'gm'
            
            # Handle alternatives with "/"
            products = [p.strip() for p in product_part.split('/')]
            for prod_mar in products:
                prod_eng = translate_product(prod_mar)
                results.append((prod_mar, prod_eng, dosage, unit))
        else:
            # No dosage - just product name
            products = [p.strip() for p in part.split('/')]
            for prod_mar in products:
                if prod_mar:
                    prod_eng = translate_product(prod_mar)
                    results.append((prod_mar, prod_eng, None, None))
    
    return results

def parse_excel():
    """Parse Excel file"""
    file_path = os.path.join(BASE_DIR,'tom.xlsx')
    df = pd.read_excel(file_path, sheet_name='Foliar Application')
    
    entries = []
    
    # Data starts from row 35 (index 35)
    for idx in range(35, len(df)):
        row = df.iloc[idx]
        
        activity = clean_text(row.iloc[0])
        day_str = clean_text(row.iloc[1])
        purpose = clean_text(row.iloc[2])
        product = clean_text(row.iloc[3])
        
        # Skip empty rows
        if not activity or not day_str:
            continue
        
        day = extract_day(day_str)
        if day is None:
            continue
        
        # Translate activity
        activity_eng = ACTIVITY_TRANS.get(activity, activity)
        
        # Parse products
        prods = parse_product_line(product)
        
        entries.append({
            'activity_mar': activity,
            'activity_eng': activity_eng,
            'day': day,
            'purpose': purpose,
            'products': prods
        })
    
    return entries

def populate():
    """Main population function"""
    print("="*80)
    print("TOMATO CROP DATA POPULATION")
    print("="*80)
    
    # Parse
    print("\n[1/6] Parsing Excel...")
    entries = parse_excel()
    print(f"✓ {len(entries)} entries parsed")
    
    # Crop
    print("\n[2/6] Creating Crop...")
    crop, _ = Crop.objects.get_or_create(
        name='Tomato',
        defaults={'name_marathi': 'टोमॅटो'}
    )
    print(f"✓ {crop.name}")
    
    # Variety
    print("\n[3/6] Creating Variety...")
    variety, _ = CropVariety.objects.get_or_create(
        crop=crop,
        name='Tomato',
        defaults={'name_marathi': 'टोमॅटो'}
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
        
        # Create DayRangeProducts (only for products with dosage)
        for prod_mar, prod_eng, dosage, unit in entry['products']:
            if dosage is None:
                continue  # Skip products without dosage
            
            product = products.get(prod_eng)
            if not product:
                continue
            
            dosage_unit = f'{unit}/acre'
            
            try:
                dosage_dec = Decimal(dosage)
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
    print(f"Crop: {crop.name} (टोमॅटो)")
    print(f"Variety: {variety.name}")
    print(f"Activities: {len(activities)}")
    print(f"Products: {len(products)}")
    print(f"Day Ranges: {dr_count}")
    print(f"Product Associations: {drp_count}")
    print("="*80)
    print("✓ COMPLETED SUCCESSFULLY!")
    print("="*80)


from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Populate Chilli crop data into the database from Excel file"

    def handle(self, *args, **options):
        populate()
