import os
import json
from docx import Document

# --- CONFIGURATION ---
FILE_NAMES = [
    '35.docx',
    '36.docx',
    '15.docx',
    'cri.docx',
    'pro.xlsx'
]
OUTPUT_FILE = 'knowledge_base.json'

# --- ENHANCED VARIETY MAPPINGS ---
VARIETY_MAPPINGS = [
    {
        "main_name": "Arra 35",
        "aliases": [
            "ara 35", "arra35", "ard 35", "arr 35", "arra 35",
            "अरा ३५", "अरा 35", "एआरडी ३५", "35"
        ],
        "crop": "Grapes",
        "schedule_file": "35.docx",
        "description": "Arra 35 is a premium table grape variety popular in Maharashtra. Requires careful pruning and pest management."
    },
    {
        "main_name": "Arra 36",
        "aliases": [
            "ara 36", "arra36", "ard 36", "arr 36", "arra 36",
            "अरा ३६", "अरा 36", "एआरडी ३६", "36"
        ],
        "crop": "Grapes",
        "schedule_file": "36.docx",
        "description": "Arra 36 is another premium grape variety grown in Maharashtra."
    },
    {
        "main_name": "Crimson Seedless",
        "aliases": [
            "crimson", "crimpson", "thompson", "thompson seedless",
            "थॉम्पसन", "क्रिमसन", "thomson"
        ],
        "crop": "Grapes",
        "schedule_file": "cri.docx",
        "description": "Crimson Seedless is a globally popular red seedless grape variety."
    }
]

# --- COMPANY INFO (Always included in knowledge base) ---
COMPANY_INFO = {
    "name": "Agriculture Service Platform",
    "services": [
        "Farm labor connection service - Connect farmers with verified workers for pruning, harvesting, spraying",
        "Crop-specific product recommendations - Fertilizers, pesticides, micronutrients based on crop stage",
        "Agri-education - Tips on farming practices, pest control, crop management",
        "Product booking - Direct ordering of recommended agricultural products"
    ],
    "labor_process": "Farmers specify: date needed, type of work (pruning/harvesting/spraying), number of laborers required. Company arranges verified laborers.",
    "target_crops": "All crops including grapes, wheat, cotton, chilli, vegetables",
    "languages": "Hindi, Marathi, English"
}

def create_company_chunks():
    """Create chunks from company information"""
    chunks = []
    
    # Main company info
    chunks.append({
        "source": "Company Info",
        "type": "overview",
        "content": f"We are an agriculture service platform providing: {', '.join(COMPANY_INFO['services'])}"
    })
    
    # Labor service details
    chunks.append({
        "source": "Company Info",
        "type": "labor_service",
        "content": f"Labor booking process: {COMPANY_INFO['labor_process']}"
    })
    
    # Target market
    chunks.append({
        "source": "Company Info",
        "type": "services",
        "content": f"We support farmers growing: {COMPANY_INFO['target_crops']}. We provide guidance in {COMPANY_INFO['languages']}."
    })
    
    return chunks

def create_mapping_chunks():
    """Create variety definition chunks"""
    chunks = []
    
    for mapping in VARIETY_MAPPINGS:
        # Main definition
        chunks.append({
            "source": "Variety Database",
            "type": "variety_info",
            "content": (
                f"{mapping['main_name']} ({mapping['crop']}): {mapping['description']} "
                f"Crop schedule information is available in {mapping['schedule_file']}."
            )
        })
        
        # Alias mappings
        for alias in mapping['aliases']:
            chunks.append({
                "source": "Variety Database",
                "type": "variety_alias",
                "content": f"'{alias}' refers to {mapping['main_name']}, which is a {mapping['crop']} variety."
            })
    
    print(f"✅ Created {len(chunks)} variety mapping chunks")
    return chunks

def process_document(filepath):
    """Extract text from DOCX files"""
    print(f"📄 Processing {filepath}...")
    try:
        doc = Document(filepath)
    except Exception as e:
        print(f"  ❌ Error opening {filepath}: {e}")
        return []

    chunks = []
    
    # Extract paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if text and len(text) > 10:  # Ignore very short paragraphs
            chunks.append({
                "source": os.path.basename(filepath),
                "type": "paragraph",
                "content": text
            })

    # Extract tables
    for table in doc.tables:
        header_cells = [cell.text.strip() for cell in table.rows[0].cells]
        
        for row in table.rows[1:]:
            row_cells = [cell.text.strip() for cell in row.cells]
            row_parts = []
            
            for header, cell in zip(header_cells, row_cells):
                if cell:
                    row_parts.append(f"{header}: {cell}")
            
            if row_parts:
                chunks.append({
                    "source": os.path.basename(filepath),
                    "type": "table_row",
                    "content": ", ".join(row_parts)
                })

    print(f"  ✅ Extracted {len(chunks)} chunks")
    return chunks

def main():
    all_chunks = []
    
    print("=" * 50)
    print("🌾 BUILDING KNOWLEDGE BASE")
    print("=" * 50)
    
    # 1. Add company info
    print("\n📋 Adding company information...")
    all_chunks.extend(create_company_chunks())
    
    # 2. Add variety mappings
    print("\n🍇 Adding variety mappings...")
    all_chunks.extend(create_mapping_chunks())
    
    # 3. Process document files
    print("\n📚 Processing documents...")
    for filename in FILE_NAMES:
        if not os.path.exists(filename):
            print(f"⚠️  WARNING: {filename} not found, skipping")
            continue
        
        chunks = process_document(filename)
        all_chunks.extend(chunks)

    # 4. Save to JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print(f"✅ SUCCESS!")
    print(f"📦 Created {OUTPUT_FILE} with {len(all_chunks)} total chunks")
    print("=" * 50)

if __name__ == "__main__":
    main()