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
- Banking/password requests
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

# Expanded spam detection
SPAM_KEYWORDS = {
    'test', 'testing', 'bank', 'password', 'loan', 'paytm', 'account',
    'cricket', 'movie', 'joke', 'song', 'video', 'game'
}


class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        
        self.llm_model_name = "gemini-2.0-flash-exp"
        self.embedding_model_name = "text-embedding-004"
        
        self.llm = genai.GenerativeModel(
            self.llm_model_name,
            system_instruction=SYSTEM_PROMPT
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
        """Detect spam messages"""
        lowered = text.strip().lower()
        
        # Check spam keywords
        if self._is_match(lowered, SPAM_KEYWORDS):
            return True
        
        # Too short (but allow "ok", "hi")
        if len(lowered) < 2 and lowered not in ACK_WORDS:
            return True
        
        # Random gibberish (no vowels or too many repeating chars)
        if len(lowered) > 5:
            vowels = sum(1 for c in lowered if c in 'aeiouआएइईउऊओऔ')
            if vowels == 0:
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
    
    def _get_simple_reply(self, history, prompt_instruction, user_lang):
        """Get simple reply without RAG"""
        try:
            # Format system prompt with user language
            formatted_prompt = SYSTEM_PROMPT.format(
                user_lang=user_lang,
                user_name="दोस्त"  # Generic friend
            )
            
            # Create temporary model with formatted system instruction
            temp_model = genai.GenerativeModel(
                self.llm_model_name,
                system_instruction=formatted_prompt
            )
            
            chat = temp_model.start_chat(history=[])
            response = chat.send_message(prompt_instruction)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Simple reply error: {str(e)}")
            return "[ESCALATE]"

    def generate_reply(self, history, user_message, user_lang, user_name):
        """
        Main reply generation with smart context awareness
        """
        lowered_message = user_message.strip().lower()

        # --- SPAM FILTER ---
        if self._is_spam(lowered_message):
            logger.info(f"🗑️ SPAM detected: '{user_message}'")
            return "[IGNORE]"

        # --- 1. GREETINGS (Simple Reply) ---
        if self._is_match(lowered_message, GREETING_WORDS):
            logger.info(f"👋 Greeting detected")
            prompt = (
                f"User said: '{user_message}' in {user_lang}. "
                f"Give a warm 1-sentence greeting and ask how you can help with their farm. Use emoji."
            )
            return self._get_simple_reply(history, prompt, user_lang)

        # --- 2. ACKNOWLEDGMENTS (Very Short Reply) ---
        if self._is_match(lowered_message, ACK_WORDS):
            logger.info(f"✅ Acknowledgment detected")
            
            # Very short responses
            if user_lang == 'hi':
                responses = ["स्वागत है! 🙏", "ठीक है! 👍", "बिल्कुल ✅"]
            elif user_lang == 'mr':
                responses = ["स्वागत आहे! 🙏", "ठीक आहे! 👍", "नक्की ✅"]
            else:
                responses = ["Welcome! 🙏", "Sure! 👍", "Great! ✅"]
            
            import random
            return random.choice(responses)
        
        # --- 3. FOLLOW-UPS (Check Status) ---
        if self._is_match(lowered_message, FOLLOW_UP_WORDS):
            logger.info(f"🔄 Follow-up detected")
            
            last_topic = "आपकी request" if user_lang == 'hi' else "your request"
            if history:
                # Get last bot message to understand context
                last_bot_msg = next((msg['parts'][0] for msg in reversed(history) if msg['role'] == 'model'), "")
                if 'labor' in last_bot_msg.lower() or 'मजूर' in last_bot_msg:
                    last_topic = "labor booking" if user_lang == 'en' else "मजूर की बुकिंग"
            
            if user_lang == 'hi':
                return f"मैं {last_topic} पर काम कर रहा हूँ, जल्द बताता हूँ 👍"
            elif user_lang == 'mr':
                return f"मी {last_topic} वर काम करत आहे, लवकरच सांगतो 👍"
            else:
                return f"I'm checking on {last_topic}, will update soon 👍"

        # --- 4. LABOR REQUESTS (Smart Flow) ---
        if self._is_labor_request(lowered_message):
            logger.info(f"👨‍🌾 Labor request detected")
            
            # Extract what we already know from history
            labor_info = self._extract_labor_info(history + [{"role": "user", "parts": [user_message]}])
            
            # Build context-aware prompt
            history_summary = ""
            if history:
                last_5 = history[-5:] if len(history) >= 5 else history
                history_summary = "\n".join([
                    f"{msg['role']}: {msg['parts'][0][:100]}" for msg in last_5
                ])
            
            prompt = f"""Conversation history:
{history_summary}

User's latest message: "{user_message}"

**What we already know:**
- Task: {labor_info['task'] or 'Not mentioned'}
- Number of workers: {labor_info['count'] or 'Not mentioned'}
- Date: {labor_info['date'] or 'Not mentioned'}
- Location: {labor_info['location'] or 'Not mentioned'}

**Your task:**
- If ALL 4 details are known: Confirm and say you're arranging it
- If ANY detail is missing: Ask ONLY for missing info (1-2 questions max)
- Be natural and conversational
- Reply in {user_lang}
- Use emojis: 👨‍🌾 📅 ✅
- Keep it SHORT (2 sentences max)

Reply:"""
            
            try:
                formatted_prompt = SYSTEM_PROMPT.format(
                    user_lang=user_lang,
                    user_name=user_name
                )
                temp_model = genai.GenerativeModel(
                    self.llm_model_name,
                    system_instruction=formatted_prompt
                )
                chat = temp_model.start_chat(history=history)
                response = chat.send_message(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"Labor flow error: {e}")
                return "[ESCALATE]"

        # --- 5. FARM/CROP QUERIES (Full RAG) ---
        logger.info(f"🌾 Farm query detected - Running RAG")
        
        # Search knowledge base
        retrieved_context = self.search_knowledge_base(user_message, top_k=5)
        
        # Build history summary
        history_text = ""
        if history:
            recent = history[-5:] if len(history) >= 5 else history
            history_text = "\n".join([
                f"{msg['role']}: {msg['parts'][0][:150]}" for msg in recent
            ])
        
        # Build RAG prompt
        prompt = f"""Recent conversation:
{history_text}

User's question: "{user_message}"

**Knowledge base context:**
{retrieved_context if retrieved_context else "No specific information found in database."}

**Instructions:**
1. Reply in {user_lang} (user's language)
2. Keep response SHORT (2-3 sentences max)
3. Use conversation history to understand context
4. If knowledge base has relevant info, use it naturally
5. If no relevant info, say: "मुझे इसके बारे में पक्की जानकारी नहीं है" and ask for more details
6. **CRITICAL**: ONLY add disclaimer `(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)` IF you mention specific spray/fertilizer/chemical names
7. Use emojis naturally: 🌾 🍇 ✅

Reply:"""

        try:
            formatted_prompt = SYSTEM_PROMPT.format(
                user_lang=user_lang,
                user_name=user_name
            )
            temp_model = genai.GenerativeModel(
                self.llm_model_name,
                system_instruction=formatted_prompt
            )
            chat = temp_model.start_chat(history=history)
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            logger.info(f"✅ RAG Reply generated: {reply[:100]}...")
            return reply
            
        except Exception as e:
            logger.error(f"RAG error: {str(e)}", exc_info=True)
            return "[ESCALATE]"