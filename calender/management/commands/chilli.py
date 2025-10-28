"""
Script to populate Chilli crop data into the database
This script reads the Chilli schedule Excel file and populates:
- Crop (Chilli)
- CropVariety (Chilli)
- Activities
- Products
- DayRange
- DayRangeProduct
"""
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

# Translation mappings for activities (Marathi to English)
ACTIVITY_TRANSLATIONS = {
    'ड्रेंचिंग': 'Drenching',
    'वाढीचा काळ': 'Growth Period',
    'वाढीचा काळ व फुलोरा': 'Growth Period and Flowering',
    'फुलोरा ते फळतोडणी': 'Flowering to Fruit Picking',
    'फुलोरा ते फळधारणा': 'Flowering to Fruit Setting',
    'फुलोरा ते फळधारणा ते तोडणी': 'Flowering to Fruit Setting to Picking',
    'फळधारणा ते तोडणी': 'Fruit Setting to Picking',
}

# Translation mappings for purposes/info (Marathi to English)
INFO_TRANSLATIONS = {
    'मर': 'Damping off disease',
    'पांढरी माशी': 'Whitefly',
    'पांढरी मुळीची वाढ': 'White root growth',
    'झाडाची रोगमुक्त वाढीसाठी': 'For disease-free plant growth',
    'पांनांवरील ठिपके': 'Leaf spots',
    'करपा': 'Disease',
    'भुरी': 'Powdery mildew',
    'थ्रिप्स': 'Thrips',
    'मावा': 'Aphids',
    'मर / मुळकुज': 'Damping off / Root rot',
    'नागअळी': 'Caterpillar',
    'नागआळी': 'Caterpillar',
    'थ्रीप्स, पांढरी माशी,मावा, आळी': 'Thrips, whitefly, aphids, caterpillar',
    'वाढीसाठी': 'For growth',
    'लवकर येणारा करपा': 'Early blight',
    'डेरा करण्यासाठी': 'For branching',
    'लवकर व उशिरा  येणारा करपा': 'Early and late blight',
    'लवकर व उशिरा येणारा करपा, भुरी, पांढरी माशी, थ्रिप्स, नागअळी': 'Early and late blight, powdery mildew, whitefly, thrips, caterpillar',
    'थ्रीप्स, नागअळी, पांढरीमाशी': 'Thrips, caterpillar, whitefly',
    'थ्रीप्स, नागअळी, पांढरी माशी': 'Thrips, caterpillar, whitefly',
    'पांढरी मुळीसाठी': 'For white roots',
    'सर्व करपा नियंत्रणासाठी': 'For all disease control',
    'तुडतुडे,फुलकिडे,लाल कोळी,करपा,फांदीमर,भुरी,अन्थ्राक्णोज': 'Mites, flower insects, red spider mites, disease, stem rot, powdery mildew, anthracnose',
    'तुडतुडे': 'Mites',
    'फुलकिडे': 'Flower insects',
    'लाल कोळी': 'Red spider mites',
    'फांदीमर': 'Stem rot',
    'अन्थ्राक्णोज': 'Anthracnose',
    'लवकर येणारा करपा, थ्रीप्स, पांढरीमाशी': 'Early blight, thrips, whitefly',
    'बुरशीजन्य रोग': 'Fungal diseases',
    'खते अपटेक साठी': 'For fertilizer uptake',
    'रोगप्रतिकार आणि वाढीसाठी': 'For disease resistance and growth',
    'लवकर आणि उशिरा येणारा करपा, पांढरी माशी,फळ पोखरनारी अळी, नागअळी': 'Early and late blight, whitefly, fruit borer, caterpillar',
    'फळ पोखरनारी अळी': 'Fruit borer',
    'नागअळी, पांढरी माशी, थ्रीप्स, लवकर येणारा करपा': 'Caterpillar, whitefly, thrips, early blight',
    'फळ पोखरनारी अळी, उशिरा येणारा करपा, भुरी': 'Fruit borer, late blight, powdery mildew',
    'उशिरा येणारा करपा': 'Late blight',
    'उशिरा येणारा करपा, पांढरी माशी, लालकोळी': 'Late blight, whitefly, red spider mites',
    'लालकोळी': 'Red spider mites',
    'पांढरी मुळी, मर, सुकवा': 'White roots, damping off, wilt',
    'सुकवा': 'Wilt',
    'भुरी,  करपा, फळ पोखरनारी अळी,थ्रीप्स, पांढरी माशी,नागअळी': 'Powdery mildew, disease, fruit borer, thrips, whitefly, caterpillar',
    'करपा, थ्रीप्स, पांढरी माशी, लालकोळी, भुरी': 'Disease, thrips, whitefly, red spider mites, powdery mildew',
    'जीवाणूजन्य करपा': 'Bacterial disease',
    'करपा,नागअळी,थ्रीप्स,पांढरी माशी, फळ पोखरनारी अळी,भुरी': 'Disease, caterpillar, thrips, whitefly, fruit borer, powdery mildew',
    'पांढरी मुळीसाठी,झाडाची वाढ': 'For white roots, plant growth',
    'करपा, भुरी, पांढरी माशी, थ्रिप्स': 'Disease, powdery mildew, whitefly, thrips',
    'पांढरी माशी,थ्रीप्स, लालकोळी, करपा': 'Whitefly, thrips, red spider mites, disease',
    'फळ पोखरनारी अळी, पांढरी माशी, थ्रीप्स, नागआळी, लालकोळी, करपा': 'Fruit borer, whitefly, thrips, caterpillar, red spider mites, disease',
    'मुळी व बोद मोकळा करण्यासाठी': 'For loosening roots and soil',
    'थ्रीप्स, पांढरीमाशी, भुरी, फळाची वाढ,करपा': 'Thrips, whitefly, powdery mildew, fruit growth, disease',
    'फळाची वाढ': 'Fruit growth',
    'भुरी,करपा, फळ पोखरनारी अळी': 'Powdery mildew, disease, fruit borer',
    'करपा, थ्रीप्स, पांढरीमाशी,नागआळी, लालकोळी': 'Disease, thrips, whitefly, caterpillar, red spider mites',
    'थ्रीप्स, पांढरी माशी, फळ पोखरनारी अळी, नागआळी': 'Thrips, whitefly, fruit borer, caterpillar',
    'फळ पोखरनारी अळी,करपा, भुरी': 'Fruit borer, disease, powdery mildew',
    'पांढरी माशी, थ्रीप्स, लालकोळी,करपा, भुरी': 'Whitefly, thrips, red spider mites, disease, powdery mildew',
    'करपा, भुरी, फळ पोखरनारी अळी': 'Disease, powdery mildew, fruit borer',
    'लालकोळी, थ्रीप्स, पांढरी माशी': 'Red spider mites, thrips, whitefly',
    'उशिरा येणारा करपा आणि फळ पोखरनारी अळी,पांढरी माशी, थ्रीप्स': 'Late blight and fruit borer, whitefly, thrips',
    'पांढरीमाशी, थ्रिप्स': 'Whitefly, thrips',
    'उशिरा येणारा करपा, फळ पोखरनारी अळी, लालकोळी, थ्रिप्स, पांढरी माशी': 'Late blight, fruit borer, red spider mites, thrips, whitefly',
    'लाल कोळी, पांढरीमाशी, उशिरा येणारा करपा, भुरी, थ्रिप्स': 'Red spider mites, whitefly, late blight, powdery mildew, thrips',
    'लाल कोळी': 'Red spider mites',
    'भुरी,पांढरीमाशी, थ्रीप्स, फळाची वाढ': 'Powdery mildew, whitefly, thrips, fruit growth',
}

def clean_text(text):
    """Clean and normalize text"""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text)
    return text

def extract_day(day_str):
    """Extract day number from string"""
    if pd.isna(day_str):
        return None
    day_str = str(day_str).strip()
    # Extract first number found
    match = re.search(r'(\d+)', day_str)
    if match:
        return int(match.group(1))
    return None

def translate_activity(marathi_activity):
    """Translate activity from Marathi to English"""
    marathi_activity = clean_text(marathi_activity)
    return ACTIVITY_TRANSLATIONS.get(marathi_activity, marathi_activity)

def translate_info(marathi_info):
    """Translate info from Marathi to English"""
    marathi_info = clean_text(marathi_info)
    return INFO_TRANSLATIONS.get(marathi_info, marathi_info)

def parse_products(product_str):
    """
    Parse product string and extract product names with dosages
    Returns list of tuples: [(product_name, dosage, unit), ...]
    """
    if pd.isna(product_str) or not product_str:
        return []
    
    product_str = clean_text(product_str)
    products = []
    
    # Split by + or common separators
    parts = re.split(r'\s*\+\s*|\n', product_str)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Try to extract product name and dosage
        # Pattern: "Product Name - Dosage Unit"
        match = re.search(r'(.+?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*([^\d\s]+)', part)
        if match:
            product_name = match.group(1).strip()
            dosage = match.group(2).strip()
            unit = match.group(3).strip()
            
            # Clean product name - remove brand prefixes like "सह्याद्री"
            product_name = re.sub(r'^सह्याद्री\s*', '', product_name)
            product_name = re.sub(r'^Sahyadri\s*', '', product_name, flags=re.IGNORECASE)
            
            # Convert Marathi units to standard units
            unit_mapping = {
                'ग्रॅम': 'gm',
                'ग्राम': 'gm',
                'किलो': 'kg',
                'मिली': 'ml',
                'मिलि': 'ml',
                'मीली': 'ml',
                'लिटर': 'liter',
                'ली': 'liter',
                'लीटर': 'liter',
            }
            
            # Determine dosage unit based on context
            dosage_unit = None
            for mar_unit, eng_unit in unit_mapping.items():
                if mar_unit in unit:
                    if 'एकर' in part or 'acre' in part.lower():
                        dosage_unit = f'{eng_unit}/acre'
                    elif 'पाणी' in part or 'water' in part.lower():
                        dosage_unit = f'{eng_unit}/liter'
                    elif 'रोप' in part or 'plant' in part.lower():
                        dosage_unit = f'{eng_unit}/plant'
                    else:
                        dosage_unit = f'{eng_unit}/acre'  # Default to per acre
                    break
            
            if not dosage_unit:
                dosage_unit = 'gm/acre'  # Default
            
            products.append((product_name, dosage, dosage_unit))
        else:
            # Just product name without dosage - skip or add with default dosage
            if len(part) > 3 and not any(char.isdigit() for char in part):
                product_name = re.sub(r'^सह्याद्री\s*', '', part)
                product_name = re.sub(r'^Sahyadri\s*', '', product_name, flags=re.IGNORECASE)
                if product_name:
                    products.append((product_name, '100', 'gm/acre'))  # Default dosage
    
    return products

def populate_data():
    """Main function to populate data"""
    
    print("Starting data population for Chilli crop...")
    
    # Read Excel file
    file_path = os.path.join(BASE_DIR,'chilli.xlsx')

    df = pd.read_excel(file_path, sheet_name='Sheet1')
    
    # Create or get Chilli crop
    crop, created = Crop.objects.get_or_create(
        name='Chilli',
        defaults={'name_marathi': 'मिरची'}
    )
    print(f"Crop: {crop.name} {'created' if created else 'already exists'}")
    
    # Create or get Chilli variety (using same name as crop since no variety specified)
    variety, created = CropVariety.objects.get_or_create(
        crop=crop,
        name='Chilli',
        defaults={'name_marathi': 'मिरची'}
    )
    print(f"Variety: {variety.name} {'created' if created else 'already exists'}")
    
    # Track unique activities and products
    activities_set = set()
    products_dict = {}  # product_name: (dosage, unit)
    
    # Parse data starting from row 17 (index 17) where actual data begins
    data_rows = []
    for idx in range(17, len(df)):
        row = df.iloc[idx]
        
        activity_marathi = clean_text(row.iloc[0])
        day_str = clean_text(row.iloc[1])
        info_marathi = clean_text(row.iloc[2])
        product_str = clean_text(row.iloc[3])
        
        # Skip empty rows
        if not day_str or not activity_marathi:
            continue
        
        # Extract day number
        day = extract_day(day_str)
        if day is None:
            continue
        
        # Translate activity and info
        activity_eng = translate_activity(activity_marathi)
        info_eng = translate_info(info_marathi)
        
        # Parse products
        products = parse_products(product_str)
        
        data_rows.append({
            'activity_marathi': activity_marathi,
            'activity_eng': activity_eng,
            'day': day,
            'info_marathi': info_marathi,
            'info_eng': info_eng,
            'products': products
        })
        
        # Collect unique activities
        activities_set.add((activity_eng, activity_marathi))
        
        # Collect unique products
        for prod_name, dosage, unit in products:
            if prod_name not in products_dict:
                products_dict[prod_name] = []
            products_dict[prod_name].append((dosage, unit))
    
    print(f"\nParsed {len(data_rows)} data rows")
    print(f"Found {len(activities_set)} unique activities")
    print(f"Found {len(products_dict)} unique products")
    
    # Create Activities
    print("\n=== Creating Activities ===")
    activity_objects = {}
    for activity_eng, activity_mar in activities_set:
        activity, created = Activity.objects.get_or_create(
            name=activity_eng,
            defaults={'name_marathi': activity_mar}
        )
        activity_objects[activity_eng] = activity
        print(f"  {activity.name} {'created' if created else 'exists'}")
    
    # Create Products
    print("\n=== Creating Products ===")
    product_objects = {}
    for prod_name in products_dict.keys():
        # Clean product name further
        clean_name = prod_name.strip()
        if not clean_name:
            continue
        
        product, created = Product.objects.get_or_create(
            name=clean_name,
            defaults={
                'product_type': 'Agricultural Input',
                'name_marathi': prod_name  # Keep original for Marathi
            }
        )
        product_objects[prod_name] = product
        print(f"  {product.name} {'created' if created else 'exists'}")
    
    # Create DayRanges and DayRangeProducts
    print("\n=== Creating Day Ranges and Products ===")
    day_range_count = 0
    day_range_product_count = 0
    
    for row_data in data_rows:
        activity = activity_objects.get(row_data['activity_eng'])
        if not activity:
            print(f"  Warning: Activity not found: {row_data['activity_eng']}")
            continue
        
        day = row_data['day']
        # Use day as both start and end since no range specified
        start_day = day
        end_day = day
        
        # Create DayRange
        day_range, created = DayRange.objects.get_or_create(
            crop_variety=variety,
            activity=activity,
            start_day=start_day,
            end_day=end_day,
            defaults={
                'info': row_data['info_eng'],
                'info_marathi': row_data['info_marathi']
            }
        )
        
        if created:
            day_range_count += 1
            print(f"  Day {day}: {activity.name} - {row_data['info_eng'][:50]}...")
        
        # Create DayRangeProducts
        for prod_name, dosage, dosage_unit in row_data['products']:
            product = product_objects.get(prod_name)
            if not product:
                print(f"    Warning: Product not found: {prod_name}")
                continue
            
            try:
                dosage_decimal = Decimal(dosage)
            except:
                print(f"    Warning: Invalid dosage '{dosage}' for {prod_name}")
                continue
            
            day_range_product, created = DayRangeProduct.objects.get_or_create(
                day_range=day_range,
                product=product,
                defaults={
                    'dosage': dosage_decimal,
                    'dosage_unit': dosage_unit
                }
            )
            
            if created:
                day_range_product_count += 1
    
    print(f"\n=== Summary ===")
    print(f"Crop: {crop.name}")
    print(f"Variety: {variety.name}")
    print(f"Activities created: {len(activities_set)}")
    print(f"Products created: {len(products_dict)}")
    print(f"Day ranges created: {day_range_count}")
    print(f"Day range products created: {day_range_product_count}")
    print("\nData population completed successfully!")

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Populate Chilli crop data into the database from Excel file"

    def handle(self, *args, **options):
        populate_data()
