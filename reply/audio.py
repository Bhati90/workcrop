import google.generativeai as genai
from django.conf import settings
import logging
import tempfile
import os
import multi_gemini_service

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """
    Handles audio transcription using Gemini 2.0 Flash
    Supports: Marathi, Hindi, English (auto-detect)
    """
    
    def __init__(self):
        self.multi_gemini_service = multi_gemini_service
        
    def _pick_instance(self):
        # Select the best available GeminiModelConfig instance
        for inst in sorted(self.multi_gemini_service.instances, key=lambda i: i.priority):
            if inst.is_available():
                return inst
        raise Exception("❌ No Gemini instances available (all limits exceeded or failed)!")
    
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
            # ✅ Pick the best available Gemini instance for each transcription
            instance = self._pick_instance()
            # Initialize model with that instance's API KEY and model_id
            genai.configure(api_key=instance.api_key)  # This sets API key globally (Gemini SDK)
            model = genai.GenerativeModel(instance.model_id)

            try:
                response = model.generate_content([prompt, audio_file])
                transcription = response.text.strip()
                instance.record_request()
                logger.info(f"✅ Transcribed: {transcription[:100]}...")
            except Exception as e:
                instance.record_failure()
                logger.error(f"❌ Gemini model error: {str(e)}")
                transcription = None
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