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
# v4: More human-like, uses emojis, and has smarter disclaimer rules.
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
- **[IGNORE]:** Respond *only* with this word if the query is spam, abuse, or a simple acknowledgment (e.g., 'ok', 'thanks', 'ha', 'yes').
- **[ESCALATE]:** Respond *only* with this phrase if the user is very angry, the query is too complex (e.g., severe unknown disease), or it's a non-agri question (e.g., "what's the weather?").

## ✅ Your Task
You will be given "Context from Knowledge Base" and the "User's Question".
1.  Analyze the "Context" to answer the "User's Question".
2.  Follow all communication rules.
3.  **IMPORTANT DISCLAIMER RULE:**
    * **ADD THIS DISCLAIMER:** `(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)` *if and only if* you are giving **specific farm advice** (like a spray/fertilizer name or dose).
    * **DO NOT ADD THE DISCLAIMER** for general chat, labor requests, or simple questions.
4.  If the "Context" is not helpful or empty, politely say you cannot find that specific detail and ask for clarification.
5.  If the question is about labor or a general topic (like saying hello), you don't need specific context. Just answer politely.
"""

# --- NEW Keyword Sets ---

# Keywords for a simple greeting reply
GREETING_WORDS = {
    'hello', 'hi', 'hey', 'namaste', 'नमस्ते', 'salam'
}

# Keywords to truly ignore (acknowledgments, simple noise)
IGNORE_WORDS = {
    'ok', 'k', 'ok.', 'okay', 'okk', 'okkay',
    'thanks', 'thank you', 'ty', 'thx', 'dhanyawad', 'dhanyavad', 'धन्यवाद',
    'ji', 'ha', 'haa', 'yes', 'ho', 'accha', 'acha', 'बरं', 'ठीक आहे',
    'test', 'testing' # We will ignore 'test' messages
}

# Keywords to detect a labor request (in lowercase)
LABOR_KEYWORDS = {
    'labor', 'labour', 'majur', 'mazdoor', 'kamgar', 'worker',
    'मजूर', 'कामगार', 'मज़दूर', 'चटणी', 'chatni' # 'chatni' (pruning) is a task, but strongly implies labor
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
            return "" # Return empty context if DB isn't loaded

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

    # --- NEW Helper Functions for Filtering ---
    def _is_labor_request(self, text):
        """Check if the message is a labor request."""
        # \b is a word boundary, so 'labor' matches but not 'laboratory'
        for keyword in LABOR_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                return True
        return False

    def _is_ignorable(self, text):
        """Check if the message is a simple acknowledgment or noise."""
        if text in IGNORE_WORDS or len(text) < 3:
            return True
        return False
    
    def _is_greeting(self, text):
        """Check if the message is a simple greeting."""
        return text in GREETING_WORDS
    # --- End of Helper Functions ---


    def generate_reply(self, history, user_message, user_lang, user_name):
        """
        Generates a reply using the RAG (Retrieval-Augmented Generation) process.
        """
        
        lowered_message = user_message.strip().lower()

        # --- PRE-FILTERS (NEW ORDER) ---

        # 1. Check for simple "ignore" words (acknowledgments, noise)
        if self._is_ignorable(lowered_message):
            logger.info(f"Message '{user_message}' is simple/ignorable. Returning [IGNORE].")
            return "[IGNORE]"

        # 2. Check for "greetings"
        if self._is_greeting(lowered_message):
            logger.info(f"Message '{user_message}' is a greeting. Bypassing RAG.")
            # This is a non-RAG call. We just give a simple reply.
            prompt = [
                # Give context to the AI for a simple, non-RAG reply
                {"role": "user", "parts": [
                    f"My name is {user_name} and my language is {user_lang}. The user just said: \"{user_message}\". "
                    f"Please give a short, polite, professional greeting in {user_lang} and ask how you can help with their farm. Use an emoji."
                ]}
            ]
            try:
                # We use a fresh model instance for this simple, one-off query
                # This avoids confusing the main chat history
                simple_model = genai.GenerativeModel(self.llm_model_name)
                response = simple_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"Error in Gemini greeting reply: {str(e)}", exc_info=True)
                # Provide a safe, hardcoded fallback
                return "Hello! 🙏 How can I help you with your farm today?" if user_lang == 'en' else "नमस्ते! 🙏 मी तुमच्या शेतीसाठी कशी मदत करू शकतो?"

        # 3. Check for "labor" requests
        if self._is_labor_request(lowered_message):
            logger.info(f"Message '{user_message}' is a labor request. Bypassing RAG search.")
            # This is a non-RAG call. We ask the AI to act as a booking agent.
            prompt = [
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
                # Use the main chat model here, passing in the history
                chat = self.llm.start_chat(history=prompt_history[:-1])
                response = chat.send_message(prompt_history[-1]['parts'][0])
                return response.text.strip()
            except Exception as e:
                logger.error(f"Error in Gemini labor request: {str(e)}", exc_info=True)
                return "[ESCALATE]"

        # --- 4. If not ignored, greeting, or labor, proceed with RAG search ---
        logger.info(f"Message '{user_message}' is a farm query. Starting RAG.")
        retrieved_context = self.search_knowledge_base(user_message)
        
        # Build the final prompt for the AI
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
Remember the disclaimer rule: ONLY add the disclaimer if you give a specific spray/fertilizer recommendation.
"""
            ]}
        ]

        # --- 3. Generate (Ask the AI) ---
        try:
            # We use `start_chat` because the `system_instruction` is set
            chat = self.llm.start_chat(history=prompt_history[:-1]) # Pass all but the last user message as history
            response = chat.send_message(prompt_history[-1]['parts'][0]) # Send the final composed prompt
            
            text = response.text.strip()
            logger.info(f"Gemini (RAG) Reply: {text}")

            # The AI itself will return [IGNORE] or [ESCALATE] based on the prompt
            return text

        except Exception as e:
            logger.error(f"Error in Gemini generate_reply (RAG): {str(e)}", exc_info=True)
            return "[ESCALATE]" # Escalate on any technical failure