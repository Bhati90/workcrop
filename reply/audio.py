import google.generativeai as genai
from django.conf import settings
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """
    Handles audio transcription using Gemini 2.0 Flash
    ✅ USES MultiGeminiService instances for model selection
    ✅ FIXED: Proper error handling for file operations
    """
    
    def __init__(self, multi_gemini_instance=None):
        """
        Initialize with MultiGeminiService instance
        ✅ Uses multi_gemini's model selection and API key rotation
        """
        self.multi_gemini = multi_gemini_instance
        
        if not self.multi_gemini:
            # Fallback: Use own API keys if multi_gemini not provided
            self.api_keys = []
            for i in range(1, 6):
                key_name = f'GEMINI_API_KEY_{i}'
                if hasattr(settings, key_name):
                    self.api_keys.append(getattr(settings, key_name))
            
            if not self.api_keys:
                self.api_keys = [settings.GEMINI_API_KEY]
            
            self.current_key_index = 0
            logger.info(f"🎤 AudioTranscriptionService initialized with {len(self.api_keys)} API keys (fallback mode)")
        else:
            logger.info(f"🎤 AudioTranscriptionService initialized with MultiGeminiService ({len(self.multi_gemini.instances)} instances available)")
    
    def _get_next_api_key_fallback(self):
        """Fallback: Rotate through API keys if multi_gemini not available"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    def transcribe_audio(self, audio_bytes, mime_type='audio/ogg', max_retries=3):
        """
        Transcribe WhatsApp audio to text using Gemini's native audio support
        ✅ USES MultiGeminiService for model and API key selection!
        """
        attempts = 0
        last_error = None
        temp_audio_path = None
        audio_file = None
        tried_instances = set()
        
        while attempts < max_retries:
            try:
                # ✅ Use MultiGeminiService to select instance
                if self.multi_gemini:
                    instance = self.multi_gemini.select_instance("general")
                    
                    # Avoid retrying same instance
                    if instance.name in tried_instances and len(tried_instances) < len(self.multi_gemini.instances):
                        available = [i for i in self.multi_gemini.instances 
                                   if i.name not in tried_instances and i.is_available()]
                        if available:
                            instance = available[0]
                        else:
                            break
                    
                    tried_instances.add(instance.name)
                    
                    api_key = instance.api_key
                    model_id = instance.model_id
                    
                    logger.info(
                        f"🎤 Transcription attempt {attempts + 1}: {instance.name} "
                        f"(Usage: {instance.get_today_usage()}/{instance.requests_per_day})"
                    )
                else:
                    # Fallback mode
                    api_key = self._get_next_api_key_fallback()
                    model_id = 'gemini-2.0-flash-exp'
                    logger.info(f"🎤 Transcription attempt {attempts + 1} with fallback API key")
                
                genai.configure(api_key=api_key)
                
                # Clean mime type
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
                    mime_type=gemini_mime_type
                )
                
                # ✅ CRITICAL FIX: Wait for file to be ready
                import time
                time.sleep(2)  # Give Gemini time to process the file
                
                # ✅ Create model using the selected model_id
                model = genai.GenerativeModel(model_id)
                
                # Transcription prompt
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
                response = model.generate_content([prompt, audio_file])
                transcription = response.text.strip()
                
                # ✅ Record success in MultiGeminiService (Redis)
                if self.multi_gemini:
                    instance.record_request()
                
                # ✅ Safe cleanup
                self._safe_cleanup(temp_audio_path, audio_file)
                
                logger.info(f"✅ Transcribed: {transcription[:100]}...")
                return transcription
                
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                attempts += 1
                
                # ✅ Record failure in MultiGeminiService (Redis)
                if self.multi_gemini and instance:
                    instance.record_failure()
                
                # Log the specific error
                if "403" in error_msg:
                    logger.error(f"❌ Gemini permission error (attempt {attempts}): {error_msg[:200]}")
                elif "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning(f"⏱️ Quota exceeded, trying next instance...")
                elif "503" in error_msg or "overloaded" in error_msg.lower():
                    logger.warning(f"⏱️ Service overloaded, trying next instance...")
                else:
                    logger.error(f"❌ Transcription attempt {attempts} failed: {error_msg[:200]}")
                
                # ✅ Safe cleanup even on error
                self._safe_cleanup(temp_audio_path, audio_file)
                
                # Continue to next attempt
                if attempts < max_retries:
                    time.sleep(1)  # Pause before retry
                    continue
        
        # All attempts failed
        logger.error(f"💥 All transcription attempts failed! Last error: {last_error}")
        return None
    
    def _safe_cleanup(self, temp_audio_path, audio_file):
        """
        ✅ SAFE cleanup that won't fail the transcription
        """
        # Clean up temp file
        if temp_audio_path:
            try:
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
                    logger.debug(f"🧹 Cleaned up temp file")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete temp file: {e}")
        
        # Clean up Gemini file
        if audio_file:
            try:
                genai.delete_file(audio_file.name)
                logger.debug(f"🧹 Cleaned up Gemini file")
            except Exception as e:
                # ✅ CRITICAL: Don't raise exception if delete fails!
                logger.warning(f"⚠️ Could not delete Gemini file (will auto-expire): {e}")
    
    def detect_language(self, text):
        """Detect if text is Hindi/Marathi/English"""
        if any(u'\u0900' <= char <= u'\u097f' for char in text):
            # Devanagari script detected
            marathi_indicators = ['आहे', 'मला', 'तुम्हाला', 'काय', 'कसे', 'पाहिजे', 'होते']
            if any(word in text for word in marathi_indicators):
                return 'mr'
            return 'hi'
        return 'en'