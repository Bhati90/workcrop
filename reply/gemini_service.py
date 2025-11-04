import google.generativeai as genai
from django.conf import settings
import logging
import json
import numpy as np
import os
import re
from collections import defaultdict
from django.core.cache import cache
import datetime

logger = logging.getLogger(__name__)

# --- FINAL System Prompt (v7: Natural, Business-Aware, Smart) ---
SYSTEM_PROMPT = """
You are a helpful WhatsApp assistant for an agriculture company. Talk naturally like a helpful friend.

## 🌾 Company Services
1. **Farm Labor Connection** - Connect farmers with verified workers (मजूर/कामगार)
2. **Crop Guidance** - Advice on fertilizers, pesticides, sprays for all crops
3. **Product Booking** - Order agri-products directly
4. **Education** - Tips on farming, pest control, crop stages

**IMPORTANT**: We may provide OTHER farm services too! If user asks for:
- Transport (वाहतूक)
- Storage (साठवण/भंडारण)
- Equipment (यंत्रे/मशीनरी)
- Processing (प्रक्रिया)
- ANY other farm service


→ **DO NOT SAY "We don't provide this" **
→ **INSTEAD SAY only WHEN QUERY IS FARM RELATED & YOU DIDNT UNDERSTAND**: "हां जी! हमारी टीम आपकी जरूरत समझकर 24 घंटे में संपर्क करेगी। आपकी सुविधा हमारी प्राथमिकता है! 🙏"

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


## 🗣️ Language Handling
- User can write in: English, Hindi, Marathi, or MIX
- Examples:
  - "मुझे 20 labour चाहिए for कटाई"
  - "मला मजूर पाहिजेत"
  - "I need workers"
  - "20 मजूर आज चाहिए urgent"
- **ALWAYS reply in the SAME language user is using**
- If mixed, use mixed too!

## 📍 Location Handling
- User can mention ANY location: Satara, Pune, Mumbai, village names, etc.
- **NEVER** say "we don't operate there"
- **ALWAYS** note the location and say: "ठीक है, [location] के लिए हम चेक करके बताएंगे!"

## 💰 Pricing Requests
When user asks about rates/prices/किंमत/दर:

**RESPONSE (Confident & Reassuring):**
"🙏 आपने सबसे अच्छा प्लेटफॉर्म चुना है! हम मार्केट में बेस्ट service देते हैं।

आपकी जरूरत:
- [Service type]
- [Quantity]
- [Location]
- [Date]

क्या यह सही है? 

किंमत की चिंता न करें! हमारी टीम आपको 24 घंटे में personalized rate के साथ contact करेगी। हम हमेशा best price देते हैं! ✅"

## 🚨 Unknown/New Services
If user asks for something unclear or new:
1. **Acknowledge positively**: "जी बिल्कुल! हम check करते हैं"
2. **Gather details**: Ask WHAT, WHERE, WHEN, HOW MUCH
3. **Reassure**: "हमारी टीम 24 घंटे में आपसे contact करेगी"
4. **DO NOT** escalate immediately - first collect information

## 📋 Information Collection (Smart)
- Check conversation history FIRST
- Don't re-ask what user already told
- If they said "20 workers yesterday", don't ask "how many workers?"
- Collect: Service type, Quantity, Location, Date, Farm details


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
4. Understand what they need (in any language)
5. Gather missing details naturally
6. Store ALL information (even if unclear)
7. For pricing → confident response + 24hr callback promise
8. Reply naturally in {user_lang}
9. Keep it SHORT and helpful
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
    'paytm offer',   # Finance spam
}
# Add this after SPAM_KEYWORDS
ILLEGAL_CROP_KEYWORDS = {
    'cannabis', 'गांजा', 'marijuana', 'weed', 'bhang', 'भांग',
    'opium', 'अफीम', 'poppy', 'खसखस', 'charas', 'चरस',
    'cocaine', 'heroin', 'drugs', 'ड्रग्स', 'नशा',
    'tobacco', 'तंबाकू', 'गुटखा', 'gutka', 'पान मसाला'
}
class GeminiModelConfig:
    """Configuration for each API key + Model combination"""
    def __init__(self, name, api_key, model_id, priority=1):
        self.name = name
        self.api_key = api_key
        self.model_id = model_id
        self.priority = priority
        self.failure_count = 0
        
    def get_today_usage(self):
        """Get request count for today"""
        cache_key = f"gemini_{self.name}_daily_count"
        return cache.get(cache_key, 0)
    
    def is_available(self):
        """Check if under daily limit"""
        usage = self.get_today_usage()
        return usage < 1450  # Keep buffer
    
    def record_request(self):
        """Record successful request"""
        cache_key = f"gemini_{self.name}_daily_count"
        current = cache.get(cache_key, 0)
        
        # Reset at midnight
        now = datetime.datetime.now()
        midnight = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1), 
            datetime.time.min
        )
        seconds_until_midnight = int((midnight - now).total_seconds())
        
        cache.set(cache_key, current + 1, timeout=seconds_until_midnight)
        logger.info(f"📊 {self.name}: {current + 1} requests today")


class GeminiService:
    def __init__(self):
        
        self.instances = self._initialize_instances()
        self.embedding_model_name = "text-embedding-004"
        
        self.db_chunks = []
        self.db_vectors = None
        self.load_vector_database()
        
        logger.info(f"🚀 GeminiService initialized with {len(self.instances)} instances")
    
    def _initialize_instances(self):
        """
        Create all combinations: 5 API keys × 5 models = 25 instances
        """
        instances = []
        
        # Load all API keys
        api_keys = []
        for i in range(1, 6):
            key_name = f'GEMINI_API_KEY_{i}'
            if hasattr(settings, key_name):
                api_keys.append((i, getattr(settings, key_name)))
        
        if not api_keys:
            raise ValueError("❌ No API keys found!")
        
        # Define models (ordered by preference)
        models = [
            # Tier 1: Best models
            {'id': 'gemini-2.0-flash-exp', 'name': '2.0-flash', 'priority': 1},
            {'id': 'gemini-1.5-flash', 'name': '1.5-flash', 'priority': 1},
            
            # Tier 2: Stable models
            {'id': 'gemini-1.5-pro', 'name': '1.5-pro', 'priority': 2},
            {'id': 'gemini-1.5-flash-8b', 'name': '1.5-flash-8b', 'priority': 2},
            
            # Tier 3: Backup
            {'id': 'gemini-pro', 'name': 'pro', 'priority': 3},
        ]
        
        # Create instances for each combination
        for api_idx, api_key in api_keys:
            for model in models:
                instance_name = f"API{api_idx}-{model['name']}"
                instances.append(GeminiModelConfig(
                    name=instance_name,
                    api_key=api_key,
                    model_id=model['id'],
                    priority=model['priority']
                ))
        
        logger.info(f"✅ Created {len(instances)} instances:")
        logger.info(f"   📍 {len(api_keys)} API keys × {len(models)} models")
        
        # Show summary by priority
        by_priority = defaultdict(int)
        for inst in instances:
            by_priority[inst.priority] += 1
        logger.info(f"   Priority 1: {by_priority[1]} (best)")
        logger.info(f"   Priority 2: {by_priority[2]} (stable)")
        logger.info(f"   Priority 3: {by_priority[3]} (backup)")
        
        return instances


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
        
        logger.info(f"🔍 RAG: Found {top_k} chunks for query: '{query[:50]}'")
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
    def _select_instance(self, query_type="general"):
        """
        Select best available instance based on query type
        """
        import random
        
        # Get available instances (under quota)
        available = [inst for inst in self.instances if inst.is_available()]
        
        if not available:
            # All at limit, use least used
            available = sorted(self.instances, key=lambda x: x.get_today_usage())[:5]
            logger.warning(f"⚠️ All instances at limit, using least used")
        
        # Filter by low failure count
        available = [inst for inst in available if inst.failure_count < 3]
        if not available:
            # Reset failures
            for inst in self.instances:
                inst.failure_count = 0
            available = [inst for inst in self.instances if inst.is_available()][:5]
        
        # Sort by priority, then failures, then usage
        available.sort(key=lambda x: (x.priority, x.failure_count, x.get_today_usage()))
        
        # Query type optimization
        if query_type in ["sticker", "reaction", "emoji"]:
            # For stickers/emojis: use ANY available (fast response)
            if len(available) > 5:
                return random.choice(available[:5])
            return available[0] if available else self.instances[0]
        
        elif query_type == "greeting":
            # For greetings: use any available
            if len(available) > 3:
                return random.choice(available[:3])
            return available[0] if available else self.instances[0]
        
        elif query_type in ["labor", "rag"]:
            # For complex queries: prefer priority 1 models
            priority_1 = [inst for inst in available if inst.priority == 1]
            if priority_1:
                return priority_1[0]
        
        # Default: best available
        return available[0] if available else self.instances[0]

    def _handle_emoji_sticker(self, history, emoji_or_sticker, user_lang):
        """
        Smart contextual emoji/sticker response - NO RAG
        """
        # Get recent context
        history_formatted = self._format_history(history[-3:])
        
        prompt = f"""Recent conversation:
    {history_formatted}

    User just sent: {emoji_or_sticker}

    Instructions:
    - Reply with SHORT friendly emoji response (1 line)
    - Match emotion (❤️ → loving, 👍 → encouraging, 🙏 → grateful)
    - Reply in {user_lang}
    - Use 2-3 emojis max
    - If context is labor: acknowledge labor
    - If context is crops: acknowledge crops
    - VERY brief and natural

    Reply:"""
        
        # Select best instance for emoji (fast query)
        instance = self._select_instance(query_type="emoji")
        
        try:
            # Configure API
            genai.configure(api_key=instance.api_key)
            
            # Create model with this instance
            model = genai.GenerativeModel(
                instance.model_id,
                system_instruction=SYSTEM_PROMPT
            )
            
            # Generate response
            chat = model.start_chat(history=[])
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            # Record success
            instance.record_request()
            logger.info(f"✅ Emoji response from {instance.name}")
            
            return reply
            
        except Exception as e:
            logger.error(f"❌ {instance.name} failed: {str(e)}")
            instance.failure_count += 1
            
            # Fallback
            if user_lang == 'hi':
                return "धन्यवाद! 🙏"
            return "Thank you! 🙏"
    def _get_simple_reply(self, history, user_message, user_lang    , user_name             ):
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
        

    def generate_reply(self, history, user_message, user_lang, user_name, message_type="text", whatsapp_user=None, conversation=None):
        """
        Main reply generation - OPTIMIZED VERSION
        """
        lowered_message = user_message.strip().lower()
        if self._is_illegal_crop(lowered_message):
            logger.warning(f"🚫 Illegal crop detected: {user_message}")
            if user_lang == 'hi':
                return "क्षमा करें, हम इस प्रकार की फसलों के लिए सेवा नहीं देते। यह हमारे नियमों के विरुद्ध है। 🙏"
            elif user_lang == 'mr':
                return "क्षमस्व, आम्ही या प्रकारच्या पिकांसाठी सेवा देत नाही। हे आमच्या नियमांच्या विरुद्ध आहे. 🙏"
            else:
                return "Sorry, we don't provide services for this type of crop. It's against our policy. 🙏"
    

        if message_type in ['sticker', 'reaction']:
            logger.info(f"😀 {message_type.upper()} - using emoji handler")
            return self._handle_emoji_sticker(history, user_message, user_lang)

        # --- SPAM FILTER ---
        if self._is_spam(lowered_message):
            logger.info(f"🗑️ SPAM detected: '{user_message}'")
            return "[IGNORE]"

        # --- 1. GREETINGS (Simple Reply) ---
        if self._is_match(lowered_message, GREETING_WORDS):
            logger.info(f"👋 Greeting detected")
            return self._get_simple_reply_multi(history, user_message, user_lang, user_name)


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
            return self._handle_labor_multi(history, user_message, user_lang)
    
    # --- 5. FARM/CROP QUERIES (RAG) ---
        return self._handle_rag_multi(history, user_message, user_lang)
            # Extract what we already know
    #         labor_info = self._extract_labor_info(history + [{"role": "user", "parts": [user_message]}])
            
    #         # Build conversation history
    #         history_formatted = self._format_history(history[-5:])
            
    #         # Build labor details text
    #         labor_details = f"""- Task: {labor_info['task'] or 'Not mentioned'}
    # - Workers: {labor_info['count'] or 'Not mentioned'}
    # - Date: {labor_info['date'] or 'Not mentioned'}
    # - Location: {labor_info['location'] or 'Not mentioned'}"""
            
    #         # Build MINIMAL prompt (no system instruction duplication)
    #         prompt = f"""Conversation:
    # {history_formatted}

    # User: "{user_message}"

    # Known details:
    # {labor_details}

    # Instructions:
    # - Reply in {user_lang}
    # - If all 4 details known: Confirm you're arranging it
    # - If any missing: Ask ONLY for missing info (1 question max)
    # - Keep SHORT (2 sentences max)
    # - Use emojis: 👨‍🌾 📅 ✅
    # - Do NOT add spray disclaimer for labor queries

    # Reply:"""
            
    #         try:
    #             # Use pre-initialized model
    #             chat = self.llm.start_chat(history=[])
    #             response = chat.send_message(prompt)
    #             reply = response.text.strip()
                
    #             # Log API usage
    #             self._log_api_usage("Labor Query", len(prompt.split()) * 1.3, len(reply.split()) * 1.3)
                
    #             return reply
    #         except Exception as e:
    #             logger.error(f"Labor flow error: {e}")
    #             return "[ESCALATE]"

    #     # --- 5. FARM/CROP QUERIES (OPTIMIZED RAG) ---
    #     logger.info(f"🌾 Farm query - Running RAG")
        
    #     # Check if query is ACTUALLY about crops/sprays
    #     crop_keywords = [
    #         'spray', 'फवारणी', 'crop', 'फसल', 'फसलं', 'fertilizer', 'खाद', 
    #         'pest', 'कीट', 'disease', 'रोग', 'बीमारी', 'product', 'उत्पाद',
    #         'grape', 'अंगूर', 'द्राक्ष', 'powder', 'पावडर', 'chemical', 'रसायन'
    #     ]
        
    #     is_crop_query = any(keyword in lowered_message for keyword in crop_keywords)
        
    #     # Only do RAG search if crop-related
    #     if is_crop_query:
    #         retrieved_context = self.search_knowledge_base(user_message, top_k=3)
    #         logger.info("🔍 RAG Search: Found context for crop query")
    #     else:
    #         retrieved_context = ""
    #         logger.info("⏭️ Skipping RAG: Not a crop query")
        
    #     # Build conversation history
    #     history_formatted = self._format_history(history[-15:])
        
    #     # Build knowledge base section
    #     kb_section = ""
    #     if retrieved_context:
    #         kb_section = f"\nKnowledge base:\n{retrieved_context}"
        
    #     # Build MINIMAL prompt
    #     disclaimer_text = "(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)"
        
    #     prompt = f"""Recent conversation:
    # {history_formatted}

    # User: "{user_message}"
    # {kb_section}

    # Instructions:
    # - Reply in {user_lang}
    # - Keep SHORT (2 sentences max)
    # - DISCLAIMER RULE: Add the disclaimer ONLY IF:
    # 1. You mention a SPECIFIC product name (like Ranman, Profiler, Emamectin, Score, etc.)
    # 2. AND the query is about spraying/fertilizer
    # - DO NOT add disclaimer for:
    # - Labor/worker discussions
    # - General greetings
    # - Questions without product names
    # - Follow-up questions
    # - If no relevant info: Say "मुझे इसके बारे में पक्की जानकारी नहीं है"
    # - Use emojis: 🌾 🍇 ✅

    # Reply:"""

    #     try:
    #         # Use pre-initialized model
    #         chat = self.llm.start_chat(history=[])
    #         response = chat.send_message(prompt)
    #         reply = response.text.strip()
            
    #         # SAFETY CHECK: Remove disclaimer if not crop-related
    #         if not is_crop_query and disclaimer_text in reply:
    #             reply = reply.replace(disclaimer_text, "").strip()
    #             logger.info("🧹 Removed incorrect disclaimer from non-crop query")
            
    #         # Also check if disclaimer is added without product name
    #         product_names = [
    #             'ranman', 'profiler', 'emamectin', 'score', 'ridomil', 
    #             'mancozeb', 'carbendazim', 'imidacloprid', 'copper', 'sulphur'
    #         ]
    #         has_product = any(prod in reply.lower() for prod in product_names)
            
    #         if disclaimer_text in reply and not has_product:
    #             reply = reply.replace(disclaimer_text, "").strip()
    #             logger.info("🧹 Removed disclaimer - no product name mentioned")
            
    #         # Log API usage
    #         self._log_api_usage("RAG Query", len(prompt.split()) * 1.3, len(reply.split()) * 1.3)
            
    #         logger.info(f"✅ RAG Reply: {reply[:100]}...")
    #         return reply
            
    #     except Exception as e:
    #         logger.error(f"RAG error: {str(e)}", exc_info=True)
    #         return "[ESCALATE]"

    def _get_simple_reply_multi(self, history, user_message, user_lang, user_name):
        """Greeting with multi-instance"""
        instance = self._select_instance(query_type="greeting")
        
        prompt = f"""User said: '{user_message}' in {user_lang}.
    Reply with warm 1-sentence greeting in {user_lang}. Use 🙏 or 🌾 emoji."""
        
        try:
            genai.configure(api_key=instance.api_key)
            model = genai.GenerativeModel(instance.model_id, system_instruction=SYSTEM_PROMPT)
            
            chat = model.start_chat(history=[])
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            instance.record_request()
            logger.info(f"✅ Greeting from {instance.name}")
            return reply
            
        except Exception as e:
            logger.error(f"Greeting error: {e}")
            return "[ESCALATE]"


    def _handle_labor_multi(self, history, user_message, user_lang):
        """Labor queries with multi-instance - EXACT SAME LOGIC"""
        try:
        # ✅ FAILSAFE: Validate all inputs
            if not isinstance(user_message, str):
                logger.error(f"❌ Invalid user_message type: {type(user_message)}")
                user_message = str(user_message)
            
            user_message = user_message.strip()
            
            if not user_message or len(user_message) < 1:
                logger.error(f"❌ Empty user_message")
                if user_lang == 'hi':
                    return "कृपया अपना सवाल भेजें। 🙏"
                return "Please send your question. 🙏"
            
            lowered_message = user_message.lower()

            # --- CHECK FOR ILLEGAL CROPS FIRST ---
            if self._is_illegal_crop(lowered_message):
                logger.warning(f"🚫 Illegal crop detected: {user_message}")
                if user_lang == 'hi':
                    return "क्षमा करें, हम इस प्रकार की फसलों के लिए सेवा नहीं देते। यह हमारे नियमों के विरुद्ध है। 🙏"
                elif user_lang == 'mr':
                    return "क्षमस्व, आम्ही या प्रकारच्या पिकांसाठी सेवा देत नाही। हे आमच्या नियमांच्या विरुद्ध आहे. 🙏"
                else:
                    return "Sorry, we don't provide services for this type of crop. It's against our policy. 🙏"
        
            # ✅ SAME: Extract what we already know
            labor_info = self._extract_labor_info(history + [{"role": "user", "parts": [user_message]}])
            
            # ✅ SAME: Build conversation history
            history_formatted = self._format_history(history[-5:])
            
            # ✅ SAME: Build labor details text
            labor_details = f"""- Task: {labor_info['task'] or 'Not mentioned'}
        - Workers: {labor_info['count'] or 'Not mentioned'}
        - Date: {labor_info['date'] or 'Not mentioned'}
        - Location: {labor_info['location'] or 'Not mentioned'}"""
            
            # ✅ SAME: Build MINIMAL prompt (IDENTICAL)
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
            
            # ✅ NEW: Select best available API key + model (instead of fixed self.llm)
            instance = self._select_instance(query_type="labor")
            
            try:
                # ✅ NEW: Configure with selected instance's API key
                genai.configure(api_key=instance.api_key)
                
                # ✅ NEW: Create model with selected instance's model_id
                model = genai.GenerativeModel(instance.model_id, system_instruction=SYSTEM_PROMPT)
                
                # ✅ SAME: Start chat and send message (IDENTICAL LOGIC)
                chat = model.start_chat(history=[])
                response = chat.send_message(prompt)
                reply = response.text.strip()
                
                # ✅ NEW: Record usage for this specific instance (quota tracking)
                instance.record_request()
                logger.info(f"✅ Labor from {instance.name}")
                
                return reply
                
            except Exception as e:
                logger.error(f"Labor error: {e}")
                # ✅ NEW: Mark this instance as failed (won't use it next time)
                instance.failure_count += 1
                return "[ESCALATE]"
            
        except Exception as e:
            logger.error(f"💥 CRITICAL ERROR in generate_reply: {e}", exc_info=True)
        
        # ✅ FAILSAFE: Never crash, always return something
        if user_lang == 'hi':
            return "क्षमा करें, technical समस्या है। हमारी टीम आपसे संपर्क करेगी। 🙏"
        return "Sorry, technical issue. Our team will contact you. 🙏"
    
    
    def _handle_rag_multi(self, history, user_message, user_lang, whatsapp_user=None, conversation=None):
        """RAG queries with multi-instance + user-specific memory - FAILSAFE VERSION"""
        
        # ✅ FAILSAFE: Validate user_message first
        if not isinstance(user_message, str):
            logger.error(f"❌ Invalid user_message type: {type(user_message)}")
            user_message = str(user_message)  # Force convert to string
        
        user_message = user_message.strip()
        
        if not user_message or len(user_message) < 2:
            logger.error(f"❌ Empty or too short user_message")
            if user_lang == 'hi':
                return "कृपया अपना सवाल फिर से भेजें। 🙏"
            return "Please send your question again. 🙏"
        
        instance = self._select_instance(query_type="rag")
        
        try:
            # Check if crop-related
            crop_keywords = ['spray', 'फवारणी', 'crop', 'फसल', 'fertilizer', 'खाद', 
                            'pest', 'कीट', 'disease', 'रोग', 'बीमारी', 'product', 'उत्पाद',
                            'grape', 'अंगूर', 'द्राक्ष', 'powder', 'पावडर', 'chemical', 'रसायन']
            
            # ✅ FAILSAFE: Ensure all keywords are strings
            crop_keywords = [str(kw) for kw in crop_keywords if kw and isinstance(kw, str)]
            
            # ✅ FAILSAFE: Safe keyword check
            is_crop_query = False
            try:
                user_message_lower = user_message.lower()
                is_crop_query = any(keyword in user_message_lower for keyword in crop_keywords)
            except Exception as e:
                logger.error(f"❌ Error in keyword check: {e}")
                is_crop_query = False
            
            # Check if asking about orders/history
            order_keywords = ['order', 'आर्डर', 'inquiry', 'पूछताछ', 'booking', 'बुकिंग', 
                            'last time', 'पिछली बार', 'मेरा ऑर्डर']
            
            # ✅ FAILSAFE: Safe order check
            is_order_query = False
            try:
                is_order_query = any(kw in user_message_lower for kw in order_keywords)
            except Exception as e:
                logger.error(f"❌ Error in order check: {e}")
                is_order_query = False
            
            # Get user's order history if asking about orders
            user_history = ""
            if is_order_query and whatsapp_user and conversation:
                try:
                    user_history = self._get_user_order_history(whatsapp_user, conversation) or ""
                except Exception as e:
                    logger.error(f"❌ Error getting order history: {e}")
                    user_history = ""
            
            # Only search knowledge base if crop-related
            retrieved_context = ""
            if is_crop_query:
                try:
                    retrieved_context = self.search_knowledge_base(user_message, top_k=3)
                except Exception as e:
                    logger.error(f"❌ Error in RAG search: {e}")
                    retrieved_context = ""
            
            # Build conversation history
            history_formatted = self._format_history(history[-10:])
            
            # Build context sections
            kb_section = f"\nKnowledge base: {retrieved_context}" if retrieved_context else ""
            order_section = f"\n{user_history}" if user_history else ""
            
            disclaimer_text = "(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)"
            
            prompt = f"""Conversation: {history_formatted}

    User: "{user_message}"
    {kb_section}
    {order_section}

    Instructions:
    - Reply in {user_lang}
    - SHORT (2 sentences max)
    - If user asks about their orders: use "Your past inquiries" info ONLY
    - NEVER mention other users' data
    - Add disclaimer ONLY if you mention specific product name
    - Use 🌾 🍇 ✅

    Reply:"""
            
            # Configure API
            genai.configure(api_key=instance.api_key)
            model = genai.GenerativeModel(instance.model_id, system_instruction=SYSTEM_PROMPT)
            
            # Generate response
            chat = model.start_chat(history=[])
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            # Remove disclaimer if not crop-related
            if not is_crop_query and disclaimer_text in reply:
                reply = reply.replace(disclaimer_text, "").strip()
            
            # Check if product name mentioned
            product_names = [
                'ranman', 'profiler', 'emamectin', 'score', 'ridomil', 
                'mancozeb', 'carbendazim', 'imidacloprid', 'copper', 'sulphur'
            ]
            has_product = any(prod in reply.lower() for prod in product_names)
            
            if disclaimer_text in reply and not has_product:
                reply = reply.replace(disclaimer_text, "").strip()
            
            # Record success
            instance.record_request()
            logger.info(f"✅ RAG from {instance.name}")
            
            return reply
            
        except Exception as e:
            logger.error(f"❌ RAG error: {e}", exc_info=True)
            instance.failure_count += 1
            
            # ✅ FAILSAFE: Return helpful error message instead of crashing
            if user_lang == 'hi':
                return "क्षमा करें, technical समस्या है। कृपया थोड़ी देर बाद try करें या text में लिखें। 🙏"
            return "Sorry, technical issue. Please try again later or send text. 🙏"
    
    
    def _get_user_order_history(self, whatsapp_user, conversation):
        """
        Get THIS user's past inquiries/orders ONLY (not other users)
        """
        try:
            from .models import ServiceInquiry
            
            # Get only THIS user's recent inquiries
            recent_inquiries = ServiceInquiry.objects.filter(
                whatsapp_user=whatsapp_user
            ).order_by('-created_at')[:5]
            
            if not recent_inquiries.exists():
                return None
            
            # Format as context
            history_text = "Your past inquiries:\n"
            for inquiry in recent_inquiries:
                history_text += f"- {inquiry.service_type}: {inquiry.service_description[:100]} (Status: {inquiry.status})\n"
            
            return history_text
            
        except Exception as e:
            logger.error(f"Error fetching user history: {e}")
            return None
    def _is_illegal_crop(self, text):
        """Check if message asks about illegal/narcotic crops"""
        lowered = text.strip().lower()
        
        for keyword in ILLEGAL_CROP_KEYWORDS:
            if keyword in lowered:
                return True
        
        return False  
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