import google.generativeai as genai
from django.conf import settings
from django.core.cache import cache
import logging
import tempfile
import os
import time
import random
from collections import defaultdict


logger = logging.getLogger(__name__)


class AudioModelConfig:
    """Configuration for each Gemini API + Audio Model combination"""
    def __init__(self, name, api_key, model_id, requests_per_day=50, priority=1):
        self.name = name
        self.api_key = api_key
        self.model_id = model_id
        self.requests_per_day = requests_per_day
        self.priority = priority
        self.failure_count = 0
        
    def get_today_usage(self):
        """Get request count for today"""
        cache_key = f"audio_{self.name}_daily_count"
        return cache.get(cache_key, 0)
    
    def is_available(self):
        """Check if this model instance is under daily limit"""
        usage = self.get_today_usage()
        # Keep 5 requests buffer
        return usage < (self.requests_per_day - 5)
    
    def record_request(self):
        """Record a successful request"""
        cache_key = f"audio_{self.name}_daily_count"
        current = cache.get(cache_key, 0)
        # Cache until midnight
        import datetime
        now = datetime.datetime.now()
        midnight = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min)
        seconds_until_midnight = int((midnight - now).total_seconds())
        cache.set(cache_key, current + 1, timeout=seconds_until_midnight)
        logger.info(f"🎤 {self.name}: {current + 1}/{self.requests_per_day} audio requests today")
    
    def record_failure(self):
        """Record a failure"""
        self.failure_count += 1
        cache_key = f"audio_{self.name}_failures"
        cache.set(cache_key, self.failure_count, timeout=300)  # Reset after 5 min


class MultiAudioTranscriptionService:
    """
    Load balancer for multiple Gemini APIs and Models for audio transcription
    Manages N API keys × M models = N×M total instances
    """
    
    def __init__(self):
        self.instances = self._initialize_instances()
        logger.info(f"🚀 MultiAudioTranscriptionService initialized with {len(self.instances)} instances")
    
    def _initialize_instances(self):
        """
        Create all combinations of API keys and audio-capable models
        """
        instances = []
        
        # Get all API keys from settings
        api_keys = []
        for i in range(1, 6):  # API keys 1-5
            key_name = f'GEMINI_API_KEY_{i}'
            if hasattr(settings, key_name):
                api_keys.append((i, getattr(settings, key_name)))
        
        # Fallback to single key if multi-key not configured
        if not api_keys and hasattr(settings, 'GEMINI_API_KEY'):
            api_keys.append((1, settings.GEMINI_API_KEY))
        
        if not api_keys:
            raise ValueError("❌ No Gemini API keys found! Add GEMINI_API_KEY or GEMINI_API_KEY_1-5 in settings")
        
        # Define audio-capable Gemini models (ordered by preference)
        models = [
            # Tier 1: Best audio models (highest priority)
            {
                'id': 'gemini-2.5-flash',
                'name': '2.5-flash',
                'priority': 1,
                'max_audio_hours': 8.4,  # ~1M tokens
            },
            {
                'id': 'gemini-2.5-pro',
                'name': '2.5-pro',
                'priority': 1,
                'max_audio_hours': 8.4,
            },
            # Tier 2: Fast and reliable
            {
                'id': 'gemini-2.0-flash-exp',
                'name': '2.0-flash-exp',
                'priority': 2,
                'max_audio_hours': 8.4,
            },
            # Tier 3: Backup options
            # {
            #     'id': 'gemini-1.5-flash',
            #     'name': '1.5-flash',
            #     'priority': 3,
            #     'max_audio_hours': 8.4,
            # },
            {
                'id': 'gemini-1.5-pro',
                'name': '1.5-pro',
                'priority': 3,
                'max_audio_hours': 8.4,
            },
        ]
        
        # Create instances for each API key + model combination
        for api_idx, api_key in api_keys:
            for model in models:
                instance_name = f"Audio-API{api_idx}-{model['name']}"
                instances.append(AudioModelConfig(
                    name=instance_name,
                    api_key=api_key,
                    model_id=model['id'],
                    requests_per_day=50,  # Adjust based on your quota
                    priority=model['priority']
                ))
        
        logger.info(f"✅ Created {len(instances)} audio transcription instances:")
        logger.info(f"   📍 {len(api_keys)} API keys × {len(models)} models")
        
        # Show summary by priority
        by_priority = defaultdict(int)
        for inst in instances:
            by_priority[inst.priority] += 1
        for priority, count in sorted(by_priority.items()):
            logger.info(f"   Priority {priority}: {count} instances")
        
        return instances
    
    def select_instance(self):
        """
        Select best available audio transcription instance
        Strategy:
        1. Filter by availability (under daily limit)
        2. Sort by priority + failure count
        3. Return best available
        """
        # Get available instances
        available = [inst for inst in self.instances if inst.is_available()]
        
        if not available:
            # All at limit, use least used
            available = sorted(self.instances, key=lambda x: x.get_today_usage())[:5]
            logger.warning(f"⚠️ All audio instances at limit, trying least used")
        
        # Filter by low failure count
        available = [inst for inst in available if inst.failure_count < 3]
        if not available:
            # Reset failures, try again
            for inst in self.instances:
                inst.failure_count = 0
            available = [inst for inst in self.instances if inst.is_available()][:5]
        
        # Sort by priority, then failure count, then usage
        available.sort(key=lambda x: (x.priority, x.failure_count, x.get_today_usage()))
        
        return available[0] if available else self.instances[0]
    
    def transcribe_audio(self, audio_bytes, mime_type='audio/ogg', max_retries=3):
        """
        Transcribe WhatsApp audio to text with automatic failover
        Supports: Marathi, Hindi, English (auto-detect)
        """
        attempts = 0
        tried_instances = set()
        temp_audio_path = None
        audio_file = None
        
        while attempts < max_retries:
            # Select best instance
            instance = self.select_instance()
            
            # Avoid retrying same instance
            if instance.name in tried_instances and len(tried_instances) < len(self.instances):
                available = [i for i in self.instances 
                           if i.name not in tried_instances and i.is_available()]
                if available:
                    instance = available[0]
                else:
                    break
            
            tried_instances.add(instance.name)
            attempts += 1
            
            logger.info(f"🎤 Audio Attempt {attempts}: {instance.name} (Usage: {instance.get_today_usage()}/{instance.requests_per_day})")
            
            try:
                # Configure API key
                genai.configure(api_key=instance.api_key)
                
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
                    'audio/flac': 'audio/flac',
                    'audio/aiff': 'audio/aiff',
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
                    'audio/flac': '.flac',
                    'audio/aiff': '.aiff',
                }
                
                extension = ext_map.get(gemini_mime_type, '.ogg')
                
                # Create temporary file with correct extension
                with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_audio:
                    temp_audio.write(audio_bytes)
                    temp_audio_path = temp_audio.name
                
                logger.info(f"🎤 Uploading audio to Gemini (type: {gemini_mime_type}, model: {instance.model_id})...")
                
                # Upload audio with EXPLICIT mime_type
                audio_file = genai.upload_file(
                    path=temp_audio_path,
                    mime_type=gemini_mime_type
                )
                
                # Create model
                model = genai.GenerativeModel(instance.model_id)
                
                # Enhanced prompt for multilingual transcription
                prompt = """
Listen to this audio message and transcribe it accurately.

Rules:
- Auto-detect language (Marathi/Hindi/English/Mixed)
- Write in the SAME language as spoken
- If Hindi/Marathi, use Devanagari script (देवनागरी)
- If English, use English script
- Keep natural and conversational
- Handle code-mixing (Hinglish/Marathlish)
- Preserve speaker intent and tone

Return ONLY the transcription text, nothing else.
"""
                
                # Generate transcription
                response = model.generate_content([prompt, audio_file])
                transcription = response.text.strip()
                
                if not transcription:
                        logger.error("Empty transcription")
                        return None
                    
                # Cleanup
                if temp_audio_path:
                    os.unlink(temp_audio_path)
                    temp_audio_path = None
                if audio_file:
                    genai.delete_file(audio_file.name)
                    audio_file = None
                
                # Record success
                instance.record_request()
                logger.info(f"✅ Audio transcription success with {instance.name}: {transcription[:100]}...")
                
                return transcription
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ {instance.name} audio transcription failed: {error_msg[:150]}")
                
                # Cleanup on error
                try:
                    if temp_audio_path and os.path.exists(temp_audio_path):
                        os.unlink(temp_audio_path)
                        temp_audio_path = None
                    if audio_file:
                        genai.delete_file(audio_file.name)
                        audio_file = None
                except Exception as cleanup_error:
                    logger.error(f"Cleanup error: {cleanup_error}")
                
                # Record failure
                instance.record_failure()
                
                # Handle specific errors
                if "429" in error_msg or "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                    logger.warning(f"⏱️ {instance.name} quota exceeded, trying next")
                    continue
                
                if "503" in error_msg or "overloaded" in error_msg.lower():
                    logger.warning(f"⏱️ {instance.name} overloaded, trying next")
                    time.sleep(0.5)
                    continue
                
                if "mime" in error_msg.lower() or "format" in error_msg.lower():
                    logger.warning(f"⚠️ {instance.name} audio format issue, trying next model")
                    continue
                
                if attempts < max_retries:
                    logger.info(f"🔄 Retrying audio transcription with different instance...")
                    time.sleep(0.5)
                    continue
        
        # All instances failed
        logger.error(f"💥 All {len(tried_instances)} audio instances failed!")
        return None
    
    def detect_language(self, text):
        """Detect if text is Hindi/Marathi/English"""
        if any(u'\u0900' <= char <= u'\u097f' for char in text):
            # Devanagari script detected
            marathi_indicators = ['आहे', 'मला', 'तुम्हाला', 'काय', 'कसे', 'कसं', 'पाहिजे', 'होते', 'आहेत']
            hindi_indicators = ['है', 'हैं', 'मुझे', 'आप', 'क्या', 'कैसे', 'चाहिए', 'था', 'थे']
            
            marathi_score = sum(1 for word in marathi_indicators if word in text)
            hindi_score = sum(1 for word in hindi_indicators if word in text)
            
            if marathi_score > hindi_score:
                return 'mr'
            elif hindi_score > 0:
                return 'hi'
            return 'hi'  # Default to Hindi for Devanagari
        return 'en'


# Singleton instance
_multi_audio_service = None


def get_multi_audio_service():
    """Get or create singleton MultiAudioTranscriptionService"""
    global _multi_audio_service
    
    if _multi_audio_service is None:
        _multi_audio_service = MultiAudioTranscriptionService()
        logger.info("🌟 MultiAudioTranscriptionService singleton created")
    else:
        logger.info("♻️ Reusing MultiAudioTranscriptionService singleton")
    
    return _multi_audio_service


# Backward compatibility wrapper
class AudioTranscriptionService:
    """
    Legacy wrapper for backward compatibility
    Delegates to MultiAudioTranscriptionService
    """
    
    def __init__(self):
        self.service = get_multi_audio_service()
    
    def transcribe_audio(self, audio_bytes, mime_type='audio/ogg'):
        """Transcribe audio using multi-service"""
        return self.service.transcribe_audio(audio_bytes, mime_type)
    
    def detect_language(self, text):
        """Detect language"""
        return self.service.detect_language(text)
