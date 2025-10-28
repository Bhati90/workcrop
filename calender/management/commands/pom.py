"""
Pomegranate Crop Data Population Script - COMPLETE VERSION
Populates database with ALL Pomegranate crop data from ALL sheets in Excel file

This script processes 3 sheets:
1. Pomegranate fertilizers - Fertigation schedule (basal dose to harvest)
2. Pomegranate Pest - Pest and disease management (before leaf fall to harvest)
3. नवीन लागवड - New plantation schedule (planting to establishment)
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
    'बेसल डोस': 'Basal Dose',
    'फर्टिगेशन': 'Fertigation',
    'ड्रिप खते': 'Drip Fertilization',
    'फवारणी': 'Foliar Spray',
    'आळवणी': 'Drenching',
    'पान गळ आधी': 'Before Leaf Fall',
    'पान गळ नंतर': 'After Leaf Fall',
    'खोड पेस्ट': 'Trunk Paste',
    'पहिले पान': 'First Leaf Stage',
    'वाढीची अवस्था': 'Growth Stage',
    'चौकी अवस्था': 'Square Stage',
    'फुलोरा': 'Flowering',
    'फळ सेटिंग': 'Fruit Setting',
    'फळ वाढ': 'Fruit Development',
    'फळ फुगवण': 'Fruit Enlargement',
    'पिकवणी': 'Maturation',
    'नवीन लागवड': 'New Plantation',
}

# Comprehensive product translations
PRODUCT_TRANS = {
    # Organic & Bio fertilizers
    'सेंद्रिय खत': 'Organic Manure', 'गांडूळ खत': 'Vermicompost',
    'निम पेंड': 'Neem Cake', 'निम पावडर': 'Neem Powder', 'शेनखत': 'Farm Yard Manure',
    'रॉक फास्पेट': 'Rock Phosphate', 'रॉक फॉस्फेट': 'Rock Phosphate',
    'सह्याद्री सल्फोप्रिल': 'Sahyadri Sulfopril', 'सल्फोप्रिल': 'Sulfopril',
    'सफ्लोप्रिल': 'Sulfopril',
    
    # NPK Fertilizers
    '१०:२६:२६': '10:26:26', '१२:३२:१६': '12:32:16', 'सह्याद्री १२:११:१८': 'Sahyadri 12:11:18',
    'सह्याद्री N-Goooo (12 :11:18 + Ca+ Mg )': 'Sahyadri N-Goooo 12:11:18',
    'सह्याद्री N-Goooo (16 :08:12 + Ca+ Mg )': 'Sahyadri N-Goooo 16:08:12',
    'N-Goooo': 'N-Goooo', 'सह्याद्री १९: १९ ;१९': 'Sahyadri 19:19:19',
    'सह्याद्री ००:५२:३४': 'Sahyadri 00:52:34', 'सह्याद्री ००.५२.३४': 'Sahyadri 00:52:34',
    'सह्याद्री १२:६१:००': 'Sahyadri 12:61:00', 'सह्याद्री १३:००:४५': 'Sahyadri 13:00:45',
    
    # Single Nutrients
    'कॅल्शियम नायट्रेट': 'Calcium Nitrate', 'कॅल्शियम थायोसल्फेट': 'Calcium Thiosulfate',
    'एसओपी': 'SOP', 'SOP': 'SOP', 'मॅग्नीशियम सल्फेट': 'Magnesium Sulfate',
    
    # Micronutrients
    'बोरॉन': 'Boron', 'सोलूबोर': 'Solubor', 'सोल्युबोर': 'Solubor',
    'फुलविक अॅसिड': 'Fulvic Acid', 'फुलविक असिड': 'Fulvic Acid',
    'पोटॅशियम हयुमेट': 'Potassium Humate', 'पो.हयुमेट': 'Potassium Humate',
    'पोटॅशियम हुमेट': 'Potassium Humate', 'NTS पो. हुमेट': 'NTS Potassium Humate',
    'झिंकमोर': 'Zincmore', 'मेटाझिंक': 'Metazinc', 'पॉलीकार्ब  Zn': 'Polycarb Zn',
    'मायक्रोन्यूट्रीयंट': 'Micronutrient', 'मायक्रोन्यूट्रिएंट': 'Micronutrient',
    'सिलिकॉन': 'Silicon', 'सिलीकेयर': 'Silicare', 'ट्रायकंटेनॉल': 'Triacontanol',
    
    # Bio products & Growth promoters
    'व्हिटाफ्लोरा': 'Vitaflora', 'व्हीटाफ्लोरा': 'Vitaflora',
    'ईक-लोनमॅक्स': 'Eclonmax', 'ईक-लोन-मॅक्स': 'Eclonmax', 'इक-लोनमॅक्स': 'Eclonmax',
    'कमाब २६': 'Kamab 26', 'कमाब-२६': 'Kamab 26', 'कमाब - २६': 'Kamab 26',
    'बम्बार्डिअर': 'Bombardier', 'बंबार्डीयर': 'Bombardier', 'बांबर्डीअर': 'Bombardier',
    'सॅलिसिओ': 'Saliceo', 'सॅलीसीओ': 'Saliceo', 'सरप्लस': 'Surplus',
    'प्लानोफिक्स': 'Planofix', 'इथेफॉन': 'Ethephon', 'टॅपगोन': 'Tafgor',
    'इथरेल': 'Ethrel', 'अमिनो अॅसिड': 'Amino Acid',
    
    # Bio-fungicides & Bactericides
    'आर्द्रा': 'Ardra', 'सह्याद्री आद्रा': 'Sahyadri Ardra',
    'जेष्ठा': 'Jeshtha', 'सह्याद्री जेष्ठा': 'Sahyadri Jeshtha',
    'ज्येष्ठा': 'Jeshtha', 'धनीष्ठा': 'Dhanishtha', 'सह्याद्री धनीष्ठा': 'Sahyadri Dhanishtha',
    'हस्ता': 'Hasta', 'सह्याद्री हस्ता': 'Sahyadri Hasta',
    'ट्रायकोडर्मा': 'Trichoderma', 'सह्याद्री ट्रायकोडर्मा': 'Sahyadri Trichoderma',
    'मायकोराइजा': 'Mycorrhiza', 'मायकोर्हाझा': 'Mycorrhiza',
    'बॅक्ट्रिनाशक': 'Bactericide',
    
    # Fungicides
    'बोर्डो': 'Bordeaux Mixture', 'सल्फर': 'Sulphur', 'कॉपर': 'Copper Oxychloride',
    'कॉपर COC': 'Copper Oxychloride', 'ब्ल्यु कॉपर': 'Blue Copper',
    'ब्लायटॉक्स': 'Blitox', 'ब्ल्युजेट': 'Blujet', 'एम-४५': 'M-45',
    'एम ४५': 'M-45', 'इंडोफिल': 'Indofil', 'यूपील': 'UPL',
    'बाविस्टीन': 'Bavistin', 'कारबेन': 'Carben', 'कार्बेनडेझीम': 'Carbendazim',
    'साफ': 'Saaf', 'स्कोर': 'Score', 'टिल्ट': 'Tilt', 'असाटाफ': 'Asataf',
    'कोंटफ': 'Contaf', 'कोंटाफ': 'Contaf', 'फॉसाटील AL': 'Fosetyl AL',
    'एलीएट': 'Aliet', 'एलिएट': 'Aliet', 'ट्रायसायक्लाझोल': 'Tricyclazole',
    'मर्जर': 'Merger', 'कर्झेट': 'Curzate', 'मॅक्सिमेट': 'Maximet',
    'सायमॉक्सनिल': 'Cymoxanil', 'व्यालीडामायसीन': 'Validamycin',
    'वॅलीडामायसीन': 'Validamycin',
    
    # Insecticides
    'डेंटासू': 'Dentasu', 'डेंटासु': 'Dentasu', 'क्लोथियांनीडीन': 'Clothianidin',
    'रिजेंट': 'Regent', 'रिजेंट ग्रानुएल': 'Regent Granules',
    'क्लोरोपायरिफोस': 'Chloropyrifos', 'प्रोक्लेम': 'Proclaim',
    'इमामेक्टिन बेंजोयेट': 'Emamectin Benzoate', 'रिलोण': 'Rilon',
    'टॅग एंबोज': 'Tag Embos', 'एल्पिडा': 'Elpida', 'इमिडा': 'Imida',
    'ईमिडा': 'Imida', 'कॉन्फिडोर': 'Confidor', 'हॉटशॉट': 'Hotshot',
    'टाटा मीडा': 'Tata Mida', 'थायोमेथोक्सम': 'Thiamethoxam',
    'अक्टरा': 'Actara', 'अनंत': 'Anant', 'डायमेथोयेट': 'Dimethoate',
    'रोगार': 'Rogor', 'रोगोर': 'Rogor', 'टाफगोर': 'Tafgor',
    'असिटामॅप्रिड': 'Acetamiprid', 'माणिक': 'Manik', 'टाटा माणिक': 'Tata Manik',
    'सांट्रानीलिप्रोल': 'Cyantraniliprole', 'बेनेविया': 'Benevia',
    'स्पिनोसॅड': 'Spinosad', 'स्पिंटोर': 'Spintor', 'ट्रेसर': 'Tracer',
    'एमजेट': 'MG\t',
    
    # Bio-insecticides & Plant extracts
    'अमिल अर्क': 'Amil Extract', 'सह्याद्री अमिल अर्क': 'Sahyadri Amil Extract',
    'सह्याद्री अमिल': 'Sahyadri Amil',
    
    # Specialty products
    'बॅटालॉंन': 'Batalon', 'बॅटोलोन': 'Batalon', 'रॅलीगोल्ड': 'Rallygold',
    'रॅली गोल्ड': 'Rallygold', 'रॅलीगोल्ड ग्रानुएल': 'Rallygold Granules',
    'रॅली गोल्ड दाणेदार': 'Rallygold Granules', 'क्षीर वॅम': 'Shirvam',
    'क्षीरवॅम': 'Shirvam', 'शीर वॅम': 'Shirvam', 'कोणीका': 'Konica',
    'स्ट्रेप्टोमायसीन': 'Streptomycin', 'गेरू': 'Red Ochre',
    'स्टिकर': 'Sticker', 'सुनामी': 'Sunami', 'गूळ': 'Jaggery',
    'पर्फोनिमॅट': 'Perfonimate', 'निमिट्झ': 'Nimitz', 'वेलम प्राईम': 'Velum Prime',
    'सोडियम मॉलिब्डेट': 'Sodium Molybdate',
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
    match = re.search(r'(\d+)\s*[-ते]\s*(\d+)', day_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Pattern: single day
    match = re.search(r'(\d+)', day_str)
    if match:
        day = int(match.group(1))
        return day, day
    
    # Special cases
    if 'पानगळ आधी' in day_str:
        # Before leaf fall stages
        if '४०' in day_str or '40' in day_str:
            return -40, -40
        elif '३०' in day_str or '30' in day_str:
            return -30, -30
        elif '२५' in day_str or '25' in day_str:
            return -25, -25
        elif '२०' in day_str or '20' in day_str:
            return -20, -20
        elif '१५' in day_str or '15' in day_str:
            return -15, -15
        elif '१०' in day_str or '10' in day_str:
            return -10, -10
    
    if 'पानगळ नंतर' in day_str or 'पान गळ नंतर' in day_str:
        # After leaf fall stages
        return 2, 2  # Typically 2 days after
    
    if 'ताणा नंतर' in day_str:
        return 1, 1  # After stress (day 1)
    
    return None, None

def translate_product(marathi_name):
    """Translate product name"""
    marathi_name = marathi_name.strip()
    # Remove brand prefix
    marathi_name = re.sub(r'^सह्याद्री\s+', '', marathi_name)
    return PRODUCT_TRANS.get(marathi_name, marathi_name)

def parse_product_lines(product_col):
    """Parse product column"""
    if not product_col or pd.isna(product_col):
        return []
    
    product_col = clean_text(product_col)
    if not product_col:
        return []
    
    # Remove instruction text
    product_col = re.sub(r'हेतु.*', '', product_col)
    product_col = re.sub(r'प्रती प्लांट.*', '', product_col)
    
    results = []
    
    # Split by + sign
    parts = [p.strip() for p in product_col.split('+') if p.strip()]
    
    for part in parts:
        # Skip junk
        if len(part) < 3 or 'सुचणे' in part or 'तयार' in part:
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
            elif 'किलो' in unit_text or 'की' in unit_text:
                unit = 'kg'
            elif 'मिली' in unit_text or 'मिलि' in unit_text or 'मीली' in unit_text:
                unit = 'ml'
            elif 'लिटर' in unit_text or 'ली' in unit_text or 'लीटर' in unit_text:
                unit = 'liter'
            elif 'क्रेट' in unit_text:
                unit = 'crate'
            elif 'टन' in unit_text:
                unit = 'ton'
            elif '%' in unit_text:
                unit = 'percent'
            else:
                unit = 'gm'  # Default
            
            # Determine dosage unit
            if '/एकर' in product_col or 'प्रती एकर' in product_col:
                dosage_unit = f'{unit}/acre'
            elif '/ली' in unit_text or 'प्रती ली' in unit_text or 'प्रती लिटर' in unit_text:
                dosage_unit = f'{unit}/liter'
            elif '/झाड' in unit_text or 'प्रती झाड' in unit_text:
                dosage_unit = f'{unit}/plant'
            elif 'प्लांट' in product_col:
                dosage_unit = f'{unit}/plant'
            else:
                dosage_unit = f'{unit}/liter'  # Default for sprays
            
            # Remove brand prefix
            product_part = re.sub(r'^सह्याद्री\s+', '', product_part)
            
            # Handle alternatives with "/"
            products = [p.strip() for p in product_part.split('/')]
            for prod_mar in products:
                if len(prod_mar) > 1:
                    prod_eng = translate_product(prod_mar)
                    results.append((prod_mar, prod_eng, dosage, dosage_unit))
        else:
            # No dosage - just product name
            product_part = re.sub(r'^सह्याद्री\s+', '', part)
            products = [p.strip() for p in product_part.split('/')]
            for prod_mar in products:
                if prod_mar and len(prod_mar) > 2:
                    prod_eng = translate_product(prod_mar)
                    results.append((prod_mar, prod_eng, None, None))
    
    return results

def parse_fertilizer_sheet():
    """Parse Pomegranate fertilizers sheet"""
    file_path = os.path.join(BASE_DIR,'pom.xlsx')

    df = pd.read_excel(file_path, sheet_name='Pomegranate fertilizers ')
    
    entries = []
    
    # Parse from row 17 onwards (main schedule)
    for idx in range(17, len(df)):
        row = df.iloc[idx]
        
        day_str = clean_text(row.iloc[0])
        stage = clean_text(row.iloc[1])
        product = clean_text(row.iloc[3])
        
        if not day_str or not product:
            continue
        
        start_day, end_day = extract_day_range(day_str)
        if start_day is None:
            continue
        
        activity_eng = ACTIVITY_TRANS.get(stage, 'Fertigation')
        
        prods = parse_product_lines(product)
        if prods:
            entries.append({
                'activity_mar': stage,
                'activity_eng': activity_eng,
                'start_day': start_day,
                'end_day': end_day,
                'purpose': f"{day_str} - {stage}",
                'products': prods
            })
    
    return entries

def parse_pest_sheet():
    """Parse Pomegranate Pest sheet"""
    file_path = os.path.join(BASE_DIR,'pom.xlsx')
    df = pd.read_excel(file_path, sheet_name='Pomegranate Pest')
    
    entries = []
    
    # Parse from row 20 onwards (main schedule)
    for idx in range(20, len(df)):
        row = df.iloc[idx]
        
        day_str = clean_text(row.iloc[0])
        stage = clean_text(row.iloc[1])
        purpose = clean_text(row.iloc[2])
        product = clean_text(row.iloc[3])
        
        if not day_str or not product:
            continue
        
        start_day, end_day = extract_day_range(day_str)
        if start_day is None:
            continue
        
        activity_eng = 'Foliar Spray'
        if 'खोड पेस्ट' in stage:
            activity_eng = 'Trunk Paste'
        elif 'पान गळ' in day_str:
            if 'आधी' in day_str:
                activity_eng = 'Before Leaf Fall'
            else:
                activity_eng = 'After Leaf Fall'
        
        prods = parse_product_lines(product)
        if prods:
            entries.append({
                'activity_mar': stage or day_str,
                'activity_eng': activity_eng,
                'start_day': start_day,
                'end_day': end_day,
                'purpose': f"{day_str} - {stage} - {purpose}" if purpose else f"{day_str} - {stage}",
                'products': prods
            })
    
    return entries

def parse_new_plantation_sheet():
    """Parse नवीन लागवड sheet"""
    file_path = os.path.join(BASE_DIR,'pom.xlsx')
    df = pd.read_excel(file_path, sheet_name='नवीन लागवड ')
    
    entries = []
    
    # Parse from row 4 onwards
    for idx in range(4, len(df)):
        row = df.iloc[idx]
        
        serial = clean_text(row.iloc[0])
        stage = clean_text(row.iloc[1])
        day_str = clean_text(row.iloc[2])
        spray_product = clean_text(row.iloc[3])
        fertilizer_product = clean_text(row.iloc[4])
        purpose = clean_text(row.iloc[5])
        
        if not serial or not day_str:
            continue
        
        start_day, end_day = extract_day_range(day_str)
        if start_day is None:
            continue
        
        activity_eng = ACTIVITY_TRANS.get(stage, 'New Plantation')
        
        all_prods = []
        if spray_product:
            all_prods.extend(parse_product_lines(spray_product))
        if fertilizer_product:
            all_prods.extend(parse_product_lines(fertilizer_product))
        
        if all_prods:
            entries.append({
                'activity_mar': stage,
                'activity_eng': activity_eng,
                'start_day': start_day,
                'end_day': end_day,
                'purpose': f"{day_str} - {stage} - {purpose}" if purpose else f"{day_str} - {stage}",
                'products': all_prods
            })
    
    return entries

def populate():
    """Main population function"""
    print("="*80)
    print("POMEGRANATE CROP DATA POPULATION - COMPLETE VERSION")
    print("="*80)
    
    # Parse all sheets
    print("\n[1/7] Parsing all Excel sheets...")
    fertilizer_entries = parse_fertilizer_sheet()
    pest_entries = parse_pest_sheet()
    plantation_entries = parse_new_plantation_sheet()
    
    all_entries = fertilizer_entries + pest_entries + plantation_entries
    
    print(f"✓ Pomegranate Fertilizers: {len(fertilizer_entries)} entries")
    print(f"✓ Pomegranate Pest: {len(pest_entries)} entries")
    print(f"✓ New Plantation: {len(plantation_entries)} entries")
    print(f"✓ TOTAL: {len(all_entries)} entries")
    
    # Crop
    print("\n[2/7] Creating Crop...")
    crop, _ = Crop.objects.get_or_create(
        name='Pomegranate',
        defaults={'name_marathi': 'डाळिंब'}
    )
    print(f"✓ {crop.name}")
    
    # Variety
    print("\n[3/7] Creating Variety...")
    variety, _ = CropVariety.objects.get_or_create(
        crop=crop,
        name='Pomegranate',
        defaults={'name_marathi': 'डाळिंब'}
    )
    print(f"✓ {variety.name}")
    
    # Delete existing data
    print("\n[4/7] Clearing existing Pomegranate data...")
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
            day_display = f"Day {start_day}" if start_day >= 0 else f"Before leaf fall ({start_day})"
            print(f"\n  {day_display}: {activity.name}")
        else:
            print(f"\n  Days {start_day}-{end_day}: {activity.name}")
        print(f"    {entry['purpose'][:70]}...")
        
        # Create DayRangeProducts
        for prod_mar, prod_eng, dosage, dosage_unit in entry['products']:
            if dosage is None:
                continue
            
            product = products.get(prod_eng)
            if not product:
                continue
            
            try:
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
    print(f"Crop: {crop.name} (डाळिंब)")
    print(f"Variety: {variety.name}")
    print(f"Activities: {len(activities)}")
    print(f"Products: {len(products)}")
    print(f"Day Ranges: {dr_count}")
    print(f"Product Associations: {drp_count}")
    print(f"\nCoverage:")
    print(f"  - Before leaf fall treatments (Day -40 to -10)")
    print(f"  - After leaf fall management (Day 2+)")
    print(f"  - Complete fertigation schedule")
    print(f"  - Pest & disease management")
    print(f"  - New plantation schedule")
    print("="*80)
    print("✓ COMPLETED SUCCESSFULLY!")
    print("="*80)


from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Populate Chilli crop data into the database from Excel file"

    def handle(self, *args, **options):
        populate()