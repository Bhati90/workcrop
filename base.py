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
    # Add the filename as context for every chunk
    file_context = f"[Source File: {os.path.basename(filepath)}]\n"

    # 1. Process Paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            # Add the chunk with its source context
            chunks.append({
                "source": os.path.basename(filepath),
                "type": "paragraph",
                "content": text
            })

    # 2. Process Tables (This is the most important part for your data)
    for i, table in enumerate(doc.tables):
        # Get header row (assumes first row is header)
        header_cells = [cell.text.strip() for cell in table.rows[0].cells]
        
        for row in table.rows[1:]: # Skip header
            row_cells = [cell.text.strip() for cell in row.cells]
            
            # Combine header and row cell to create a meaningful text chunk
            # e.g., "दिवस: १०, अवस्था: ५०% पोंगा, औषधाचे नाव: मेटाडोर..."
            row_text_parts = []
            for header, cell in zip(header_cells, row_cells):
                if cell: # Only add if the cell has content
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

def main():
    all_chunks = []
    
    for filename in FILE_NAMES:
        if not os.path.exists(filename):
            print(f"WARNING: File not found: {filename}. Skipping.")
            continue
        
        chunks = process_document(filename)
        all_chunks.extend(chunks)

    # Save all chunks to the output JSON file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Success! Created {OUTPUT_FILE} with {len(all_chunks)} total chunks.")
    print("This file now contains all the text from your documents.")

if __name__ == "__main__":
    main()