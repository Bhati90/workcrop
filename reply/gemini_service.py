# In whatsapp_chat/gemini_service.py

import google.generativeai as genai
from django.conf import settings
import logging
import json
import numpy as np
import os
import re

logger = logging.getLogger(__name__)

# --- This is the NEW "General Awareness" Prompt ---
# v5: More human-like, handles acknowledgments, and stricter disclaimer rules.
SYSTEM_PROMPT = """
You are a professional, farmer-friendly WhatsApp assistant for an agriculture company. 
Your tone should be helpful, polite, and conversational. 
You can use emojis (like 🙏, 🍇, 👨‍🌾, ✅, 📅) where appropriate to make the conversation feel more human.

## 🌾 Company Information
- **Offerings:** We connect farmers with labor (मजूर), provide crop advice (especially for grapes 🍇), and allow product booking.
- **Rules:** Be polite, professional, and use simple, farmer-friendly language.
- **Language:** You **MUST** reply in the **exact same language** as the user ({user_lang}).
- **Name:** The user's name in our system is {user_name}.

## 🚫 Restrictions
- **STAY ON TOPIC:** Only discuss agriculture, farm labor, and agri-products.
- **DO NOT** answer non-agri questions (politics, jokes, etc.).
- **DO NOT** make up information.

## ⚠️ Query Handling Logic
- **[IGNORE]:** Respond *only* with this word if the query is spam, abuse, or gibberish.
- **[ESCALATE]:** Respond *only* with this phrase if the user is very angry, the query is too complex (e.g., severe unknown disease), or it's a non-agri question (e.g., "what's the weather?").
- **Acknowledgments:** If the user sends a simple acknowledgment (like 'ok', 'thanks'), give a very short, polite reply (e.g., "You're welcome! 🙏", "Great! 👍", "ठीक आहे.").
- **Follow-ups:** If the user asks for an 'update' on a pending request, politely tell them you are still checking and will get back to them.

## ✅ Your Task
You will be given "Context from Knowledge Base" and the "User's Question".
1.  Analyze the "Context" to answer the "User's Question".
2.  Follow all communication rules.
3.  **CRITICAL DISCLAIMER RULE:**
    * **ADD THIS DISCLAIMER:** `(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)` *if and only if* you are giving **specific farm advice** (like a spray/fertilizer name or dose).
    * **NEVER** add the disclaimer for general chat, labor requests, or simple questions.
4.  If the "Context" is not helpful or empty, politely say you cannot find that specific detail and ask for clarification.
5.  If the question is about labor or a general topic (like saying hello), you don't need specific context. Just answer politely.
"""

# --- NEW Keyword Sets (v5) ---

# 1. GREETINGS (Get a reply)
GREETING_WORDS = {
    'hello', 'hi', 'hey', 'namaste', 'नमस्ते', 'salam'
}

# 2. ACKNOWLEDGMENTS (Get a *short* reply, not ignored)
ACK_WORDS = {
    'ok', 'k', 'ok.', 'okay', 'okk', 'okkay',
    'thanks', 'thank you', 'ty', 'thx', 'dhanyawad', 'dhanyavad', 'धन्यवाद',
    'ji', 'ha', 'haa', 'yes', 'ho', 'accha', 'acha', 'बरं', 'ठीक आहे'
}

# 3. FOLLOW-UPS (Get a "still checking" reply)
FOLLOW_UP_WORDS = {
    'update', 'any update', 'what happened', 'any news',
    'अपडेट', 'काही बातमी', 'काय झालं'
}

# 4. LABOR (Go to booking flow)
LABOR_KEYWORDS = {
    'labor', 'labour', 'majur', 'mazdoor', 'kamgar', 'worker',
    'मजूर', 'कामगार', 'मज़दूर', 'चटणी', 'chatni'
}

# 5. IGNORE (No reply, only for spam/test)
IGNORE_WORDS = {
    'test', 'testing' # We will ignore 'test' messages
}


class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        
        self.llm_model_name = "gemini-2.0-flash-exp"
        self.embedding_model_name = "text-embedding-004"
        
        self.llm = genai.GenerativeModel(
            self.llm_model_name,
            # Set the new System Prompt as a base instruction
            system_instruction=SYSTEM_PROMPT 
        )
        
        self.db_chunks = []
        self.db_vectors = None
        self.load_vector_database()

    def load_vector_database(self):
        """Loads the vector_database.json file into memory."""
        db_path = os.path.join(settings.BASE_DIR, 'vector_database.json')
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self.db_chunks = json.load(f)
            
            self.db_vectors = np.array([chunk['vector'] for chunk in self.db_chunks])
            norms = np.linalg.norm(self.db_vectors, axis=1, keepdims=True)
            self.db_vectors = self.db_vectors / norms
            
            logger.info(f"Successfully loaded {len(self.db_chunks)} vectors into memory.")
        
        except FileNotFoundError:
            logger.error(f"CRITICAL: vector_database.json not found at {db_path}.")
            logger.error("Please run `create_vector_database.py` first.")
            self.db_chunks = []
            self.db_vectors = None
        except Exception as e:
            logger.error(f"Error loading vector database: {e}")
            self.db_chunks = []
            self.db_vectors = None

    def _embed(self, text, task_type="RETRIEVAL_QUERY"):
        """Helper function to embed text."""
        try:
            result = genai.embed_content(
                model=self.embedding_model_name,
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error embedding text '{text}': {e}")
            return None

    def search_knowledge_base(self, query, top_k=3):
        """Finds the top_k most relevant text chunks from the vector database."""
        if self.db_vectors is None or len(self.db_vectors) == 0:
            return "" 

        query_vector = self._embed(query, task_type="RETRIEVAL_QUERY")
        if query_vector is None:
            return ""

        query_vector = np.array(query_vector)
        query_vector = query_vector / np.linalg.norm(query_vector)

        scores = np.dot(self.db_vectors, query_vector)
        top_k_indices = np.argsort(scores)[-top_k:][::-1]

        context = ""
        for i in top_k_indices:
            chunk = self.db_chunks[i]
            context += f"Source: {chunk['source']}\nType: {chunk['type']}\nContent: {chunk['content']}\n---\n"
        
        logger.info(f"RAG: Found {top_k} relevant chunks for query: '{query}'")
        return context

    # --- Helper Functions for Filtering ---
    def _is_match(self, text, word_set):
        """Checks if the text matches any word in the set."""
        lowered_text = text.strip().lower()
        if lowered_text in word_set:
            return True
        # Check for partial match in follow-up words
        if word_set == FOLLOW_UP_WORDS:
            for word in word_set:
                if word in lowered_text:
                    return True
        return False

    def _is_labor_request(self, text):
        """Check if the message is a labor request."""
        for keyword in LABOR_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                return True
        return False
    
    def _get_simple_reply(self, history, prompt_instruction):
        """Calls the LLM for a simple, non-RAG reply."""
        try:
            # We use a fresh chat to avoid history contamination for simple replies
            chat = self.llm.start_chat(history=[]) 
            response = chat.send_message(prompt_instruction)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error in Gemini simple reply: {str(e)}", exc_info=True)
            return "[ESCALATE]" # Escalate if the simple reply fails

    def generate_reply(self, history, user_message, user_lang, user_name):
        """
        Generates a reply using the 5-step RAG process.
        """
        
        lowered_message = user_message.strip().lower()

        # --- PRE-FILTERS (v5) ---

        # 1. IGNORE (Spam/Test) -> [IGNORE]
        if self._is_match(lowered_message, IGNORE_WORDS) or len(lowered_message) < 2:
            logger.info(f"Message '{user_message}' is ignorable. Returning [IGNORE].")
            return "[IGNORE]"

        # 2. GREETINGS -> (Simple Reply)
        if self._is_match(lowered_message, GREETING_WORDS):
            logger.info(f"Message '{user_message}' is a greeting. Bypassing RAG.")
            prompt = (
                f"My name is {user_name} and my language is {user_lang}. The user just said: \"{user_message}\". "
                f"Please give a short, polite, professional greeting in {user_lang} and ask how you can help with their farm. Use an emoji. (e.g., नमस्ते! 🙏 मी कशी मदत करू शकतो?)"
            )
            return self._get_simple_reply(history, prompt)

        # 3. ACKNOWLEDGMENTS ("ok", "thanks") -> (Simple Reply)
        if self._is_match(lowered_message, ACK_WORDS):
            logger.info(f"Message '{user_message}' is an acknowledgment. Bypassing RAG.")
            prompt = (
                f"My name is {user_name} and my language is {user_lang}. The user just sent an acknowledgment: \"{user_message}\". "
                f"Please give a very short, polite, one-or-two-word confirmation in {user_lang}. (e.g., 'You're welcome! 🙏', 'Great! 👍', 'ठीक आहे.', 'धन्यवाद!')"
            )
            return self._get_simple_reply(history, prompt)
        
        # 4. FOLLOW-UPS ("any update?") -> (Simple Reply)
        if self._is_match(lowered_message, FOLLOW_UP_WORDS):
            logger.info(f"Message '{user_message}' is a follow-up. Bypassing RAG.")
            prompt = (
                f"My name is {user_name} and my language is {user_lang}. The user just asked for an update: \"{user_message}\". "
                f"Look at the last message in the history: {history[-1] if history else 'No history'}. "
                f"Politely tell them in {user_lang} that you are still checking on their last request (e.g., 'I am still checking on this for you') and will update them soon. Be very polite."
            )
            # We *can* use the main chat here to be context-aware, but a simple reply is safer
            return self._get_simple_reply(history, prompt) # Using simple reply to avoid RAG error

        # 5. LABOR -> (Booking Flow)
        if self._is_labor_request(lowered_message):
            logger.info(f"Message '{user_message}' is a labor request. Bypassing RAG search.")
            prompt_history = [
                *history,
                {"role": "user", "parts": [
                    f"My name is {user_name} and my language is {user_lang}. "
                    f"The user's latest message is: \"{user_message}\"\n\n"
                    "This is a labor request. Please be helpful and ask for the "
                    "key details we need: \n1. What task (e.g., pruning, spraying)? \n2. How many laborers? \n3. What date? 📅 \n4. What location/address? \n"
                    "If they already provided some info, confirm it and ask for what's missing. Be conversational and use emojis. (e.g., 👨‍🌾, ✅)"
                ]}
            ]
            try:
                chat = self.llm.start_chat(history=prompt_history[:-1])
                response = chat.send_message(prompt_history[-1]['parts'][0])
                return response.text.strip()
            except Exception as e:
                logger.error(f"Error in Gemini labor request: {str(e)}", exc_info=True)
                return "[ESCALATE]"

        # --- 6. FARM QUERY -> (Full RAG) ---
        logger.info(f"Message '{user_message}' is a farm query. Starting RAG.")
        retrieved_context = self.search_knowledge_base(user_message)
        
        prompt_history = [
            *history,
            {"role": "user", "parts": [
                f"""My name is {user_name} and my language is {user_lang}.
User's Latest Question: "{user_message}"

Here is the relevant context from our knowledge base:
<context>
{retrieved_context if retrieved_context else "No specific context was found."}
</context>

Please use this context (if relevant) to formulate a helpful, polite, farmer-friendly reply.
Remember the CRITICAL disclaimer rule: ONLY add the disclaimer if you give a specific spray/fertilizer recommendation.
"""
            ]}
        ]

        try:
            chat = self.llm.start_chat(history=prompt_history[:-1]) 
            response = chat.send_message(prompt_history[-1]['parts'][0]) 
            text = response.text.strip()
            logger.info(f"Gemini (RAG) Reply: {text}")
            return text

        except Exception as e:
            logger.error(f"Error in Gemini generate_reply (RAG): {str(e)}", exc_info=True)
            return "[ESCALATE]"