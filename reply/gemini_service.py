import google.generativeai as genai
from django.conf import settings
import logging
import json
import numpy as np
import os
import re

logger = logging.getLogger(__name__)

# --- FINAL System Prompt (v7: Natural, Business-Aware, Smart) ---
SYSTEM_PROMPT = """
You are a helpful WhatsApp assistant for an agriculture company. Talk naturally like a helpful friend.

## 🌾 Company Services
1. **Farm Labor Connection** - Connect farmers with verified workers (मजूर/कामगार)
2. **Crop Guidance** - Advice on fertilizers, pesticides, sprays for all crops
3. **Product Booking** - Order agri-products directly
4. **Education** - Tips on farming, pest control, crop stages

## 🗣️ Communication Style
- **Natural & Friendly** - Not robotic, like talking to a farmer friend
- **SHORT replies** - Maximum 2-3 sentences
- **Use emojis naturally**: 🙏 👨‍🌾 🍇 ✅ 📅 🌾
- **Reply in {user_lang}** (Hindi/Marathi/English based on user's language)
- **Use name when needed**: If user introduces themselves differently, use that name. Otherwise use {user_name}

## 🧠 CRITICAL: Memory & Context Awareness
**ALWAYS read conversation history before replying!**

**Smart Rules:**
- If user already said "20 workers", don't ask "how many workers?"
- If user said "Satara", don't ask "where is your farm?"
- If user said "pruning", don't ask "what work?"
- If user changes topic (labor → crop advice), acknowledge: "ठीक आहे, अब फसल के बारे में बात करते हैं"

## 📋 Labor Booking Flow (Smart & Natural)
**Collect ONLY missing information:**
1. ✅ Type of work (pruning/कटाई/spraying/फवारणी/harvesting)
2. ✅ How many workers
3. ✅ Date/When needed
4. ✅ Location (village/taluka)

**Example Natural Flow:**
```
User: "मुझे मजूर चाहिए"
You: "जी बताइए, कितने मजूर और कौन सा काम? 👨‍🌾"

User: "20 मजूर, कटाई के लिए"
You: "ठीक है! कब और कहाँ चाहिए? 📅"

User: "15 दिसंबर, सातारा"
You: "बिल्कुल! मैं सातारा में 15 दिसंबर को 20 कटाई मजूर की व्यवस्था चेक करता हूँ ✅"
```

**If all info is collected:**
Say: "बहुत अच्छा! मैं अभी चेक करके बताता हूँ 👍" or similar

## 🌾 Crop Advice Flow
- Check knowledge base for relevant crop/pest/spray info
- Give specific product recommendations with dosage
- If knowledge base has info, use it. If not, say: "इस बारे में मुझे पक्की जानकारी नहीं है, क्या आप थोड़ा और बता सकते हैं?"

## ⚠️ Disclaimer Rule (VERY STRICT)
**ONLY add this disclaimer IF you mention specific spray/fertilizer/chemical names:**
`(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)`

**DO NOT add for:**
- ❌ Greetings (hello, namaste)
- ❌ Labor booking discussions
- ❌ General questions
- ❌ Acknowledgments (ok, thanks)
- ❌ Follow-up questions

**ONLY add when:**
- ✅ "Use Ranman 80ml" (spray name given)
- ✅ "Apply Profiler 2.5g" (product name given)

## 🚫 Spam & Off-Topic Detection
**Immediately return [IGNORE] for:**
- Test messages ("test", "testing")
- Gibberish ("asdfgh", "xyz123")
- Very short meaningless texts (<3 characters)

**Immediately return [ESCALATE] for:**
- Abusive language
- Political questions
- Entertainment queries (movies, cricket)
- Weather outside farming context
- Anything NOT related to agriculture/farming

**For simple off-topic but polite queries:**
Reply: "मैं सिर्फ खेती और मजूर की मदद कर सकता हूँ 🌾 कोई और सवाल?"

## 🎯 Response Quality Rules
1. **Be brief** - Don't repeat yourself
2. **Use context** - Reference previous messages naturally
3. **One question at a time** - Don't overwhelm with multiple questions
4. **Acknowledge topic changes** - "अच्छा, अब मजूर के बारे में बात करते हैं"
5. **Be honest** - If you don't know, say so

## 📝 Your Task
1. Read conversation history carefully
2. Check if user already provided some info
3. Use knowledge base context if relevant
4. Reply naturally in {user_lang}
5. Keep it SHORT and helpful
"""

# --- Keywords (Optimized) ---
GREETING_WORDS = {
    'hello', 'hi', 'hey', 'namaste', 'नमस्ते', 'namaskar', 'नमस्कार',
    'good morning', 'good evening', 'सुप्रभात', 'शुभ संध्या'
}

ACK_WORDS = {
    'ok', 'okay', 'okk', 'k', 'thanks', 'thank you', 'धन्यवाद', 'धन्यवाद',
    'ठीक', 'ठीक आहे', 'accha', 'अच्छा', 'बरं', 'yes', 'ha', 'हा', 'ji', 'जी'
}

FOLLOW_UP_WORDS = {
    'update', 'any update', 'status', 'kya hua', 'what happened',
    'अपडेट', 'काय झालं', 'काय झाले', 'कोई खबर', 'koi khabar'
}

LABOR_KEYWORDS = {
    'labor', 'labour', 'majur', 'mazdoor', 'kamgar', 'worker', 'workers',
    'मजूर', 'मजदूर', 'कामगार', 'काम', 'chatni', 'चटणी',
    'pruning', 'कटाई', 'harvesting', 'spraying', 'फवारणी'
}
    # ✅ More specific spam detection
SPAM_KEYWORDS = {
    'test123', 'testing', 'asdfgh', 'xyz123',  # Actual spam
    'joke', 'song', 'video game', 'movie ticket',  # Entertainment
    'cricket score', 'ipl', 'match',  # Sports
    'paytm offer', 'bank loan', 'credit card'  # Finance spam
}


class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        
        self.llm_model_name = "gemini-2.0-flash-exp"
        self.embedding_model_name = "text-embedding-004"
        
        # ✅ Create ONE model instance - reuse for all chats
        # DON'T format system prompt here - we'll do it per-user
        self.llm = genai.GenerativeModel(
            self.llm_model_name,
            system_instruction=SYSTEM_PROMPT  # Keep placeholder
        )
        
        self.db_chunks = []
        self.db_vectors = None
        self.load_vector_database()

    def load_vector_database(self):
        """Loads vector database into memory"""
        db_path = os.path.join(settings.BASE_DIR, 'vector_database.json')
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self.db_chunks = json.load(f)
            
            self.db_vectors = np.array([chunk['vector'] for chunk in self.db_chunks])
            norms = np.linalg.norm(self.db_vectors, axis=1, keepdims=True)
            self.db_vectors = self.db_vectors / norms
            
            logger.info(f"✅ Loaded {len(self.db_chunks)} vectors")
        except FileNotFoundError:
            logger.error(f"❌ vector_database.json not found at {db_path}")
            self.db_chunks = []
            self.db_vectors = None
        except Exception as e:
            logger.error(f"❌ Error loading vectors: {e}")
            self.db_chunks = []
            self.db_vectors = None

    def _embed(self, text, task_type="RETRIEVAL_QUERY"):
        """Helper to embed text"""
        try:
            result = genai.embed_content(
                model=self.embedding_model_name,
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def search_knowledge_base(self, query, top_k=5):
        """Semantic search in vector database"""
        if self.db_vectors is None or len(self.db_vectors) == 0:
            return ""

        query_vector = self._embed(query, task_type="RETRIEVAL_QUERY")
        if query_vector is None:
            return ""

        query_vector = np.array(query_vector)
        query_vector = query_vector / np.linalg.norm(query_vector)

        # Cosine similarity
        scores = np.dot(self.db_vectors, query_vector)
        top_k_indices = np.argsort(scores)[-top_k:][::-1]

        context = ""
        for i in top_k_indices:
            chunk = self.db_chunks[i]
            context += f"📄 {chunk['source']} ({chunk['type']}): {chunk['content']}\n---\n"
        
        logger.info(f"🔍 RAG: Found {top_k} chunks for query: '{query[:50]}...'")
        return context

    # --- Helper Functions ---
    def _is_match(self, text, word_set):
        """Check if text matches any word in set"""
        lowered = text.strip().lower()
        
        # Direct match
        if lowered in word_set:
            return True
        
        # Partial match for multi-word phrases
        for word in word_set:
            if ' ' in word and word in lowered:
                return True
        
        return False



    def _is_spam(self, text):
        """Improved spam detection - avoids false positives"""
        lowered = text.strip().lower()
        
        # Updated spam keywords (more specific)
        SPECIFIC_SPAM = {
            'test123', 'testing123', 'asdfgh', 'qwerty', 'xyz123',
            'joke', 'funny', 'meme', 'song lyrics', 'video game',
            'cricket score', 'ipl', 'match prediction',
            'movie ticket', 'film', 'entertainment',
            'paytm offer', 'bank loan', 'credit card offer',
            'win prize', 'lottery', 'free gift'
        }
        
        # Check spam keywords
        for spam_word in SPECIFIC_SPAM:
            if spam_word in lowered:
                return True
        
        # Too short (but allow common words)
        if len(lowered) < 2 and lowered not in ['hi', 'ok', 'no', 'ha', 'ji']:
            return True
        
        # Gibberish detection (no vowels in long words)
        if len(lowered) > 6:
            vowels = sum(1 for c in lowered if c in 'aeiouआएइईउऊओऔ')
            if vowels == 0:
                return True
        
        # Random characters (no alphabets)
        if len(lowered) > 3:
            alpha_chars = sum(1 for c in lowered if c.isalpha())
            if alpha_chars == 0:
                return True
        
        return False
    def _is_labor_request(self, text):
        """Check if message is labor-related"""
        for keyword in LABOR_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                return True
        return False
    
    def _extract_labor_info(self, history):
        """Extract already-provided labor details from history"""
        info = {
            'task': None,
            'count': None,
            'date': None,
            'location': None
        }
        
        # Look through history for these details
        full_conversation = " ".join([msg['parts'][0] for msg in history if msg['role'] == 'user'])
        
        # Task detection
        tasks = ['pruning', 'कटाई', 'spraying', 'फवारणी', 'harvesting', 'चटणी', 'chatni']
        for task in tasks:
            if task.lower() in full_conversation.lower():
                info['task'] = task
                break
        
        # Number detection
        numbers = re.findall(r'\b(\d+)\s*(worker|labour|labor|majur|मजूर)', full_conversation, re.IGNORECASE)
        if numbers:
            info['count'] = numbers[-1][0]  # Last mentioned number
        
        # Location detection
        locations = ['satara', 'सातारा', 'pune', 'पुणे', 'nashik', 'नाशिक']
        for loc in locations:
            if loc.lower() in full_conversation.lower():
                info['location'] = loc
                break
        
        # Date detection (simple patterns)
        dates = re.findall(r'\b(\d{1,2})\s*(dec|december|दिसंबर|jan|january)', full_conversation, re.IGNORECASE)
        if dates:
            info['date'] = f"{dates[-1][0]} {dates[-1][1]}"
        
        return info
    

    def _get_simple_reply(self, history, user_message, user_lang, user_name):
        """Get simple reply without RAG - OPTIMIZED"""
        try:
            # Build minimal prompt
            prompt = f"""User said: '{user_message}' in {user_lang}.

    Instructions:
    - Give a warm, friendly 1-sentence greeting
    - Ask how you can help with their farm
    - Reply in {user_lang}
    - Use 1 emoji (🙏 or 🌾)
    - Keep it natural and SHORT

    Reply:"""
            
            # Use pre-initialized model
            chat = self.llm.start_chat(history=[])
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            # Log API usage
            self._log_api_usage("Greeting", len(prompt.split()) * 1.3, len(reply.split()) * 1.3)
            
            return reply
        except Exception as e:
            logger.error(f"Simple reply error: {str(e)}")
            return "[ESCALATE]"
        

    def generate_reply(self, history, user_message, user_lang, user_name):
        """
        Main reply generation - OPTIMIZED VERSION
        """
        lowered_message = user_message.strip().lower()

        # --- SPAM FILTER ---
        if self._is_spam(lowered_message):
            logger.info(f"🗑️ SPAM detected: '{user_message}'")
            return "[IGNORE]"

        # --- 1. GREETINGS (Simple Reply) ---
        if self._is_match(lowered_message, GREETING_WORDS):
            logger.info(f"👋 Greeting detected")
            return self._get_simple_reply(history, user_message, user_lang, user_name)

        # --- 2. ACKNOWLEDGMENTS (NO API CALL) ---
        if self._is_match(lowered_message, ACK_WORDS):
            logger.info(f"✅ Acknowledgment detected")
            
            # Very short responses - NO API CALL
            if user_lang == 'hi':
                responses = ["स्वागत है! 🙏", "ठीक है! 👍", "बिल्कुल ✅"]
            elif user_lang == 'mr':
                responses = ["स्वागत आहे! 🙏", "ठीक आहे! 👍", "नक्की ✅"]
            else:
                responses = ["Welcome! 🙏", "Sure! 👍", "Great! ✅"]
            
            import random
            return random.choice(responses)
        
        # --- 3. FOLLOW-UPS (SMART CHECK) ---
        if self._is_match(lowered_message, FOLLOW_UP_WORDS):
            logger.info(f"🔄 Follow-up detected")
            
            # Check if this is about labor
            labor_info = self._extract_labor_info(history)
            
            # If we have labor context, give specific update
            if any(labor_info.values()):
                if user_lang == 'hi':
                    return "मैं आपके मजूर की request पर काम कर रहा हूँ। जल्द ही update मिलेगा 👍"
                elif user_lang == 'mr':
                    return "मी तुमच्या मजूर request वर काम करत आहे। लवकरच update मिळेल 👍"
                else:
                    return "I'm working on your labor request. Will update soon 👍"
            
            # Otherwise, treat as normal query (fall through to RAG)

        # --- 4. LABOR REQUESTS (OPTIMIZED) ---
        if self._is_labor_request(lowered_message):
            logger.info(f"👨‍🌾 Labor request detected")
            
            # Extract what we already know
            labor_info = self._extract_labor_info(history + [{"role": "user", "parts": [user_message]}])
            
            # Build conversation history
            history_formatted = self._format_history(history[-5:])
            
            # Build labor details text
            labor_details = f"""- Task: {labor_info['task'] or 'Not mentioned'}
    - Workers: {labor_info['count'] or 'Not mentioned'}
    - Date: {labor_info['date'] or 'Not mentioned'}
    - Location: {labor_info['location'] or 'Not mentioned'}"""
            
            # Build MINIMAL prompt (no system instruction duplication)
            prompt = f"""Conversation:
    {history_formatted}

    User: "{user_message}"

    Known details:
    {labor_details}

    Instructions:
    - Reply in {user_lang}
    - If all 4 details known: Confirm you're arranging it
    - If any missing: Ask ONLY for missing info (1 question max)
    - Keep SHORT (2 sentences max)
    - Use emojis: 👨‍🌾 📅 ✅
    - Do NOT add spray disclaimer for labor queries

    Reply:"""
            
            try:
                # Use pre-initialized model
                chat = self.llm.start_chat(history=[])
                response = chat.send_message(prompt)
                reply = response.text.strip()
                
                # Log API usage
                self._log_api_usage("Labor Query", len(prompt.split()) * 1.3, len(reply.split()) * 1.3)
                
                return reply
            except Exception as e:
                logger.error(f"Labor flow error: {e}")
                return "[ESCALATE]"

        # --- 5. FARM/CROP QUERIES (OPTIMIZED RAG) ---
        logger.info(f"🌾 Farm query - Running RAG")
        
        # Check if query is ACTUALLY about crops/sprays
        crop_keywords = [
            'spray', 'फवारणी', 'crop', 'फसल', 'फसलं', 'fertilizer', 'खाद', 
            'pest', 'कीट', 'disease', 'रोग', 'बीमारी', 'product', 'उत्पाद',
            'grape', 'अंगूर', 'द्राक्ष', 'powder', 'पावडर', 'chemical', 'रसायन'
        ]
        
        is_crop_query = any(keyword in lowered_message for keyword in crop_keywords)
        
        # Only do RAG search if crop-related
        if is_crop_query:
            retrieved_context = self.search_knowledge_base(user_message, top_k=3)
            logger.info("🔍 RAG Search: Found context for crop query")
        else:
            retrieved_context = ""
            logger.info("⏭️ Skipping RAG: Not a crop query")
        
        # Build conversation history
        history_formatted = self._format_history(history[-3:])
        
        # Build knowledge base section
        kb_section = ""
        if retrieved_context:
            kb_section = f"\nKnowledge base:\n{retrieved_context}"
        
        # Build MINIMAL prompt
        disclaimer_text = "(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)"
        
        prompt = f"""Recent conversation:
    {history_formatted}

    User: "{user_message}"
    {kb_section}

    Instructions:
    - Reply in {user_lang}
    - Keep SHORT (2 sentences max)
    - DISCLAIMER RULE: Add the disclaimer ONLY IF:
    1. You mention a SPECIFIC product name (like Ranman, Profiler, Emamectin, Score, etc.)
    2. AND the query is about spraying/fertilizer
    - DO NOT add disclaimer for:
    - Labor/worker discussions
    - General greetings
    - Questions without product names
    - Follow-up questions
    - If no relevant info: Say "मुझे इसके बारे में पक्की जानकारी नहीं है"
    - Use emojis: 🌾 🍇 ✅

    Reply:"""

        try:
            # Use pre-initialized model
            chat = self.llm.start_chat(history=[])
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            # SAFETY CHECK: Remove disclaimer if not crop-related
            if not is_crop_query and disclaimer_text in reply:
                reply = reply.replace(disclaimer_text, "").strip()
                logger.info("🧹 Removed incorrect disclaimer from non-crop query")
            
            # Also check if disclaimer is added without product name
            product_names = [
                'ranman', 'profiler', 'emamectin', 'score', 'ridomil', 
                'mancozeb', 'carbendazim', 'imidacloprid', 'copper', 'sulphur'
            ]
            has_product = any(prod in reply.lower() for prod in product_names)
            
            if disclaimer_text in reply and not has_product:
                reply = reply.replace(disclaimer_text, "").strip()
                logger.info("🧹 Removed disclaimer - no product name mentioned")
            
            # Log API usage
            self._log_api_usage("RAG Query", len(prompt.split()) * 1.3, len(reply.split()) * 1.3)
            
            logger.info(f"✅ RAG Reply: {reply[:100]}...")
            return reply
            
        except Exception as e:
            logger.error(f"RAG error: {str(e)}", exc_info=True)
            return "[ESCALATE]"
        
    def _format_history(self, messages):
        """Format conversation history concisely"""
        if not messages:
            return "No previous conversation"
        
        formatted = []
        for msg in messages:
            role = "User" if msg['role'] == 'user' else "Bot"
            content = msg['parts'][0][:100]
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)

    def _log_api_usage(self, call_type, input_tokens, output_tokens):
        """Track API usage for monitoring"""
        total = int(input_tokens + output_tokens)
        logger.info(f"📊 API Call: {call_type} | In: {int(input_tokens)}t | Out: {int(output_tokens)}t | Total: {total}t")