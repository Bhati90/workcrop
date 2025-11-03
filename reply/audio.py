import google.generativeai as genai
from django.conf import settings
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """
    Handles audio transcription using Gemini 2.0 Flash
    Supports: Marathi, Hindi, English (auto-detect)
    """
    
    def __init__(self):
        # Use first available API key from multi-gemini setup
        self.api_key = settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    def transcribe_audio(self, audio_bytes, mime_type='audio/ogg'):
        """
        Transcribe WhatsApp audio to text using Gemini's native audio support
        No external libraries needed!
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio_path = temp_audio.name
            
            logger.info(f"🎤 Uploading audio to Gemini...")
            
            # Upload audio directly to Gemini (supports audio/ogg, audio/mp3, etc.)
            audio_file = genai.upload_file(path=temp_audio_path)
            
            # Gemini 2.0 Flash can process audio natively
            prompt = """
Listen to this audio message and transcribe it accurately.

Rules:
- Auto-detect language (Marathi/Hindi/English/Mixed)
- Write in the SAME language as spoken
- If Hindi/Marathi, use Devanagari script (देवनागरी)
- If English, use English script
- Keep natural and conversational
- Handle code-mixing (Hinglish/Marathlish)

Return ONLY the transcription text, nothing else.
"""
            
            # Generate transcription
            response = self.model.generate_content([prompt, audio_file])
            transcription = response.text.strip()
            
            # Cleanup
            os.unlink(temp_audio_path)
            genai.delete_file(audio_file.name)
            
            logger.info(f"✅ Transcribed: {transcription[:100]}...")
            return transcription
            
        except Exception as e:
            logger.error(f"❌ Audio transcription error: {str(e)}")
            
            # Cleanup on error
            try:
                if 'temp_audio_path' in locals():
                    os.unlink(temp_audio_path)
                if 'audio_file' in locals():
                    genai.delete_file(audio_file.name)
            except:
                pass
            
            return None
    
    def detect_language(self, text):
        """Detect if text is Hindi/Marathi/English"""
        if any(u'\u0900' <= char <= u'\u097f' for char in text):
            # Devanagari script detected
            marathi_indicators = ['आहे', 'मला', 'तुम्हाला', 'काय', 'कसे', 'पाहिजे', 'होते']
            if any(word in text for word in marathi_indicators):
                return 'mr'
            return 'hi'
        return 'en'