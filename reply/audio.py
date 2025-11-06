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
        # ✅ FIX: Get all available API keys
        self.api_keys = []
        for i in range(1, 6):  # API keys 1-5
            key_name = f'GEMINI_API_KEY_{i}'
            if hasattr(settings, key_name):
                self.api_keys.append(getattr(settings, key_name))
        
        if not self.api_keys:
            # Fallback to single key
            self.api_keys = [settings.GEMINI_API_KEY]
        
        self.model_id = 'gemini-2.0-flash-exp'
        self.current_key_index = 0
        
        logger.info(f"🎤 AudioTranscriptionService initialized with {len(self.api_keys)} API keys")
    
    def _get_next_api_key(self):
        """Rotate through API keys for load balancing"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    def transcribe_audio(self, audio_bytes, mime_type='audio/ogg'):
        """
        Transcribe WhatsApp audio to text using Gemini's native audio support
        No external libraries needed!
        """
        try:
            # WhatsApp sends "audio/ogg; codecs=opus" - clean it
            clean_mime_type = mime_type.split(';')[0].strip()
            
            # Map WhatsApp MIME types to Gemini-supported ones
            mime_type_map = {
                'audio/ogg': 'audio/ogg',
                'audio/mpeg': 'audio/mpeg',
                'audio/mp3': 'audio/mpeg',
                'audio/mp4': 'audio/mp4',
                'audio/aac': 'audio/aac',
                'audio/amr': 'audio/amr',
                'audio/wav': 'audio/wav',
            }
            
            gemini_mime_type = mime_type_map.get(clean_mime_type, 'audio/ogg')
            
            # Determine file extension
            ext_map = {
                'audio/ogg': '.ogg',
                'audio/mpeg': '.mp3',
                'audio/mp4': '.m4a',
                'audio/aac': '.aac',
                'audio/amr': '.amr',
                'audio/wav': '.wav',
            }
            
            extension = ext_map.get(gemini_mime_type, '.ogg')
            
            # Create temporary file with correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio_path = temp_audio.name
            
            logger.info(f"🎤 Uploading audio to Gemini (type: {gemini_mime_type})...")
            
            # Upload audio with EXPLICIT mime_type
            audio_file = genai.upload_file(
                path=temp_audio_path,
                mime_type=gemini_mime_type  # ✅ FIX: Explicitly set MIME type
            )
            
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