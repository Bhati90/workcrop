import google.generativeai as genai
import json
import os
import time

# --- CONFIGURATION ---
INPUT_FILE = "knowledge_base.json"
OUTPUT_FILE = "vector_database.json"
EMBEDDING_MODEL = "text-embedding-004" # The new, powerful embedding model
# We can process 100 chunks in a single API call (batching)
BATCH_SIZE = 100
# ---------------------

def main():
    # 1. Configure the API key
    api_key = 'AIzaSyCh0DeWCZr8m3kF4LDB2A_xoAlqbmKjvgs'
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

    # 2. Load the text chunks from knowledge_base.json
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        print("Please run the `create_knowledge_base.py` script first.")
        return

    print(f"Loaded {len(chunks)} text chunks from {INPUT_FILE}.")
    
    # 3. Embed the chunks in batches
    embedded_chunks = []
    total_chunks = len(chunks)

    print(f"Starting embedding process using '{EMBEDDING_MODEL}'...")

    for i in range(0, total_chunks, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        
        # Get the text content for each chunk in the batch
        texts_to_embed = [chunk['content'] for chunk in batch]
        
        try:
            # Call the embedding model
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=texts_to_embed,
                task_type="RETRIEVAL_DOCUMENT" # Important: optimize for RAG
            )
            
            # Combine the original chunk with its new vector
            for original_chunk, vector in zip(batch, result['embedding']):
                embedded_chunks.append({
                    "source": original_chunk['source'],
                    "type": original_chunk['type'],
                    "content": original_chunk['content'],
                    "vector": vector # Add the new vector
                })

            print(f"  Processed batch {i // BATCH_SIZE + 1} / {total_chunks // BATCH_SIZE + 1}...")

            # Be nice to the API, especially in free tiers
            time.sleep(1) 

        except Exception as e:
            print(f"Error processing batch {i}: {e}")
            print("  Skipping this batch.")

    # 4. Save the new list of embedded chunks
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(embedded_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Success! Created {OUTPUT_FILE} with {len(embedded_chunks)} vectors.")
    print("Your vector database is ready.")

if __name__ == "__main__":
    main()