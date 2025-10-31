# In whatsapp_chat/gemini_service.py

import google.generativeai as genai
from django.conf import settings
import logging
import json
import numpy as np
import os

logger = logging.getLogger(__name__)

# --- This is the NEW "General Awareness" Prompt ---
# All specific crop knowledge has been REMOVED
# It will be "augmented" (added) by the RAG search.
SYSTEM_PROMPT = """
You are a professional, farmer-friendly WhatsApp assistant for an agriculture company.
Your expertise is in Grapes (द्राक्ष).

## 🌾 Company Information
- **Offerings:** We connect farmers with labor (मजूर), provide crop advice (especially for grapes), and allow product booking.
- **Rules:** Be polite, professional, and use simple, farmer-friendly language.
- **Language:** You **MUST** reply in the **exact same language** as the user ({user_lang}).
- **Name:** The user's name in our system is {user_name}.

## 🚫 Restrictions
- **STAY ON TOPIC:** Only discuss agriculture, farm labor, and agri-products.
- **DO NOT** answer non-agri questions (politics, jokes, etc.).
- **DO NOT** make up information. If you don't know, say so.
- **DO NOT** just repeat the context. Use it to build a natural, helpful answer.

## ⚠️ Query Handling Logic
- **[IGNORE]:** Respond *only* with this word if the query is spam, abuse, or a single, non-sensical word (e.g., 'ok', 'test').
- **[ESCALATE]:** Respond *only* with this phrase if the user is angry, the query is too complex (e.g., severe unknown disease), or it's a non-agri question (e.g., "what's the weather?").

## ✅ Your Task
You will be given "Context from Knowledge Base" and the "User's Question".
1.  Analyze the "Context" to answer the "User's Question".
2.  Follow all communication rules.
3.  If the "Context" is not helpful or empty, politely say you cannot find that specific detail and ask for clarification.
4.  If the question is about labor or a general topic (like saying hello), you don't need specific context. Just answer politely.
"""

class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        
        self.llm_model_name = "gemini-2.0-flash-exp"
        self.embedding_model_name = "text-embedding-004"
        
        self.llm = genai.GenerativeModel(self.llm_model_name)
        
        # --- Load the gemini Database into Memory ---
        self.db_chunks = []
        self.db_vectors = None
        self.load_vector_database()

    def load_vector_database(self):
        """Loads the vector_database.json file into memory."""
        db_path = os.path.join(settings.BASE_DIR, 'vector_database.json')
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self.db_chunks = json.load(f)
            
            # Store all vectors in a single NumPy array for fast math
            self.db_vectors = np.array([chunk['vector'] for chunk in self.db_chunks])
            
            # Normalize vectors for cosine similarity (makes calculation faster)
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

    def _embed(self, text):
        """Helper function to embed a single piece of text (like the user query)."""
        try:
            result = genai.embed_content(
                model=self.embedding_model_name,
                content=text,
                task_type="RETRIEVAL_QUERY" # Optimize for search query
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            return None

    def search_knowledge_base(self, query, top_k=3):
        """
        Finds the top_k most relevant text chunks from the vector database.
        """
        if self.db_vectors is None:
            return "" # Return empty context if DB isn't loaded

        # 1. Embed the user's query
        query_vector = self._embed(query)
        if query_vector is None:
            return ""

        # 2. Normalize the query vector
        query_vector = np.array(query_vector)
        query_vector = query_vector / np.linalg.norm(query_vector)

        # 3. Calculate Cosine Similarity (fast dot product)
        # This is the "search"
        scores = np.dot(self.db_vectors, query_vector)

        # 4. Get the indices of the top_k highest scores
        top_k_indices = np.argsort(scores)[-top_k:][::-1]

        # 5. Format the context for the AI
        context = ""
        for i in top_k_indices:
            chunk = self.db_chunks[i]
            context += f"Source: {chunk['source']}\nType: {chunk['type']}\nContent: {chunk['content']}\n---\n"
        
        logger.info(f"RAG: Found {top_k} relevant chunks for query: '{query}'")
        return context

    def generate_reply(self, history, user_message, user_lang, user_name):
        """
        Generates a reply using the RAG (Retrieval-Augmented Generation) process.
        """
        
        # --- 1. Retrieve (Search) ---
        # Find relevant knowledge based on the user's message
        retrieved_context = self.search_knowledge_base(user_message)
        
        # --- 2. Augment (Build Prompt) ---
        formatted_system_prompt = SYSTEM_PROMPT.format(
            user_lang=user_lang,
            user_name=user_name
        )

        # Build the final prompt history for the AI
        prompt_history = [
            # Set the AI's "personality" and rules
            {"role": "user", "parts": [formatted_system_prompt]},
            {"role": "model", "parts": ["Ok, I am ready to help the farmer."]},
            
            # Add the recent conversation history
            *history,
            
            # Add the new user message AND the context we found
            {"role": "user", "parts": [
                f"""User's Latest Question: "{user_message}"

Here is the relevant context from our knowledge base:
<context>
{retrieved_context}
</context>

Please use this context to formulate a helpful, polite, farmer-friendly reply in {user_lang}.
"""
            ]}
        ]

        # --- 3. Generate (Ask the AI) ---
        try:
            # We use `generate_content` directly, not `start_chat`
            # because we are building a custom prompt history each time
            response = self.llm.generate_content(prompt_history)
            text = response.text.strip()
            
            logger.info(f"Gemini (RAG) Reply: {text}")

            # Check for AI's decision to ignore or escalate
            if text == "[IGNORE]" or text == "[ESCALATE]":
                return text

            # Add the mandatory disclaimer to all valid responses
            disclaimer_hi = "\n\n(कृपया फवारणी करण्यापूर्वी तुमच्या प्लॉटची परिस्थिती आणि हवामान तपासून घ्या.)"
            disclaimer_en = "\n\n(Please check your plot conditions and the weather before spraying.)"
            
            disclaimer = disclaimer_hi if user_lang == 'hi' else disclaimer_en
            
            # Only add disclaimer if it's a real answer, not a simple greeting
            if len(text) > 50 and "Source:" not in text: # simple heuristic
                 return text + disclaimer
            else:
                 return text

        except Exception as e:
            logger.error(f"Error in Gemini generate_reply (RAG): {str(e)}", exc_info=True)
            return "[ESCALATE]" # Escalate on any technical failure