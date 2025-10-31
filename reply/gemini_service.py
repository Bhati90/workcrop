import google.generativeai as genai
from django.conf import settings

class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        self.model_name = "gemini-2.0-flash-exp"
    
    def generate_reply(self, history, user_message, user_lang, user_name, context_info):
        chat = genai.GenerativeModel(self.model_name).start_chat(history=[
            {"role": m['role'], "parts": [m['content']]} for m in history
        ])
        # Compose prompt
        prompt = (
            f"Company: {context_info['company_overview']}\n"
            f"Mission: {context_info['mission']}\n"
            f"Offerings: {context_info['core_offerings']}\n"
            f"Restrictions: {context_info['restrictions']}\n"
            f"Previous user name: {user_name}\n"
            f"Last message in {user_lang}: {user_message}\n"
            f"Please reply in the same language. Use polite, farmer-friendly tone. "
            f"Do NOT respond to non-agriculture, personal, or external queries. "
            f"If message looks spam, totally ignore and do not reply. "
            f"If message needs escalation (complex, ambiguous, abusive), reply as ‘Our team will reach you soon.’"
        )
        response = chat.send_message(prompt)
        text = response.text.strip()
        return text
