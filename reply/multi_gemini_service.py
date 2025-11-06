"""
REDIS-INTEGRATED MULTI GEMINI SERVICE
Shares state across all workers while keeping heavy objects in memory
"""

import google.generativeai as genai
from django.conf import settings
from django.core.cache import cache
import logging
import json
import numpy as np
import os
import re
import random
import time
from collections import defaultdict
import datetime
import hashlib

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# REDIS-BACKED MODEL CONFIG (Shared State Across Workers)
# ═══════════════════════════════════════════════════════════════════

class GeminiModelConfig:
    """
    Configuration for each Gemini API + Model combination
    ✅ NOW USES REDIS FOR SHARED STATE ACROSS ALL WORKERS!
    """
    def __init__(self, name, api_key, model_id, requests_per_day=1500, priority=1):
        self.name = name
        self.api_key = api_key
        self.model_id = model_id
        self.requests_per_day = requests_per_day
        self.priority = priority
        
        # ✅ Redis cache keys (shared across workers)
        self.usage_key = f"gemini_usage_{self.name}"
        self.failure_key = f"gemini_failures_{self.name}"
        self.last_used_key = f"gemini_last_used_{self.name}"
    
    def get_today_usage(self):
        """Get request count for today (from Redis)"""
        return cache.get(self.usage_key, 0)
    
    def is_available(self):
        """Check if this model instance is under daily limit"""
        usage = self.get_today_usage()
        # Keep 5 requests buffer
        return usage < (self.requests_per_day - 5)
    
    def record_request(self):
        """Record a successful request (in Redis)"""
        current = self.get_today_usage()
        
        # Calculate seconds until midnight
        now = datetime.datetime.now()
        midnight = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1), 
            datetime.time.min
        )
        seconds_until_midnight = int((midnight - now).total_seconds())
        
        # ✅ Store in Redis with auto-expire at midnight
        cache.set(self.usage_key, current + 1, timeout=seconds_until_midnight)
        cache.set(self.last_used_key, now.isoformat(), timeout=3600)  # Track last use
        
        logger.info(f"📊 {self.name}: {current + 1}/{self.requests_per_day} requests today")
    
    def record_failure(self):
        """Record a failure (in Redis)"""
        failure_count = cache.get(self.failure_key, 0)
        cache.set(self.failure_key, failure_count + 1, timeout=300)  # Reset after 5 min
        logger.warning(f"⚠️ {self.name}: {failure_count + 1} failures")
    
    def get_failure_count(self):
        """Get failure count from Redis"""
        return cache.get(self.failure_key, 0)


# ═══════════════════════════════════════════════════════════════════
# MULTI GEMINI SERVICE (Worker-Local Objects, Redis State)
# ═══════════════════════════════════════════════════════════════════

class MultiGeminiService:
    """
    Load balancer for multiple Gemini APIs and Models
    ✅ Each worker has its own instance (for heavy objects)
    ✅ Shared state via Redis (for coordination)
    """
    
    def __init__(self):
        # ✅ Worker-specific ID (to track which worker this is)
        self.worker_id = self._generate_worker_id()
        
        logger.info(f"🚀 MultiGeminiService initializing for worker {self.worker_id}")
        
        # ✅ Initialize instances (Redis-backed state)
        self.instances = self._initialize_instances()
        
        # ✅ Load vector database (stays in worker memory)
        self.vector_db = None
        self.vector_chunks = None
        self._load_vector_database()
        
        # ✅ Register this worker in Redis
        self._register_worker()
        
        logger.info(f"✅ Worker {self.worker_id} ready with {len(self.instances)} instances")
    
    def _generate_worker_id(self):
        """Generate unique ID for this worker process"""
        import os
        pid = os.getpid()
        timestamp = datetime.datetime.now().isoformat()
        worker_hash = hashlib.md5(f"{pid}_{timestamp}".encode()).hexdigest()[:8]
        return f"worker_{pid}_{worker_hash}"
    
    def _register_worker(self):
        """Register this worker in Redis for monitoring"""
        workers_key = "gemini_active_workers"
        workers = cache.get(workers_key, [])
        
        if self.worker_id not in workers:
            workers.append(self.worker_id)
            cache.set(workers_key, workers, timeout=3600)  # 1 hour
            logger.info(f"📝 Registered worker {self.worker_id} in Redis")
    
    def _initialize_instances(self):
        """
        Create all combinations of API keys and models
        ✅ 5 API keys × 5 models = 25 instances
        ✅ State stored in Redis, accessible by all workers
        """
        instances = []
        
        # Get all API keys from settings
        api_keys = []
        for i in range(1, 6):  # API keys 1-5
            key_name = f'GEMINI_API_KEY_{i}'
            if hasattr(settings, key_name):
                api_keys.append((i, getattr(settings, key_name)))
        
        if not api_keys:
            raise ValueError("❌ No Gemini API keys found!")
        
        # ✅ Define ALL Gemini models (fixed from your code)
        models = [
            # Tier 1: Best models (highest priority)
            {
                'id': 'gemini-2.0-flash-exp',
                'name': '2.0-flash-exp',
                'priority': 1,
                'requests_per_day': 1500,
            },
            {
                'id': 'gemini-2.5-flash',
                'name': '1.5-flash-002',
                'priority': 1,
                'requests_per_day': 1500,
            },
            
            # Tier 2: Standard models
            {
                'id': 'gemini-1.5-pro',
                'name': '1.5-flash',
                'priority': 2,
                'requests_per_day': 1500,
            },
            {
                'id': 'gemini-1.5-flash',
                'name': '1.5-flash-8b',
                'priority': 2,
                'requests_per_day': 4000,  # Higher limit
            },
            
            # Tier 3: Backup models
            {
                'id': 'gemini-1.5-pro',
                'name': '1.5-pro',
                'priority': 3,
                'requests_per_day': 50,
            },
        ]
        
        # Create instances for each API key + model combination
        for api_idx, api_key in api_keys:
            for model in models:
                instance_name = f"API{api_idx}-{model['name']}"
                instances.append(GeminiModelConfig(
                    name=instance_name,
                    api_key=api_key,
                    model_id=model['id'],
                    requests_per_day=model.get('requests_per_day', 1500),
                    priority=model['priority']
                ))
        
        logger.info(f"✅ Created {len(instances)} Gemini instances (Redis-backed state)")
        logger.info(f"   📍 {len(api_keys)} API keys × {len(models)} models")
        
        # Show summary by priority
        by_priority = defaultdict(int)
        for inst in instances:
            by_priority[inst.priority] += 1
        
        logger.info(f"   Priority 1: {by_priority[1]} instances (best)")
        logger.info(f"   Priority 2: {by_priority[2]} instances (stable)")
        logger.info(f"   Priority 3: {by_priority[3]} instances (backup)")
        
        return instances
    
    def _load_vector_database(self):
        """Load vector database into worker memory (NOT Redis)"""
        db_path = os.path.join(settings.BASE_DIR, 'vector_database.json')
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self.vector_chunks = json.load(f)
            
            vectors = np.array([chunk['vector'] for chunk in self.vector_chunks])
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            self.vector_db = vectors / norms
            
            logger.info(f"✅ Worker {self.worker_id}: Loaded {len(self.vector_chunks)} vectors into memory")
        except FileNotFoundError:
            logger.error(f"❌ vector_database.json not found at {db_path}")
            self.vector_chunks = []
            self.vector_db = None
        except Exception as e:
            logger.error(f"❌ Error loading vectors: {e}")
            self.vector_chunks = []
            self.vector_db = None
    
    def select_instance(self, query_type="general"):
        """
        Select best available Gemini instance
        ✅ Uses Redis state shared across all workers
        """
        # ✅ Get real-time availability from Redis
        available = []
        for inst in self.instances:
            if inst.is_available():  # Checks Redis
                available.append(inst)
        
        if not available:
            # All at limit, use least used
            available = sorted(self.instances, key=lambda x: x.get_today_usage())[:5]
            logger.warning(f"⚠️ Worker {self.worker_id}: All instances at limit, trying least used")
        
        # Filter by low failure count (from Redis)
        available = [inst for inst in available if inst.get_failure_count() < 3]
        if not available:
            # Reset failures, try again
            for inst in self.instances:
                cache.delete(inst.failure_key)
            available = [inst for inst in self.instances if inst.is_available()][:5]
        
        # Sort by priority, then failure count, then usage
        available.sort(key=lambda x: (
            x.priority, 
            x.get_failure_count(),
            x.get_today_usage()
        ))
        
        # Query type optimization
        if query_type in ["greeting", "acknowledgment"]:
            if len(available) > 5:
                return random.choice(available[:5])
            return available[0] if available else self.instances[0]
        
        elif query_type in ["rag", "labor"]:
            priority_1 = [inst for inst in available if inst.priority == 1]
            if priority_1:
                return priority_1[0]
        
        return available[0] if available else self.instances[0]
    
    def generate_reply(self, system_prompt, user_message, history=None, 
                      query_type="general", max_retries=3):
        """
        Generate response with automatic failover
        ✅ Coordinates with other workers via Redis
        """
        history = history or []
        attempts = 0
        tried_instances = set()
        
        while attempts < max_retries:
            instance = self.select_instance(query_type)
            
            if instance.name in tried_instances and len(tried_instances) < len(self.instances):
                available = [i for i in self.instances 
                           if i.name not in tried_instances and i.is_available()]
                if available:
                    instance = available[0]
                else:
                    break
            
            tried_instances.add(instance.name)
            attempts += 1
            
            logger.info(f"🤖 Worker {self.worker_id} - Attempt {attempts}: {instance.name} "
                       f"(Usage: {instance.get_today_usage()}/{instance.requests_per_day})")
            
            try:
                genai.configure(api_key=instance.api_key)
                
                model = genai.GenerativeModel(
                    instance.model_id,
                    system_instruction=system_prompt
                )
                
                chat = model.start_chat(history=history)
                response = chat.send_message(user_message)
                reply = response.text.strip()
                
                # ✅ Record success in Redis
                instance.record_request()
                logger.info(f"✅ Worker {self.worker_id}: Success with {instance.name}")
                
                return reply
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Worker {self.worker_id} - {instance.name} failed: {error_msg[:100]}")
                
                # ✅ Record failure in Redis
                instance.record_failure()
                
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning(f"⏱️ {instance.name} quota exceeded, trying next")
                    continue
                
                if "503" in error_msg or "overloaded" in error_msg.lower():
                    logger.warning(f"⏱️ {instance.name} overloaded, trying next")
                    continue
                
                if attempts < max_retries:
                    logger.info(f"🔄 Retrying with different instance...")
                    time.sleep(0.5)
                    continue
        
        logger.error(f"💥 Worker {self.worker_id}: All {len(tried_instances)} instances failed!")
        return "[ESCALATE]"
    
    def analyze_image(self, image_bytes, mime_type, caption="", user_lang='hi', 
                user_name='User', history=None, max_retries=3):
        """
        Smart image analysis with context awareness
        ✅ NOW WITH REDIS COORDINATION ACROSS WORKERS
        """
        history = history or []
        attempts = 0
        tried_instances = set()
        
        # ✅ FIX 1: Check if user asked a specific question
        has_recent_question = False
        user_question = ""
        
        if history:
            # Check last 2 messages for user questions
            for msg in history[-2:]:
                if msg.get('role') == 'user':
                    content = msg.get('parts', [''])[0]
                    # Check if it's a question or request
                    question_indicators = [
                        'क्या', 'कैसे', 'कौन', 'कब', 'क्यों', 'कितना',  # Hindi
                        'what', 'how', 'when', 'why', 'which', 'can you', 'tell me',  # English
                        'problem', 'issue', 'help', 'समस्या', 'मदद'
                    ]
                    if any(indicator in content.lower() for indicator in question_indicators):
                        has_recent_question = True
                        user_question = content
                        break
        
        # ✅ FIX 2: Check if caption has context
        has_caption_context = bool(caption and len(caption.strip()) > 5)
        
        # ✅ FIX 3: Create context-aware vision prompt
        if user_lang == 'hi':
            if has_recent_question or has_caption_context:
                # User asked something specific - analyze deeply
                vision_prompt = f"""तुम {user_name} के लिए एक खेती सलाहकार हो।

    उपयोगकर्ता ने पूछा: "{user_question or caption}"

    इस फोटो को देखो और उनके सवाल का जवाब दो:
    - अगर फोटो खेती से related है (फसल, पत्ती, कीड़ा, खेत, उपकरण), तो detailed जवाब दो
    - फसल की पहचान करो
    - कोई बीमारी या समस्या दिख रही है?
    - क्या करना चाहिए?

    हिंदी में, छोटे और आसान शब्दों में जवाब दो।
    अगर फोटो सवाल से match नहीं करती, कहो: "यह फोटो आपके सवाल से related नहीं लग रही। कृपया खेती से related फोटो भेजें। 🌾"
    """
            else:
                # No context - ask what they need
                vision_prompt = f"""तुम {user_name} के लिए एक खेती सलाहकार हो।

    इस फोटो को देखो:
    - अगर यह खेती से related है (फसल, पत्ती, बीमारी, कीड़ा, खेत, मिट्टी, उपकरण), तो बस बताओ कि क्या दिख रहा है और पूछो: "इस बारे में आप क्या जानना चाहते हैं?"
    - अगर यह कोई selfie, person, random object, या खेती से बिल्कुल अलग चीज है, तो कहो: "कृपया खेती से related फोटो भेजें जैसे फसल, पत्ती, या खेत। मैं खेती में मदद कर सकता हूँ। 🌾"
    - अगर फोटो blurry या unclear है, कहो: "फोटो साफ नहीं दिख रही। कृपया clear फोटो भेजें। 📸"

    बहुत छोटे में (2-3 lines) जवाब दो।
    """
        else:
            if has_recent_question or has_caption_context:
                # User asked something specific
                vision_prompt = f"""You are a farming advisor for {user_name}.

    User asked: "{user_question or caption}"

    Analyze this image and answer their question:
    - If image is farm-related (crop, leaf, pest, field, equipment), give detailed answer
    - Identify the crop
    - Any disease or problem visible?
    - What should be done?

    Respond in simple English.
    If image doesn't match their question, say: "This image doesn't seem related to your question. Please send a farm-related image. 🌾"
    """
            else:
                # No context - ask what they need
                vision_prompt = f"""You are a farming advisor for {user_name}.

    Look at this image:
    - If it's farm-related (crop, leaf, disease, pest, field, soil, equipment), just tell what you see and ask: "What would you like to know about this?"
    - If it's a selfie, person, random object, or completely unrelated to farming, say: "Please send farm-related images like crops, leaves, or fields. I can help with farming. 🌾"
    - If image is blurry or unclear, say: "Image is not clear. Please send a clearer photo. 📸"

    Keep response very short (2-3 lines).
    """
        
        # ✅ CHANGE 1: Main retry loop with Redis coordination
        while attempts < max_retries:
            # ✅ CHANGE 2: Select instance (uses Redis state)
            instance = self.select_instance("general")
            
            # Avoid retrying same instance
            if instance.name in tried_instances and len(tried_instances) < len(self.instances):
                # ✅ CHANGE 3: Get available instances (checks Redis availability)
                available = [i for i in self.instances 
                        if i.name not in tried_instances and i.is_available()]
                if available:
                    instance = available[0]
                else:
                    break
            
            tried_instances.add(instance.name)
            attempts += 1
            
            # ✅ CHANGE 4: Enhanced logging with worker ID and Redis state
            logger.info(
                f"🖼️ Worker {self.worker_id} - Vision Attempt {attempts}: {instance.name} "
                f"(Usage: {instance.get_today_usage()}/{instance.requests_per_day}, "
                f"Failures: {instance.get_failure_count()})"
            )
            
            try:
                # Configure API key
                genai.configure(api_key=instance.api_key)
                
                # Create model with vision prompt
                model = genai.GenerativeModel(
                    instance.model_id,
                    system_instruction=vision_prompt
                )
                
                # Prepare image
                import io
                from PIL import Image
                
                image = Image.open(io.BytesIO(image_bytes))
                
                # Prepare message
                parts = ["Analyze this image:", image]
                
                # Generate response
                if history:
                    chat = model.start_chat(history=history)
                    response = chat.send_message(parts)
                else:
                    response = model.generate_content(parts)
                
                reply = response.text.strip()
                
                # ✅ CHANGE 5: Record success in Redis
                instance.record_request()
                logger.info(f"✅ Worker {self.worker_id}: Vision success with {instance.name}")
                
                return reply
            
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"❌ Worker {self.worker_id} - Vision {instance.name} failed: "
                    f"{error_msg[:100]}"
                )
                
                # ✅ CHANGE 6: Record failure in Redis (visible to all workers)
                instance.record_failure()
                
                # Handle quota exceeded
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning(
                        f"⏱️ Worker {self.worker_id}: {instance.name} quota exceeded "
                        f"({instance.get_today_usage()}/{instance.requests_per_day}), trying next"
                    )
                    continue
                
                # Handle service overloaded
                if "503" in error_msg or "overloaded" in error_msg.lower():
                    logger.warning(
                        f"⏱️ Worker {self.worker_id}: {instance.name} overloaded, trying next"
                    )
                    continue
                
                # Retry with different instance
                if attempts < max_retries:
                    logger.info(f"🔄 Worker {self.worker_id}: Retrying with different instance...")
                    time.sleep(0.5)
                    continue
        
        # All attempts failed
        logger.error(
            f"💥 Worker {self.worker_id}: All vision attempts failed! "
            f"Tried {len(tried_instances)} instances"
        )
        return "[ESCALATE]"

    def search_knowledge_base(self, query, top_k=3):
        """
        RAG search using vector database (stays in worker memory)
        ✅ Vector DB is NOT in Redis (too large)
        ✅ Each worker has its own copy in memory
        """
        if self.vector_db is None:
            return ""
        
        try:
            # Use first available instance for embedding
            instance = self.select_instance("general")
            genai.configure(api_key=instance.api_key)
            
            result = genai.embed_content(
                model="text-embedding-004",
                content=query,
                task_type="RETRIEVAL_QUERY"
            )
            
            query_vector = result['embedding']
            query_vector = query_vector / (sum(x**2 for x in query_vector) ** 0.5)
            
            query_vec = np.array(query_vector)
            scores = np.dot(self.vector_db, query_vec)
            top_indices = np.argsort(scores)[-top_k:][::-1]
            
            context = ""
            for i in top_indices:
                chunk = self.vector_chunks[i]
                context += f"📄 {chunk['source']}: {chunk['content'][:200]}...\n---\n"
            
            return context
        
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return ""


# ═══════════════════════════════════════════════════════════════════
# SINGLETON GETTER (Each Worker Gets Its Own Instance)
# ═══════════════════════════════════════════════════════════════════

_multi_gemini_service = None  # Worker-local singleton

def get_multi_gemini_service():
    """
    Get or create MultiGeminiService for this worker
    ✅ Each worker has its own instance (for heavy objects)
    ✅ All workers share state via Redis (for coordination)
    """
    global _multi_gemini_service
    
    if _multi_gemini_service is None:
        _multi_gemini_service = MultiGeminiService()
        logger.info("🌟 MultiGeminiService created for this worker")
    else:
        logger.info("♻️ Reusing MultiGeminiService for this worker")
    
    return _multi_gemini_service


# ═══════════════════════════════════════════════════════════════════
# REDIS MONITORING UTILITIES
# ═══════════════════════════════════════════════════════════════════

def get_global_statistics():
    """
    Get statistics across all workers (from Redis)
    Useful for monitoring dashboard
    """
    service = get_multi_gemini_service()
    
    stats = {
        'total_instances': len(service.instances),
        'active_workers': len(cache.get('gemini_active_workers', [])),
        'instance_usage': {},
        'instance_failures': {},
    }
    
    for inst in service.instances:
        stats['instance_usage'][inst.name] = {
            'used': inst.get_today_usage(),
            'limit': inst.requests_per_day,
            'available': inst.is_available(),
        }
        stats['instance_failures'][inst.name] = inst.get_failure_count()
    
    return stats
# import google.generativeai as genai
# from django.conf import settings
# from django.core.cache import cache
# import logging
# import random
# import time
# from collections import defaultdict

# logger = logging.getLogger(__name__)


# class GeminiModelConfig:
#     """Configuration for each Gemini API + Model combination"""
#     def __init__(self, name, api_key, model_id, requests_per_day=50, priority=1):
#         self.name = name
#         self.api_key = api_key
#         self.model_id = model_id
#         self.requests_per_day = requests_per_day
#         self.priority = priority
#         self.failure_count = 0
        
#     def get_today_usage(self):
#         """Get request count for today"""
#         cache_key = f"gemini_{self.name}_daily_count"
#         return cache.get(cache_key, 0)
    
#     def is_available(self):
#         """Check if this model instance is under daily limit"""
#         usage = self.get_today_usage()
#         # Keep 5 requests buffer
#         return usage < (self.requests_per_day - 5)
    
#     def record_request(self):
#         """Record a successful request"""
#         cache_key = f"gemini_{self.name}_daily_count"
#         current = cache.get(cache_key, 0)
#         # Cache until midnight (86400 seconds = 24 hours)
#         import datetime
#         now = datetime.datetime.now()
#         midnight = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min)
#         seconds_until_midnight = int((midnight - now).total_seconds())
#         cache.set(cache_key, current + 1, timeout=seconds_until_midnight)
#         logger.info(f"📊 {self.name}: {current + 1}/{self.requests_per_day} requests today")
    
#     def record_failure(self):
#         """Record a failure"""
#         self.failure_count += 1
#         cache_key = f"gemini_{self.name}_failures"
#         cache.set(cache_key, self.failure_count, timeout=300)  # Reset after 5 min


# class MultiGeminiService:
#     """
#     Load balancer for multiple Gemini APIs and Models
#     Manages 5 API keys × 5 models = 25 total instances
#     """
    
#     def __init__(self):
#         self.instances = self._initialize_instances()
#         self.vector_db = None
#         self.vector_chunks = None
#         self._load_vector_database()
#         logger.info(f"🚀 MultiGeminiService initialized with {len(self.instances)} instances")
    
#     def _initialize_instances(self):
#         """
#         Create all combinations of API keys and models
#         5 API keys × 5 models = 25 instances
#         """
#         instances = []
        
#         # Get all API keys from settings
#         api_keys = []
#         for i in range(1, 6):  # API keys 1-5
#             key_name = f'GEMINI_API_KEY_{i}'
#             if hasattr(settings, key_name):
#                 api_keys.append((i, getattr(settings, key_name)))
        
#         if not api_keys:
#             raise ValueError("❌ No Gemini API keys found! Add GEMINI_API_KEY_1 to GEMINI_API_KEY_5 in settings")
        
#         # Define Gemini models (ordered by preference)
#         models = [
#             # Tier 1: Best models (highest priority)
#             {
#                 'id': 'gemini-2.5-flash', 
#                 'name': '2.5-flash-exp',
#                 'priority': 1,
                
#             },
#             # {
#             #     'id': 'gemini-1.5-flash-',
#             #     'name': '1.5-flash-002',
#             #     'priority': 1,
                
#             # },
#             # Tier 2: Stable models
#             # {
#             #     'id': 'gemini-1.5-flash',
#             #     'name': '1.5-flash',
#             #     'priority': 2,
                
#             # },
#             # {
#             #     'id': 'gemini-1.5-flash-8b',
#             #     'name': '1.5-flash-8b',
#             #     'priority': 2,
                
#             # },
#             # Tier 3: Backup models
#             # {
#             #     'id': 'gemini-pro',
#             #     'name': 'pro',
#             #     'priority': 3,
                
#             # },
#         ]
        
#         # Create instances for each API key + model combination
#         for api_idx, api_key in api_keys:
#             for model in models:
#                 instance_name = f"API{api_idx}-{model['name']}"
#                 instances.append(GeminiModelConfig(
#                     name=instance_name,
#                     api_key=api_key,
#                     model_id=model['id'],
                    
#                     priority=model['priority']
#                 ))
        
#         logger.info(f"✅ Created {len(instances)} Gemini instances:")
#         logger.info(f"   📍 {len(api_keys)} API keys × {len(models)} models")
        
#         # Show summary
#         by_priority = defaultdict(int)
#         for inst in instances:
#             by_priority[inst.priority] += 1
#         logger.info(f"   Priority 1: {by_priority[1]} instances (best)")
#         logger.info(f"   Priority 2: {by_priority[2]} instances (stable)")
#         logger.info(f"   Priority 3: {by_priority[3]} instances (backup)")
        
#         return instances
    
#     def _load_vector_database(self):
#         """Load vector database for RAG"""
#         import os
#         import json
#         import numpy as np
        
#         db_path = os.path.join(settings.BASE_DIR, 'vector_database.json')
#         try:
#             with open(db_path, 'r', encoding='utf-8') as f:
#                 self.vector_chunks = json.load(f)
            
#             vectors = np.array([chunk['vector'] for chunk in self.vector_chunks])
#             norms = np.linalg.norm(vectors, axis=1, keepdims=True)
#             self.vector_db = vectors / norms
            
#             logger.info(f"✅ Loaded {len(self.vector_chunks)} vectors for RAG")
#         except Exception as e:
#             logger.error(f"❌ Vector DB error: {e}")
#             self.vector_chunks = []
#             self.vector_db = None
    
#     def select_instance(self, query_type="general"):
#         """
#         Select best available Gemini instance
#         Strategy:
#         1. Filter by availability (under daily limit)
#         2. Sort by priority + failure count
#         3. For simple queries, prefer any available
#         4. For complex queries, prefer priority 1
#         """
#         # Get available instances
#         available = [inst for inst in self.instances if inst.is_available()]
        
#         if not available:
#             # All at limit, use least used
#             available = sorted(self.instances, key=lambda x: x.get_today_usage())[:5]
#             logger.warning(f"⚠️ All instances at limit, trying least used")
        
#         # Filter by low failure count
#         available = [inst for inst in available if inst.failure_count < 3]
#         if not available:
#             # Reset failures, try again
#             for inst in self.instances:
#                 inst.failure_count = 0
#             available = [inst for inst in self.instances if inst.is_available()][:5]
        
#         # Sort by priority, then failure count
#         available.sort(key=lambda x: (x.priority, x.failure_count, x.get_today_usage()))
        
#         # Query type optimization
#         if query_type in ["greeting", "acknowledgment"]:
#             # For simple queries, use any available (load balance)
#             if len(available) > 5:
#                 return random.choice(available[:5])
#             return available[0] if available else self.instances[0]
        
#         elif query_type in ["rag", "labor"]:
#             # For complex queries, prefer priority 1 models
#             priority_1 = [inst for inst in available if inst.priority == 1]
#             if priority_1:
#                 return priority_1[0]
        
#         # Default: return best available
#         return available[0] if available else self.instances[0]
    
#     def generate_reply(self, system_prompt, user_message, history=None, 
#                       query_type="general", max_retries=3):
#         """
#         Generate response with automatic failover
#         """
#         history = history or []
#         attempts = 0
#         tried_instances = set()
        
#         while attempts < max_retries:
#             # Select best instance
#             instance = self.select_instance(query_type)
            
#             # Avoid retrying same instance
#             if instance.name in tried_instances and len(tried_instances) < len(self.instances):
#                 available = [i for i in self.instances 
#                            if i.name not in tried_instances and i.is_available()]
#                 if available:
#                     instance = available[0]
#                 else:
#                     break
            
#             tried_instances.add(instance.name)
#             attempts += 1
            
#             logger.info(f"🤖 Attempt {attempts}: {instance.name} (Usage: {instance.get_today_usage()}/{instance.requests_per_day})")
            
#             try:
#                 # Configure API key
#                 genai.configure(api_key=instance.api_key)
                
#                 # Create model
#                 model = genai.GenerativeModel(
#                     instance.model_id,
#                     system_instruction=system_prompt
#                 )
                
#                 # Generate response
#                 chat = model.start_chat(history=history)
#                 response = chat.send_message(user_message)
#                 reply = response.text.strip()
                
#                 # Record success
#                 instance.record_request()
#                 logger.info(f"✅ Success with {instance.name}")
                
#                 return reply
            
#             except Exception as e:
#                 error_msg = str(e)
#                 logger.error(f"❌ {instance.name} failed: {error_msg[:100]}")
                
#                 # Record failure
#                 instance.record_failure()
                
#                 # Handle specific errors
#                 if "429" in error_msg or "quota" in error_msg.lower():
#                     logger.warning(f"⏱️ {instance.name} quota exceeded, trying next")
#                     continue
                
#                 if "503" in error_msg or "overloaded" in error_msg.lower():
#                     logger.warning(f"⏱️ {instance.name} overloaded, trying next")
#                     continue
                
#                 if attempts < max_retries:
#                     logger.info(f"🔄 Retrying with different instance...")
#                     time.sleep(0.5)  # Brief pause
#                     continue
        
#         # All instances failed
#         logger.error(f"💥 All {len(tried_instances)} instances failed!")
#         return "[ESCALATE]"
    

#     def analyze_image(self, image_bytes, mime_type, caption="", user_lang='hi', 
#                     user_name='User', history=None, max_retries=3):
#         """
#         Smart image analysis with context awareness
#         """
#         history = history or []
#         attempts = 0
#         tried_instances = set()
        
#         # ✅ FIX 1: Check if user asked a specific question
#         has_recent_question = False
#         user_question = ""
        
#         if history:
#             # Check last 2 messages for user questions
#             for msg in history[-2:]:
#                 if msg.get('role') == 'user':
#                     content = msg.get('parts', [''])[0]
#                     # Check if it's a question or request
#                     question_indicators = [
#                         'क्या', 'कैसे', 'कौन', 'कब', 'क्यों', 'कितना',  # Hindi
#                         'what', 'how', 'when', 'why', 'which', 'can you', 'tell me',  # English
#                         'problem', 'issue', 'help', 'समस्या', 'मदद'
#                     ]
#                     if any(indicator in content.lower() for indicator in question_indicators):
#                         has_recent_question = True
#                         user_question = content
#                         break
        
#         # ✅ FIX 2: Check if caption has context
#         has_caption_context = bool(caption and len(caption.strip()) > 5)
        
#         # ✅ FIX 3: Create context-aware vision prompt
#         if user_lang == 'hi':
#             if has_recent_question or has_caption_context:
#                 # User asked something specific - analyze deeply
#                 vision_prompt = f"""तुम {user_name} के लिए एक खेती सलाहकार हो।

#     उपयोगकर्ता ने पूछा: "{user_question or caption}"

#     इस फोटो को देखो और उनके सवाल का जवाब दो:
#     - अगर फोटो खेती से related है (फसल, पत्ती, कीड़ा, खेत, उपकरण), तो detailed जवाब दो
#     - फसल की पहचान करो
#     - कोई बीमारी या समस्या दिख रही है?
#     - क्या करना चाहिए?

#     हिंदी में, छोटे और आसान शब्दों में जवाब दो।
#     अगर फोटो सवाल से match नहीं करती, कहो: "यह फोटो आपके सवाल से related नहीं लग रही। कृपया खेती से related फोटो भेजें। 🌾"
#     """
#             else:
#                 # No context - ask what they need
#                 vision_prompt = f"""तुम {user_name} के लिए एक खेती सलाहकार हो।

#     इस फोटो को देखो:
#     - अगर यह खेती से related है (फसल, पत्ती, बीमारी, कीड़ा, खेत, मिट्टी, उपकरण), तो बस बताओ कि क्या दिख रहा है और पूछो: "इस बारे में आप क्या जानना चाहते हैं?"
#     - अगर यह कोई selfie, person, random object, या खेती से बिल्कुल अलग चीज है, तो कहो: "कृपया खेती से related फोटो भेजें जैसे फसल, पत्ती, या खेत। मैं खेती में मदद कर सकता हूँ। 🌾"
#     - अगर फोटो blurry या unclear है, कहो: "फोटो साफ नहीं दिख रही। कृपया clear फोटो भेजें। 📸"

#     बहुत छोटे में (2-3 lines) जवाब दो।
#     """
#         else:
#             if has_recent_question or has_caption_context:
#                 # User asked something specific
#                 vision_prompt = f"""You are a farming advisor for {user_name}.

#     User asked: "{user_question or caption}"

#     Analyze this image and answer their question:
#     - If image is farm-related (crop, leaf, pest, field, equipment), give detailed answer
#     - Identify the crop
#     - Any disease or problem visible?
#     - What should be done?

#     Respond in simple English.
#     If image doesn't match their question, say: "This image doesn't seem related to your question. Please send a farm-related image. 🌾"
#     """
#             else:
#                 # No context - ask what they need
#                 vision_prompt = f"""You are a farming advisor for {user_name}.

#     Look at this image:
#     - If it's farm-related (crop, leaf, disease, pest, field, soil, equipment), just tell what you see and ask: "What would you like to know about this?"
#     - If it's a selfie, person, random object, or completely unrelated to farming, say: "Please send farm-related images like crops, leaves, or fields. I can help with farming. 🌾"
#     - If image is blurry or unclear, say: "Image is not clear. Please send a clearer photo. 📸"

#     Keep response very short (2-3 lines).
#     """
        
#         while attempts < max_retries:
#             instance = self.select_instance("general")
            
#             if instance.name in tried_instances and len(tried_instances) < len(self.instances):
#                 available = [i for i in self.instances 
#                         if i.name not in tried_instances and i.is_available()]
#                 if available:
#                     instance = available[0]
#                 else:
#                     break
            
#             tried_instances.add(instance.name)
#             attempts += 1
            
#             logger.info(f"🖼️ Vision Attempt {attempts}: {instance.name}")
            
#             try:
#                 genai.configure(api_key=instance.api_key)
                
#                 model = genai.GenerativeModel(
#                     instance.model_id,
#                     system_instruction=vision_prompt
#                 )
                
#                 # Prepare image
#                 import io
#                 from PIL import Image
                
#                 image = Image.open(io.BytesIO(image_bytes))
                
#                 # Prepare message
#                 parts = ["Analyze this image:", image]
                
#                 # Generate response
#                 if history:
#                     chat = model.start_chat(history=history)
#                     response = chat.send_message(parts)
#                 else:
#                     response = model.generate_content(parts)
                
#                 reply = response.text.strip()
                
#                 instance.record_request()
#                 logger.info(f"✅ Vision success with {instance.name}")
                
#                 return reply
            
#             except Exception as e:
#                 error_msg = str(e)
#                 logger.error(f"❌ Vision {instance.name} failed: {error_msg[:100]}")
                
#                 instance.record_failure()
                
#                 if "429" in error_msg or "quota" in error_msg.lower():
#                     logger.warning(f"⏱️ {instance.name} quota exceeded, trying next")
#                     continue
                
#                 if "503" in error_msg or "overloaded" in error_msg.lower():
#                     logger.warning(f"⏱️ {instance.name} overloaded, trying next")
#                     continue
                
#                 if attempts < max_retries:
#                     logger.info(f"🔄 Retrying with different instance...")
#                     time.sleep(0.5)
#                     continue
        
#         logger.error(f"💥 All vision attempts failed!")
#         return "[ESCALATE]"
        
#     def search_knowledge_base(self, query, top_k=3):
#         """RAG search using first available instance for embedding"""
#         if self.vector_db is None:
#             return ""
        
#         try:
#             # Use first available instance for embedding
#             instance = self.select_instance("general")
#             genai.configure(api_key=instance.api_key)
            
#             # Embed query
#             result = genai.embed_content(
#                 model="text-embedding-004",
#                 content=query,
#                 task_type="RETRIEVAL_QUERY"
#             )
            
#             query_vector = result['embedding']
#             query_vector = query_vector / (sum(x**2 for x in query_vector) ** 0.5)
            
#             # Cosine similarity
#             import numpy as np
#             query_vec = np.array(query_vector)
#             scores = np.dot(self.vector_db, query_vec)
#             top_indices = np.argsort(scores)[-top_k:][::-1]
            
#             context = ""
#             for i in top_indices:
#                 chunk = self.vector_chunks[i]
#                 context += f"📄 {chunk['source']}: {chunk['content'][:200]}...\n---\n"
            
#             return context
        
#         except Exception as e:
#             logger.error(f"RAG search error: {e}")
#             return ""


# # Singleton instance
# _multi_gemini_service = None

# def get_multi_gemini_service():
#     """Get or create singleton MultiGeminiService"""
#     global _multi_gemini_service
    
#     if _multi_gemini_service is None:
#         _multi_gemini_service = MultiGeminiService()
#         logger.info("🌟 MultiGeminiService singleton created")
#     else:
#         logger.info("♻️ Reusing MultiGeminiService singleton")
    
#     return _multi_gemini_service