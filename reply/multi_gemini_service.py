import google.generativeai as genai
from django.conf import settings
from django.core.cache import cache
import logging
import random
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class GeminiModelConfig:
    """Configuration for each Gemini API + Model combination"""
    def __init__(self, name, api_key, model_id, requests_per_day=50, priority=1):
        self.name = name
        self.api_key = api_key
        self.model_id = model_id
        self.requests_per_day = requests_per_day
        self.priority = priority
        self.failure_count = 0
        
    def get_today_usage(self):
        """Get request count for today"""
        cache_key = f"gemini_{self.name}_daily_count"
        return cache.get(cache_key, 0)
    
    def is_available(self):
        """Check if this model instance is under daily limit"""
        usage = self.get_today_usage()
        # Keep 5 requests buffer
        return usage < (self.requests_per_day - 5)
    
    def record_request(self):
        """Record a successful request"""
        cache_key = f"gemini_{self.name}_daily_count"
        current = cache.get(cache_key, 0)
        # Cache until midnight (86400 seconds = 24 hours)
        import datetime
        now = datetime.datetime.now()
        midnight = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min)
        seconds_until_midnight = int((midnight - now).total_seconds())
        cache.set(cache_key, current + 1, timeout=seconds_until_midnight)
        logger.info(f"📊 {self.name}: {current + 1}/{self.requests_per_day} requests today")
    
    def record_failure(self):
        """Record a failure"""
        self.failure_count += 1
        cache_key = f"gemini_{self.name}_failures"
        cache.set(cache_key, self.failure_count, timeout=300)  # Reset after 5 min


class MultiGeminiService:
    """
    Load balancer for multiple Gemini APIs and Models
    Manages 5 API keys × 5 models = 25 total instances
    """
    
    def __init__(self):
        self.instances = self._initialize_instances()
        self.vector_db = None
        self.vector_chunks = None
        self._load_vector_database()
        logger.info(f"🚀 MultiGeminiService initialized with {len(self.instances)} instances")
    
    def _initialize_instances(self):
        """
        Create all combinations of API keys and models
        5 API keys × 5 models = 25 instances
        """
        instances = []
        
        # Get all API keys from settings
        api_keys = []
        for i in range(1, 6):  # API keys 1-5
            key_name = f'GEMINI_API_KEY_{i}'
            if hasattr(settings, key_name):
                api_keys.append((i, getattr(settings, key_name)))
        
        if not api_keys:
            raise ValueError("❌ No Gemini API keys found! Add GEMINI_API_KEY_1 to GEMINI_API_KEY_5 in settings")
        
        # Define Gemini models (ordered by preference)
        models = [
            # Tier 1: Best models (highest priority)
            {
                'id': 'gemini-2.5-flash', 
                'name': '2.5-flash-exp',
                'priority': 1,
                
            },
            # {
            #     'id': 'gemini-1.5-flash-',
            #     'name': '1.5-flash-002',
            #     'priority': 1,
                
            # },
            # Tier 2: Stable models
            # {
            #     'id': 'gemini-1.5-flash',
            #     'name': '1.5-flash',
            #     'priority': 2,
                
            # },
            # {
            #     'id': 'gemini-1.5-flash-8b',
            #     'name': '1.5-flash-8b',
            #     'priority': 2,
                
            # },
            # Tier 3: Backup models
            # {
            #     'id': 'gemini-pro',
            #     'name': 'pro',
            #     'priority': 3,
                
            # },
        ]
        
        # Create instances for each API key + model combination
        for api_idx, api_key in api_keys:
            for model in models:
                instance_name = f"API{api_idx}-{model['name']}"
                instances.append(GeminiModelConfig(
                    name=instance_name,
                    api_key=api_key,
                    model_id=model['id'],
                    
                    priority=model['priority']
                ))
        
        logger.info(f"✅ Created {len(instances)} Gemini instances:")
        logger.info(f"   📍 {len(api_keys)} API keys × {len(models)} models")
        
        # Show summary
        by_priority = defaultdict(int)
        for inst in instances:
            by_priority[inst.priority] += 1
        logger.info(f"   Priority 1: {by_priority[1]} instances (best)")
        logger.info(f"   Priority 2: {by_priority[2]} instances (stable)")
        logger.info(f"   Priority 3: {by_priority[3]} instances (backup)")
        
        return instances
    
    def _load_vector_database(self):
        """Load vector database for RAG"""
        import os
        import json
        import numpy as np
        
        db_path = os.path.join(settings.BASE_DIR, 'vector_database.json')
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self.vector_chunks = json.load(f)
            
            vectors = np.array([chunk['vector'] for chunk in self.vector_chunks])
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            self.vector_db = vectors / norms
            
            logger.info(f"✅ Loaded {len(self.vector_chunks)} vectors for RAG")
        except Exception as e:
            logger.error(f"❌ Vector DB error: {e}")
            self.vector_chunks = []
            self.vector_db = None
    
    def select_instance(self, query_type="general"):
        """
        Select best available Gemini instance
        Strategy:
        1. Filter by availability (under daily limit)
        2. Sort by priority + failure count
        3. For simple queries, prefer any available
        4. For complex queries, prefer priority 1
        """
        # Get available instances
        available = [inst for inst in self.instances if inst.is_available()]
        
        if not available:
            # All at limit, use least used
            available = sorted(self.instances, key=lambda x: x.get_today_usage())[:5]
            logger.warning(f"⚠️ All instances at limit, trying least used")
        
        # Filter by low failure count
        available = [inst for inst in available if inst.failure_count < 3]
        if not available:
            # Reset failures, try again
            for inst in self.instances:
                inst.failure_count = 0
            available = [inst for inst in self.instances if inst.is_available()][:5]
        
        # Sort by priority, then failure count
        available.sort(key=lambda x: (x.priority, x.failure_count, x.get_today_usage()))
        
        # Query type optimization
        if query_type in ["greeting", "acknowledgment"]:
            # For simple queries, use any available (load balance)
            if len(available) > 5:
                return random.choice(available[:5])
            return available[0] if available else self.instances[0]
        
        elif query_type in ["rag", "labor"]:
            # For complex queries, prefer priority 1 models
            priority_1 = [inst for inst in available if inst.priority == 1]
            if priority_1:
                return priority_1[0]
        
        # Default: return best available
        return available[0] if available else self.instances[0]
    
    def generate_reply(self, system_prompt, user_message, history=None, 
                      query_type="general", max_retries=3):
        """
        Generate response with automatic failover
        """
        history = history or []
        attempts = 0
        tried_instances = set()
        
        while attempts < max_retries:
            # Select best instance
            instance = self.select_instance(query_type)
            
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
            
            logger.info(f"🤖 Attempt {attempts}: {instance.name} (Usage: {instance.get_today_usage()}/{instance.requests_per_day})")
            
            try:
                # Configure API key
                genai.configure(api_key=instance.api_key)
                
                # Create model
                model = genai.GenerativeModel(
                    instance.model_id,
                    system_instruction=system_prompt
                )
                
                # Generate response
                chat = model.start_chat(history=history)
                response = chat.send_message(user_message)
                reply = response.text.strip()
                
                # Record success
                instance.record_request()
                logger.info(f"✅ Success with {instance.name}")
                
                return reply
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ {instance.name} failed: {error_msg[:100]}")
                
                # Record failure
                instance.record_failure()
                
                # Handle specific errors
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning(f"⏱️ {instance.name} quota exceeded, trying next")
                    continue
                
                if "503" in error_msg or "overloaded" in error_msg.lower():
                    logger.warning(f"⏱️ {instance.name} overloaded, trying next")
                    continue
                
                if attempts < max_retries:
                    logger.info(f"🔄 Retrying with different instance...")
                    time.sleep(0.5)  # Brief pause
                    continue
        
        # All instances failed
        logger.error(f"💥 All {len(tried_instances)} instances failed!")
        return "[ESCALATE]"
    

    def analyze_image(self, image_bytes, mime_type, caption="", user_lang='hi', 
                    user_name='User', history=None, max_retries=3):
        """
        Analyze image with Gemini Vision
        Detects crops, diseases, pests, equipment, etc.
        """
        history = history or []
        attempts = 0
        tried_instances = set()
        
        # Create farming-specific vision prompt
        if user_lang == 'hi':
            vision_prompt = f"""तुम {user_name} के लिए एक खेती सलाहकार हो। 

    इस फोटो को देखो और बताओ:
    - क्या फसल है?
    - कोई बीमारी या कीड़ा दिख रहा है?
    - क्या समस्या है?
    - क्या करना चाहिए?

    अगर caption है: "{caption}"

    हिंदी में, छोटे और आसान शब्दों में जवाब दो।
    अगर खेती से related नहीं है, तो कहो: [ESCALATE]
    """
        else:
            vision_prompt = f"""You are a farming advisor for {user_name}.

    Analyze this image and tell:
    - What crop is this?
    - Any disease or pest visible?
    - What's the problem?
    - What should be done?

    If caption provided: "{caption}"

    Respond in simple English.
    If not farming-related, say: [ESCALATE]
    """
        
        while attempts < max_retries:
            # Select best instance (prefer priority 1 for vision)
            instance = self.select_instance("general")
            
            if instance.name in tried_instances and len(tried_instances) < len(self.instances):
                available = [i for i in self.instances 
                        if i.name not in tried_instances and i.is_available()]
                if available:
                    instance = available[0]
                else:
                    break
            
            tried_instances.add(instance.name)
            attempts += 1
            
            logger.info(f"🖼️ Vision Attempt {attempts}: {instance.name}")
            
            try:
                # Configure API key
                genai.configure(api_key=instance.api_key)
                
                # Create model with vision support
                model = genai.GenerativeModel(
                    instance.model_id,
                    system_instruction=vision_prompt
                )
                
                # Prepare image data
                import io
                from PIL import Image
                
                # Convert bytes to PIL Image
                image = Image.open(io.BytesIO(image_bytes))
                
                # Prepare message parts
                parts = []
                if caption:
                    parts.append(f"User's caption: {caption}\n\nAnalyze this image:")
                else:
                    parts.append("Analyze this farming-related image:")
                
                parts.append(image)
                
                # Generate response with history
                if history:
                    chat = model.start_chat(history=history)
                    response = chat.send_message(parts)
                else:
                    response = model.generate_content(parts)
                
                reply = response.text.strip()
                
                # Record success
                instance.record_request()
                logger.info(f"✅ Vision success with {instance.name}")
                
                return reply
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Vision {instance.name} failed: {error_msg[:100]}")
                
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
        
        # All instances failed
        logger.error(f"💥 All vision attempts failed!")
        return "[ESCALATE]"
    def search_knowledge_base(self, query, top_k=3):
        """RAG search using first available instance for embedding"""
        if self.vector_db is None:
            return ""
        
        try:
            # Use first available instance for embedding
            instance = self.select_instance("general")
            genai.configure(api_key=instance.api_key)
            
            # Embed query
            result = genai.embed_content(
                model="text-embedding-004",
                content=query,
                task_type="RETRIEVAL_QUERY"
            )
            
            query_vector = result['embedding']
            query_vector = query_vector / (sum(x**2 for x in query_vector) ** 0.5)
            
            # Cosine similarity
            import numpy as np
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


# Singleton instance
_multi_gemini_service = None

def get_multi_gemini_service():
    """Get or create singleton MultiGeminiService"""
    global _multi_gemini_service
    
    if _multi_gemini_service is None:
        _multi_gemini_service = MultiGeminiService()
        logger.info("🌟 MultiGeminiService singleton created")
    else:
        logger.info("♻️ Reusing MultiGeminiService singleton")
    
    return _multi_gemini_service