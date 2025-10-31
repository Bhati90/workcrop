import os
import json
from docx import Document

# --- CONFIGURATION ---
# Add all your filenames here
FILE_NAMES = [
    '35.docx',
    '36.docx',
    '15.docx',
    'cri.docx',
    'pro.xlsx'
]
OUTPUT_FILE = 'knowledge_base.json'
# ---------------------
# --- NEW: VARIETY & CROP MAPPINGS ---
# This is where we teach the AI what the varieties are.
# You MUST add all your varieties and misspellings here.
VARIETY_MAPPINGS = [
    {
        "main_name": "Arra 35", # The variety name
        "aliases": ["ara 35", "arra35", "ard 35", "arr 35", "अरा ३५", "एआरडी ३५"], # Common misspellings & names
        "crop": "Grapes (द्राक्ष)", # The crop type
        "schedule_file": "35.docx" # The file to use
    },
    {
        "main_name": "Arra 36",
        "aliases": ["ara 36", "arra36", "ard 36", "arr 36", "अरा ३६", "एआरडी ३६"],
        "crop": "Grapes (द्राक्ष)",
        "schedule_file": "36.docx"
    },
    {
        "main_name": "Crimpson",
        "aliases": ["thompson seedless", "थॉम्पसन", "thomson"],
        "crop": "Grapes (द्राक्ष)",
        "schedule_file": "cri.docx"
    }
    # {
    #     "main_name": "Tomato (Variety XYZ)",
    #     "aliases": ["tamatar", "टोमॅटो"],
    #     "crop": "Tomato (टोमॅटो)",
    #     "schedule_file": "your-tomato-schedule-file.docx" # <-- ADD YOUR FILE TO FILE_NAMES FIRST
    # },
    # {
    #     "main_name": "Crimson",
    #     "aliases": ["crimson seedless", "क्रिमसन"],
    #     "crop": "Grapes (द्राक्ष)",
    #     "schedule_file": "your-crimson-schedule-file.docx" # <-- ADD FILE TO FILE_NAMES FIRST
    # }
]
# ------------------------------------
def process_document(filepath):
    """
    Reads a .docx file and extracts text chunks from paragraphs and tables.
    """
    print(f"Processing {filepath}...")
    try:
        doc = Document(filepath)
    except Exception as e:
        print(f"  Error opening {filepath}: {e}")
        return []

    chunks = []
    
    # 1. Process Paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            chunks.append({
                "source": os.path.basename(filepath),
                "type": "paragraph",
                "content": text
            })

    # 2. Process Tables
    for i, table in enumerate(doc.tables):
        header_cells = [cell.text.strip() for cell in table.rows[0].cells]
        
        for row in table.rows[1:]: # Skip header
            row_cells = [cell.text.strip() for cell in row.cells]
            row_text_parts = []
            for header, cell in zip(header_cells, row_cells):
                if cell:
                    row_text_parts.append(f"{header}: {cell}")
            
            row_text = ", ".join(row_text_parts)
            
            if row_text:
                chunks.append({
                    "source": os.path.basename(filepath),
                    "type": "table_row",
                    "content": row_text
                })

    print(f"  Found {len(chunks)} chunks.")
    return chunks

def create_mapping_chunks():
    """
    Creates special text chunks from the VARIETY_MAPPINGS.
    This explicitly teaches the AI what each name means.
    """
    chunks = []
    for mapping in VARIETY_MAPPINGS:
        # Create a chunk for each alias
        for alias in mapping['aliases']:
            content = (
                f"The term '{alias}' refers to the '{mapping['main_name']}' variety, "
                f"which is a type of {mapping['crop']}. "
                f"The crop schedule for this variety is in the document named '{mapping['schedule_file']}'."
            )
            chunks.append({
                "source": "Variety Mappings",
                "type": "definition",
                "content": content
            })
    print(f"Created {len(chunks)} new mapping chunks.")
    return chunks

def main():
    all_chunks = []
    
    # 1. Add all the new mapping chunks
    all_chunks.extend(create_mapping_chunks())
    
    # 2. Add all the chunks from the documents
    for filename in FILE_NAMES:
        if not os.path.exists(filename):
            print(f"WARNING: File not found: {filename}. Skipping.")
            continue
        
        chunks = process_document(filename)
        all_chunks.extend(chunks)

    # 3. Save all chunks to the output JSON file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Success! Created {OUTPUT_FILE} with {len(all_chunks)} total chunks.")
    print("This file now contains all document text AND your new variety mappings.")

if __name__ == "__main__":
    main()