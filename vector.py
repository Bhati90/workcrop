import google.generativeai as genai
import json
import time
import sys

# --- CONFIGURATION ---
INPUT_FILE = "knowledge_base.json"
OUTPUT_FILE = "vector_database.json"
EMBEDDING_MODEL = "text-embedding-004"
BATCH_SIZE = 100  # Gemini allows 100 per batch
API_KEY = "AIzaSyCh0DeWCZr8m3kF4LDB2A_xoAlqbmKjvgs"  # Replace with your key

def main():
    print("=" * 60)
    print("🔮 CREATING VECTOR DATABASE")
    print("=" * 60)
    
    # 1. Configure API
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        print("❌ Error: Please set your Gemini API key in the script")
        return
    
    genai.configure(api_key=API_KEY)
    print(f"✅ API configured with model: {EMBEDDING_MODEL}")
    
    # 2. Load chunks
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {INPUT_FILE} not found")
        print("Please run create_enhanced_knowledge_base.py first")
        return
    
    print(f"📦 Loaded {len(chunks)} chunks from {INPUT_FILE}")
    
    # 3. Embed in batches
    embedded_chunks = []
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    failed_batches = []
    
    print(f"\n🚀 Starting embedding process...")
    print(f"   Processing in {total_batches} batches of {BATCH_SIZE}")
    
    for batch_num in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_num:batch_num + BATCH_SIZE]
        batch_index = batch_num // BATCH_SIZE + 1
        
        print(f"\n📊 Batch {batch_index}/{total_batches} ({len(batch)} chunks)...", end=" ")
        
        try:
            # Extract text content
            texts = [chunk['content'] for chunk in batch]
            
            # Call embedding API
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=texts,
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            # Combine chunks with vectors
            for chunk, vector in zip(batch, result['embedding']):
                embedded_chunks.append({
                    "source": chunk['source'],
                    "type": chunk['type'],
                    "content": chunk['content'],
                    "vector": vector
                })
            
            print("✅")
            
            # Rate limiting - be nice to API
            if batch_index < total_batches:
                time.sleep(1)
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            failed_batches.append(batch_index)
            
            # If quota exceeded, wait longer
            if "quota" in str(e).lower() or "429" in str(e):
                print("⏳ Quota limit hit, waiting 60 seconds...")
                time.sleep(60)
    
    # 4. Save results
    if embedded_chunks:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(embedded_chunks, f, indent=2, ensure_ascii=False)
        
        print("\n" + "=" * 60)
        print(f"✅ SUCCESS!")
        print(f"📦 Created {OUTPUT_FILE}")
        print(f"   Total vectors: {len(embedded_chunks)}")
        print(f"   Vector dimensions: {len(embedded_chunks[0]['vector'])} (768D)")
        
        if failed_batches:
            print(f"\n⚠️ {len(failed_batches)} batches failed: {failed_batches}")
            print("   You can re-run to retry failed batches")
        
        print("=" * 60)
        
        # Show sample
        print("\n📝 Sample embedded chunk:")
        sample = embedded_chunks[0]
        print(f"Source: {sample['source']}")
        print(f"Type: {sample['type']}")
        print(f"Content: {sample['content'][:100]}...")
        print(f"Vector: [{sample['vector'][0]:.6f}, {sample['vector'][1]:.6f}, ...]")
    else:
        print("\n❌ No chunks were successfully embedded")
        print("   Check your API key and quota limits")

if __name__ == "__main__":
    main()