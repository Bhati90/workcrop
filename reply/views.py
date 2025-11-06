import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.files.base import ContentFile
import requests
import os
import tempfile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import re
from dateutil import parser

from .models import WhatsAppUser, Conversation, Message, MediaFile, WebhookLog, WhatsAppTemplate
from .service import WhatsAppService

logger = logging.getLogger(__name__)
from .multi_gemini_service import get_multi_gemini_service
from .gemini_service import SYSTEM_PROMPT

from .location import extract_location_from_conversation

@require_http_methods(["POST"])
def add_contact_api(request):
    """Add a new contact/user"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        phone_number = data.get('phone_number', '').strip()
        name = data.get('name', '').strip()
        
        if not phone_number or not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Phone number and name are required'
            }, status=400)
        
        # Create or get user
        whatsapp_user, created = WhatsAppUser.objects.get_or_create(
            phone_number=phone_number,
            defaults={'name': name}
        )
        
        if not created:
            # Update name if user already exists
            whatsapp_user.name = name
            whatsapp_user.save()
        
        # Create conversation if doesn't exist
        conversation, _ = Conversation.objects.get_or_create(
            whatsapp_user=whatsapp_user
        )
        
        return JsonResponse({
            'status': 'success',
            'user_id': whatsapp_user.id,
            'message': 'Contact added successfully'
        })
        
    except Exception as e:
        logger.error(f"Add contact error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)



logger = logging.getLogger(__name__)


@csrf_exempt
def whatsapp_webhook(request):
    """
    Handles incoming WhatsApp messages and status updates.
    No verification needed - centralized webhook routes data here.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"====== INCOMING WEBHOOK ======\n{json.dumps(data, indent=2)}")
            
            # Log webhook for debugging
            WebhookLog.objects.create(payload=data)
            
            # Process webhook data
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # --- PROCESS INCOMING MESSAGES ---
                    if 'messages' in value:
                        process_incoming_messages(value, data)
                    
                    # --- PROCESS STATUS UPDATES ---
                    if 'statuses' in value:
                        process_status_updates(value)
            
            return JsonResponse({"status": "success"}, status=200)
            
        except Exception as e:
            logger.error(f"Error in webhook: {e}", exc_info=True)
            WebhookLog.objects.create(
                payload={"error": str(e)},
                error=str(e)
            )
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    # If GET request (shouldn't happen with centralized webhook)
    return JsonResponse({"status": "success"}, status=200)

# Add at the top:
from .gemini_service import GeminiService
from django.utils import timezone

SPAM_KEYWORDS = ['xxx', 'joke', 'random', 'movie', 'cricket']  # Expand as needed

ESCALATE_KEYWORDS = ['help', 'urgent', 'complaint', 'problem', 'error']
# Add this at the TOP of webhooks.py (after imports)
from django.core.cache import cache
from .gemini_service import GeminiService
import logging

logger = logging.getLogger(__name__)

# Cache key for singleton
GEMINI_SERVICE_CACHE_KEY = 'gemini_service_singleton'

def get_gemini_service():
    """
    Returns cached GeminiService instance (survives across requests/processes)
    """
    # Try to get from cache first
    gemini = cache.get(GEMINI_SERVICE_CACHE_KEY)
    
    if gemini is None:
        # Create new instance
        gemini = GeminiService()
        # Cache it forever (or until server restart)
        cache.set(GEMINI_SERVICE_CACHE_KEY, gemini, timeout=None)
        logger.info("🚀 Created NEW single GeminiService and cached it")
    else:
        logger.info("♻️ Reusing CACHED single GeminiService instance")
    
    return gemini


def process_incoming_messages(value, full_webhook_data):
    """
    Handles processing logic for all incoming messages.
    """
    messages = value.get('messages', [])
    contacts = value.get('contacts', [])
    
    if not messages:
        return
        
    msg_data = messages[0]
    
    try:
        from_number = msg_data['from']
        message_type = msg_data.get('type')
        whatsapp_message_id = msg_data['id']
        timestamp = timezone.datetime.fromtimestamp(int(msg_data['timestamp']))

        # --- 1. Get or Create User & Conversation ---
        profile_name = contacts[0].get('profile', {}).get('name', from_number)
        whatsapp_user, _ = WhatsAppUser.objects.get_or_create(
            phone_number=from_number,
            defaults={'name': profile_name}
        )
        conversation, _ = Conversation.objects.get_or_create(
            whatsapp_user=whatsapp_user
        )

        # --- 2. Check for 24-Hour Escalation Block ---
        if whatsapp_user.is_blocked and whatsapp_user.blocked_until and whatsapp_user.blocked_until > timezone.now():
            logger.info(f"User {from_number} is in 24-hour escalation block. Ignoring message.")
            _save_incoming_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            return
        elif whatsapp_user.is_blocked:
            whatsapp_user.is_blocked = False
            whatsapp_user.blocked_until = None
            whatsapp_user.save()


        if message_type == 'image':
            handle_image_with_ai(msg_data, conversation, whatsapp_user, from_number, timestamp, whatsapp_message_id)
            return
        
        # --- 6.5. Handle LOCATION (AI Response) ---
        if message_type == 'location':
            handle_location_with_ai(msg_data, conversation, whatsapp_user, from_number, timestamp, whatsapp_message_id)
            return
        
        if message_type == 'audio':
            # ✅ FIX: Check for duplicate audio BEFORE processing
            audio_data = msg_data.get('audio', {})
            audio_id = audio_data.get('id')
            
            # Check if this audio was already processed
            existing_audio = Message.objects.filter(
                media_id=audio_id,
                message_type='audio'
            ).first()
            
            if existing_audio:
                logger.warning(f"⚠️ Audio {audio_id} already processed (duplicate webhook). Skipping.")
                return  # Exit immediately - don't process
            
            # Process audio only if it's new
            handle_audio_transcription(msg_data, conversation, whatsapp_user, from_number, timestamp)
            return
        
        # --- 3. Save the Incoming Message to DB ---
        msg_obj = _save_incoming_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
        
        if not msg_obj:
            return

        # --- 4. Send "Read" Receipt ---
        WhatsAppService().mark_message_as_read(whatsapp_message_id)

        # --- 5. We ONLY respond to 'text' messages with AI ---
         # --- 5. Handle REACTIONS (Emoji responses) ---
        if message_type == 'reaction':
            handle_reaction_response(msg_data, conversation, whatsapp_user, from_number)
            return

        # --- 6. Handle STICKERS (Fun responses) ---
        if message_type == 'sticker':
            handle_sticker_response(conversation, whatsapp_user, from_number)
            return
        
        

        # --- 7. Handle IMAGE/VIDEO/DOCUMENT (Polite decline) ---
        # --- 7. Handle IMAGE (AI Vision Analysis) ---
        

        # --- 8. Handle VIDEO/DOCUMENT (Polite decline) ---
        if message_type in ['video', 'document']:
            handle_media_not_supported(message_type, from_number, conversation, whatsapp_user)
            return

        # --- 8. Handle AUDIO (Transcription + AI Response) ---

        # --- 6. Prepare data for Gemini ---
        txt = msg_data.get('text', {}).get('body', '').strip()
        if not txt:
            logger.info("Ignoring empty text message.")
            return

        # Detect language from text
        def detect_language(text):
            if any(u'\u0900' <= char <= u'\u097f' for char in text):
                marathi_words = ['आहे', 'मला', 'तुम्हाला', 'पाहिजे', 'माझा']
                if any(word in text.lower() for word in marathi_words):
                    return 'mr'
                return 'hi'
            return 'en'

        detected_lang = detect_language(txt)

        # Save user's language preference
        if whatsapp_user.preferred_language != detected_lang:
            whatsapp_user.preferred_language = detected_lang
            whatsapp_user.save()

        user_lang = whatsapp_user.preferred_language
        user_name = whatsapp_user.name

        logger.info(f"🗣️ User language: {user_lang}")

        # --- 7. Gather History ---
        history = []
        qs = conversation.messages.filter(timestamp__lt=timestamp).order_by('-timestamp')[:10]
        
        for m in reversed(qs):
            if m.message_type not in ('document'):
                role = 'user' if m.direction == 'inbound' else 'model'
                content = m.text_content or m.caption or f'[{m.message_type}]'
                history.append({"role": role, "parts": [content]})
        
        # --- 8. Get CACHED GeminiService instance ---
        ai_service = get_multi_gemini_service()
        
        # Format system prompt
        formatted_prompt = SYSTEM_PROMPT.format(
            user_lang=user_lang,
            user_name=user_name
        )
        query_type = "general"
        txt_lower = txt.lower()
        if any(kw in txt_lower for kw in ['hello', 'hi', 'namaste', 'नमस्ते']):
            query_type = "greeting"
        elif any(kw in txt_lower for kw in ['ok', 'thanks', 'धन्यवाद', 'ठीक']):
            query_type = "acknowledgment"
        elif any(kw in txt_lower for kw in ['labor', 'majur', 'मजूर', 'worker']):
            query_type = "labor"
        elif any(kw in txt_lower for kw in ['spray', 'फवारणी', 'crop', 'फसल']):
            query_type = "rag"
        # --- 9. Handle quota errors gracefully ---
        try:
            reply = ai_service.generate_reply(system_prompt=formatted_prompt,
                user_message=txt,
                history=history,
                query_type=query_type)
            log_inquiry_details(
            txt, 
            reply, 
            whatsapp_user, 
            conversation, 
            user_lang
        )
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a quota error
            if '429' in error_msg or 'quota' in error_msg.lower():
                logger.error(f"🚫 QUOTA EXCEEDED: {error_msg}")
                
                # Send friendly message to user
                quota_msg = (
                    "क्षमा करें, अभी सिस्टम व्यस्त है। कृपया थोड़ी देर बाद try करें। 🙏"
                    if user_lang == 'hi' else
                    "Sorry, system is busy right now. Please try again in a few minutes. 🙏"
                )
                WhatsAppService().send_text_message(from_number, quota_msg, conversation)
                return
            else:
                # Other errors, escalate
                logger.error(f"❌ Gemini error: {error_msg}")
                reply = "[ESCALATE]"

        # --- 10. Process Gemini's Decision ---
        if reply == "[IGNORE]":
            logger.info(f"Gemini classified as [IGNORE]. No reply sent to {from_number}.")
            return

        if reply == "[ESCALATE]":
            logger.warning(f"⚠️ ESCALATE triggered for: '{txt}' from {from_number}")
            
            recent_redirects = conversation.messages.filter(
                direction='outbound',
                text_content__contains='सिर्फ खेती और मजूर'
            ).count()
            
            recent_escalations = conversation.messages.filter(
                direction='outbound',
                text_content__contains='Our team will reach you soon'
            ).count()
            
            # First strike: Polite redirect
            if recent_redirects == 0 and recent_escalations == 0:
                redirect_msg = (
                    "मैं सिर्फ खेती और मजूर की मदद कर सकता हूँ 🌾 क्या कोई खेती से related सवाल है?"
                    if user_lang == 'hi' else
                    "I can only help with farming and labor 🌾 Any farming-related questions?"
                )
                WhatsAppService().send_text_message(from_number, redirect_msg, conversation)
                logger.info(f"↩️ First escalation - sent redirect message")
            
            # Second strike: Block
            elif recent_redirects >= 100 or recent_escalations >= 100:
                escalation_msg = (
                    "हमारी टीम जल्द ही आपसे संपर्क करेगी।" 
                    if user_lang == 'hi' else 
                    "Our team will reach you soon."
                )
                WhatsAppService().send_text_message(from_number, escalation_msg, conversation)
                
                whatsapp_user.is_blocked = True
                whatsapp_user.blocked_until = timezone.now() + timezone.timedelta(hours=24)
                whatsapp_user.save()
                logger.warning(f"🚫 User {from_number} blocked for 24 hours")
            
            return

        # --- 11. Send the Gemini Reply ---
        # --- 11. Send the Gemini Reply ---
        # --- 11. Send the Gemini Reply ---
        if reply:
            # ✅ FIX: Remove any "Silent thinking process" or internal reasoning
            clean_reply = reply
            
            # Remove silent thinking/reasoning patterns
            patterns_to_remove = [
                r"Silent thinking process:.*?(?=\n[^\*]|\n\n|$)",  # Remove thinking blocks
                r"\*Initial thought.*?\*",  # Remove initial thoughts
                r"\*Refinement.*?\*",  # Remove refinements
                r"\*Final.*?\*",  # Remove final checks
                r"^\d+\.\s+\*\*.*?\*\*.*?(?=\n\d+\.|\n\n|$)",  # Remove numbered thinking steps
            ]
            
            import re
            for pattern in patterns_to_remove:
                clean_reply = re.sub(pattern, '', clean_reply, flags=re.DOTALL | re.MULTILINE)
            
            # Remove extra whitespace
            clean_reply = '\n'.join(line.strip() for line in clean_reply.split('\n') if line.strip())
            clean_reply = clean_reply.strip()
            
            if not clean_reply:
                logger.error("Reply became empty after cleaning!")
                clean_reply = "माफ करा, कृपया पुन्हा विचारा। 🙏" if user_lang in ['hi', 'mr'] else "Sorry, please ask again. 🙏"
            
            logger.info(f"📤 Sending cleaned reply: {clean_reply[:100]}...")
            
            sent_msg = WhatsAppService().send_text_message(from_number, clean_reply, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
        else:
            logger.error("Gemini returned empty reply.")
            fallback_msg = (
                "हमारी टीम जल्द ही आपसे संपर्क करेगी।" 
                if user_lang == 'hi' else 
                "Our team will reach you soon."
            )
            sent_msg = WhatsAppService().send_text_message(from_number, fallback_msg, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
    except Exception as e:
        logger.error(f"CRITICAL Error: {str(e)}", exc_info=True)

def handle_image_with_ai(msg_data, conversation, whatsapp_user, from_number, timestamp, whatsapp_message_id):
    """
    Handle image messages + AI Vision Analysis
    Downloads image → Analyzes with Gemini Vision → Responds
    """
    try:
        # Save image message first
        msg_obj = handle_image_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
        
        if not msg_obj:
            logger.error("Failed to save image message")
            return
        
        if not msg_obj.media_url:
            logger.warning(f"⚠️ Image {media_id} saved to DB but media_url is empty, may still be downloading")
        else:
            logger.info(f"✅ Image available at: {msg_obj.media_url}")
        
        image_data = msg_data.get('image', {})
        media_id = image_data.get('id')
        caption = image_data.get('caption', '').strip()
        
        logger.info(f"🖼️ Processing image {media_id} with AI vision...")
        
        # Download image from WhatsApp
        whatsapp_service = WhatsAppService()
        image_bytes, mime_type = whatsapp_service.download_media(media_id)
        
        if not image_bytes:
            logger.error("Failed to download image")
            error_msg = (
                "माफ़ करें, फोटो देखने में समस्या हुई। कृपया फिर से भेजें। 🙏"
                if whatsapp_user.name else
                "Sorry, couldn't process image. Please try again. 🙏"
            )
            sent_msg = WhatsAppService().send_text_message(from_number, error_msg, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
            return
        
        # Detect user language from history
        recent_msg = conversation.messages.filter(
            direction='inbound',
            message_type='text'
        ).order_by('-timestamp').first()
        
        user_lang = 'hi'
        if recent_msg and recent_msg.text_content:
            if any(u'\u0900' <= char <= u'\u097f' for char in recent_msg.text_content):
                user_lang = 'hi'
            else:
                user_lang = 'en'
        
        user_name = whatsapp_user.name
        
        # Get conversation history
        history = []
        qs = conversation.messages.filter(timestamp__lt=timestamp).order_by('-timestamp')[:10]
        
        for m in reversed(qs):
            if m.message_type in ('text', 'audio'):
                role = 'user' if m.direction == 'inbound' else 'model'
                content = m.text_content or f'[{m.message_type}]'
                content = content.replace('[AUDIO] ', '')
                history.append({"role": role, "parts": [content]})
        
        # Analyze image with Gemini Vision
        ai_service = get_multi_gemini_service()
        reply = ai_service.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            caption=caption,
            user_lang=user_lang,
            user_name=user_name,
            history=history
        )
        
        # Log inquiry
        image_query = f"[IMAGE] {caption}" if caption else "[IMAGE]"
        log_inquiry_details(image_query, reply, whatsapp_user, conversation, user_lang)
        
        # Handle response
        # Handle response
        if reply == "[IGNORE]":
            logger.info("AI classified image as [IGNORE]")
            return

        # ✅ Don't escalate on image - AI will handle the conversation
        if reply == "[ESCALATE]":
            # For images, send a polite redirect instead of escalating
            polite_msg = (
                "मुझे इस फोटो को समझने में दिक्कत हो रही है। क्या आप बता सकते हैं कि आप क्या जानना चाहते हैं? या खेती से related कोई और फोटो भेज सकते हैं? 🌾"
                if user_lang == 'hi' else 
                "I'm having trouble understanding this image. Can you tell me what you'd like to know? Or send another farm-related image? 🌾"
            )
            sent_msg = WhatsAppService().send_text_message(from_number, polite_msg, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
            return

        # Send AI response
        if reply:
            sent_msg = WhatsAppService().send_text_message(from_number, reply, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
            logger.info(f"✅ AI responded to image")
        
        
        else:
            logger.error("Gemini returned empty reply for image")
            fallback_msg = (
                "हमारी टीम जल्द ही आपसे संपर्क करेगी।" 
                if user_lang == 'hi' else 
                " i cant understand it. Our team will reach you soon. "
            )
            sent_msg = WhatsAppService().send_text_message(from_number, fallback_msg, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
        
    except Exception as e:
        logger.error(f"❌ Error processing image with AI: {str(e)}", exc_info=True)
        error_msg = "Sorry, image processing failed. Please send text."
        sent_msg = WhatsAppService().send_text_message(from_number, error_msg, conversation)
        if sent_msg:
            sent_msg.is_ai_generated = True
            sent_msg.save()

def log_inquiry_details(user_message, bot_reply, whatsapp_user, conversation, language):
    """
    Smart logger - extracts and stores inquiry details in ANY language
    """
    from .models import ServiceInquiry, UnknownQuery
    import re
    
    # Skip very short messages
    if len(user_message.strip()) < 3:
        return
    
    msg_lower = user_message.lower()
    
    # ✅ FIX: Map language codes to full names
    language_map = {
        'en': 'english',
        'hi': 'hindi',
        'mr': 'marathi',
        'mixed': 'mixed',
        'english': 'english',
        'hindi': 'hindi',
        'marathi': 'marathi',
    }
    service_lang = language_map.get(language, 'mixed')
    
    # Detect service type (multilingual keywords)
    service_keywords = {
        'labor': ['labor', 'labour', 'majur', 'मजूर', 'मजदूर', 'kamgar', 'कामगार', 'worker', 'काम'],
        'spray': ['spray', 'फवारणी', 'spraying', 'छिडकाव'],
        'fertilizer': ['fertilizer', 'खाद', 'खत'],
        'disease': ['disease', 'रोग', 'बीमारी', 'problem'],
        'equipment': ['equipment', 'machine', 'यंत्र', 'मशीन'],
        'transport': ['transport', 'वाहतूक', 'vehicle'],
        'storage': ['storage', 'साठवण', 'भंडारण'],
        'price': ['price', 'rate', 'किंमत', 'दर', 'cost'],
    }
    
    detected_services = []
    for service, keywords in service_keywords.items():
        if any(kw in msg_lower for kw in keywords):
            detected_services.append(service)
    
    # ========== CHECK IF UNKNOWN QUERY ==========
    is_escalated = '[escalate]' in str(bot_reply).lower()
    is_unknown_service = not detected_services and is_escalated
    
    # If completely unknown, log to UnknownQuery table
    if is_unknown_service:
        log_unknown_query(user_message, bot_reply, whatsapp_user, service_lang)
        return
    
    # ========== EXTRACT ALL FIELDS ==========
    
    # 1. CUSTOMER NAME EXTRACTION
    customer_name = extract_customer_name(user_message, conversation)
    
    # 2. FARM SIZE EXTRACTION
    farm_size = extract_farm_size(user_message)
    
    # 3. CROP TYPE & VARIETY
    crop_type, crop_variety = extract_crop_info(user_message)
    
    # 4. QUANTITY EXTRACTION
    quantity = extract_quantity(user_message)
    
    # 5. DATE EXTRACTION
    requested_date = extract_date(user_message, service_lang)
    
    # 6. LOCATION EXTRACTION (your existing function)
    detected_location = extract_location_from_conversation(user_message, conversation)
    
    # 7. URGENCY DETECTION
    urgent_keywords = ['urgent', 'तुरंत', 'आज', 'today', 'अभी', 'now', 'जल्दी', 'emergency']
    is_urgent = any(kw in msg_lower for kw in urgent_keywords)
    
    # 8. PRICE REQUEST DETECTION
    asked_price = any(kw in msg_lower for kw in ['price', 'rate', 'किंमत', 'दर', 'रेट', 'cost', 'charges'])
    
    # 9. QUOTED PRICE (from bot reply)
    customer_quoted_price = extract_customer_quoted_price(user_message, conversation)
    
    
    try:
        ai_response_truncated = str(bot_reply)[:500] if bot_reply else ''
        
        ServiceInquiry.objects.create(
            whatsapp_user=whatsapp_user,
            conversation=conversation,
            
            # Customer details
            customer_name_in_chat=customer_name,
            
            # Service details
            service_type=', '.join(detected_services) if detected_services else 'general',
            service_description=user_message[:500],
            service_language=service_lang,
            
            # Quantity & specifications
            quantity_needed=quantity,
            farm_size=farm_size,
            crop_type=crop_type,
            crop_variety=crop_variety,
            
            # Location & timing
            location_mentioned=detected_location,
            requested_date=requested_date,
            
            # Status & priority
            urgency='high' if is_urgent else 'medium',
            status='new' if not is_escalated else 'reviewing',
            
            # Pricing
            requested_price_info=asked_price,
            quoted_price=customer_quoted_price,
            
            # Tracking
            original_query=user_message[:1000],
            ai_response=ai_response_truncated,
            needs_human_review=is_escalated,
        )
        
        logger.info(f"✅ Logged inquiry: {', '.join(detected_services) if detected_services else 'general'}")
         
    except Exception as e:
        logger.error(f"❌ Error logging ServiceInquiry: {str(e)}")
        # Don't crash the webhook if logging fails

# ========== HELPER FUNCTIONS FOR EXTRACTION ==========

def extract_customer_name(user_message, conversation):
    """
    Extract customer name from:
    1. "My name is X" patterns
    2. Conversation history
    3. User profile
    """
    # Pattern 1: Direct name mentions
    name_patterns = [
        r'(?:my name is|i am|मेरा नाम|नाव|मी)\s+([A-Za-zऀ-ॿ]+)',
        r'(?:call me|you can call me)\s+([A-Za-z]+)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
    
    # Pattern 2: Check conversation history
    try:
        name_msg = conversation.messages.filter(
            direction='inbound',
            message_type='text'
        ).order_by('-timestamp')[:10]
        
        for msg in name_msg:
            if msg.text_content:
                for pattern in name_patterns:
                    match = re.search(pattern, msg.text_content, re.IGNORECASE)
                    if match:
                        return match.group(1).strip().title()
    except:
        pass
    
    return None


def extract_farm_size(text):
    """
    Extract farm size like "35 acre", "2 हेक्टर", "50 एकर"
    """
    if not text:
        return None
    
    # Patterns for farm size
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:acre|एकर|acres)',
        r'(\d+(?:\.\d+)?)\s*(?:hectare|हेक्टर|hectares)',
        r'(\d+(?:\.\d+)?)\s*(?:bigha|बीघा)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            size = match.group(1)
            unit = match.group(0).split()[-1] if len(match.group(0).split()) > 1 else 'acre'
            return f"{size} {unit}"
    
    return None


def extract_crop_info(text):
    """
    Extract crop type and variety
    Returns: (crop_type, crop_variety)
    """
    if not text:
        return None, None
    
    text_lower = text.lower()
    
    # Common crops (multilingual)
    crops = {
        'grapes': ['grape', 'grapes', 'द्राक्ष', 'अंगूर', 'draksh'],
        'pomegranate': ['pomegranate', 'dalimb', 'डाळिंब', 'अनार'],
        'onion': ['onion', 'कांदा', 'pyaj'],
        'tomato': ['tomato', 'टमाटर'],
        'wheat': ['wheat', 'गहू', 'gehun'],
        'rice': ['rice', 'तांदूळ', 'chawal'],
        'sugarcane': ['sugarcane', 'ऊस', 'गन्ना'],
    }
    
    crop_type = None
    for crop_name, keywords in crops.items():
        if any(kw in text_lower for kw in keywords):
            crop_type = crop_name
            break
    
    # Extract variety (usually capital letters or numbers)
    variety_pattern = r'(?:variety|वॅरायटी)?\s*([A-Z]{2,}[-\s]?\d*|Thompson|Sonaka|ARD\s*\d+)'
    variety_match = re.search(variety_pattern, text, re.IGNORECASE)
    crop_variety = variety_match.group(1).strip() if variety_match else None
    
    return crop_type, crop_variety


def extract_quantity(text):
    """
    Extract quantities like "35 workers", "50 tons", "10 acres"
    """
    if not text:
        return None
    
    # Look for number + unit patterns
    patterns = [
        r'(\d+)\s*(?:worker|workers|majur|मजूर|मजदूर|people)',
        r'(\d+)\s*(?:ton|tons|kg|quintals|क्विंटल)',
        r'(\d+)\s*(?:acre|एकर|hectare|हेक्टर)',
        r'(\d+)\s*(?:days|दिवस|week|आठवडा)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    # Fallback: just extract first number if present
    numbers = re.findall(r'\d+', text)
    if numbers:
        return numbers[0]
    
    return None


def extract_date(text, language='mixed'):
    """
    Extract dates from multilingual text using dateutil and patterns
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Relative dates (Hindi/Marathi/English)
    relative_dates = {
        'today': ['today', 'आज', 'aaj'],
        'tomorrow': ['tomorrow', 'कल', 'kal', 'उद्या'],
        'day after tomorrow': ['परवा', 'parso'],
        'next week': ['next week', 'पुढच्या आठवड्यात', 'अगले हफ्ते'],
        'this month': ['this month', 'या महिन्यात', 'इस महीने'],
        'day':['23th','2','2june']
    }
    
    for date_type, keywords in relative_dates.items():
        if any(kw in text_lower for kw in keywords):
            return date_type
    
    # Try to parse specific dates using dateutil
    try:
        # Extract potential date strings
        date_patterns = [
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',  # 05-12-2025
            r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}',  # 5 Dec 2025
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(0)
                try:
                    parsed_date = parser.parse(date_str, fuzzy=True)
                    return parsed_date.strftime('%Y-%m-%d')
                except:
                    return date_str
    except Exception as e:
        logger.error(f"Date parsing error: {e}")
    
    return None

def extract_customer_quoted_price(user_message, conversation):
    """
    Extract the price CUSTOMER is offering to pay from their messages
    NOT from bot replies (since you never share prices)
    
    Examples:
    - "I will pay 500 per labour per day"
    - "मैं 600 रुपये दूंगा"
    - "My rate is 10000"
    - "₹450 per day"
    """
    if not user_message:
        return None
    
    text_lower = user_message.lower()
    
    # Keywords indicating customer is stating their price
    price_indicators = [
        'i will pay', 'i can pay', 'मैं दूंगा', 'मैं देंगे',
        'my rate', 'मेरा रेट', 'हम देंगे', 'हमारा रेट',
        'i offer', 'मैं ऑफर', 'we pay', 'हम देते',
        'my budget', 'मेरा बजट'
    ]
    
    has_price_indicator = any(indicator in text_lower for indicator in price_indicators)
    
    # ========== EXTRACTION PATTERNS ==========
    
    # Pattern 1: Price with currency symbol
    # "₹500 per labour", "₹600/day", "Rs. 450 per worker"
    currency_patterns = [
        r'₹\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:per|/|प्रति)?\s*(?:labour|labor|day|दिन|मजूर|worker|acre|एकर)?',
        r'rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:per|/|प्रति)?\s*(?:labour|labor|day|दिन|मजूर|worker|acre|एकर)?',
        r'(\d+)\s*(?:rupees|रुपये|rupaiya)\s*(?:per|/|प्रति)?\s*(?:labour|labor|day|दिन|मजूर|worker|acre|एकर)?',
    ]
    
    for pattern in currency_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            amount = match.group(1).replace(',', '')
            
            # Determine unit from context
            unit = determine_price_unit(user_message)
            
            return f"₹{amount}{unit}"
    
    # Pattern 2: Direct number with context (only if price indicators present)
    # "I will pay 500 per labour", "मैं 600 दूंगा per day"
    if has_price_indicator:
        number_pattern = r'(\d+)\s*(?:per|/|प्रति)\s*(labour|labor|day|दिन|मजूर|worker|acre|एकर|hour|घंटा)'
        match = re.search(number_pattern, user_message, re.IGNORECASE)
        if match:
            amount = match.group(1)
            unit_raw = match.group(2)
            
            # Standardize unit
            unit_map = {
                'labour': '/labour', 'labor': '/labour', 'मजूर': '/labour',
                'worker': '/labour', 'day': '/day', 'दिन': '/day',
                'acre': '/acre', 'एकर': '/acre', 'hour': '/hour', 'घंटा': '/hour'
            }
            unit = unit_map.get(unit_raw.lower(), f'/{unit_raw}')
            
            return f"₹{amount}{unit}"
    
    # Pattern 3: Range prices (e.g., "5000-6000", "500 से 600")
    if has_price_indicator:
        range_pattern = r'(\d+)\s*(?:to|-|से)\s*(\d+)'
        match = re.search(range_pattern, user_message, re.IGNORECASE)
        if match:
            min_amount = match.group(1)
            max_amount = match.group(2)
            unit = determine_price_unit(user_message)
            return f"₹{min_amount}-{max_amount}{unit}"
    
    # Pattern 4: Simple number after price indicator
    # "My rate is 500"
    if has_price_indicator:
        simple_number = r'(?:rate|रेट|pay|दूंगा|देंगे)\s+(\d+)'
        match = re.search(simple_number, user_message, re.IGNORECASE)
        if match:
            amount = match.group(1)
            unit = determine_price_unit(user_message)
            return f"₹{amount}{unit}"
    
    # ========== CHECK CONVERSATION HISTORY ==========
    # Look back 3-5 messages for price mentions
    try:
        recent_msgs = conversation.messages.filter(
            direction='inbound',
            message_type='text'
        ).order_by('-timestamp')[:5]
        
        for msg in recent_msgs:
            if msg.text_content and msg.text_content != user_message:
                price = extract_customer_quoted_price(msg.text_content, None)
                if price:
                    return price
    except:
        pass
    
    return None


def determine_price_unit(text):
    """
    Determine the pricing unit from context
    Returns: "/labour", "/day", "/acre", etc.
    """
    text_lower = text.lower()
    
    # Check for specific units
    if any(word in text_lower for word in ['per labour', 'per worker', 'per majur', 'प्रति मजूर']):
        return '/labour'
    elif any(word in text_lower for word in ['per day', 'daily', 'per दिन', 'प्रति दिन', 'रोज']):
        return '/day'
    elif any(word in text_lower for word in ['per acre', 'per एकर', 'प्रति एकर']):
        return '/acre'
    elif any(word in text_lower for word in ['per hour', 'hourly', 'per घंटा', 'प्रति घंटा']):
        return '/hour'
    elif any(word in text_lower for word in ['total', 'overall', 'कुल']):
        return ' total'
    
    # Default
    return ''


# ========== UNKNOWN QUERY LOGGER ==========

def log_unknown_query(user_message, bot_reply, whatsapp_user, language):
    """
    Log queries we don't understand or can't serve
    For future service expansion
    """
    from .models import UnknownQuery
    
    msg_lower = user_message.lower()
    
    # Determine reason
    reason = 'unclear_request'
    potential_service = None
    
    # Check if it's a language issue
    if language in ['mixed', 'unknown']:
        reason = 'language_issue'
    
    # Check if location not covered
    elif 'not available' in str(bot_reply).lower() or 'don\'t operate' in str(bot_reply).lower():
        reason = 'unknown_area'
        
    # Try to guess what service they might want
    service_hints = {
        'packaging': ['pack', 'packaging', 'पॅकिंग'],
        'cold_storage': ['cold storage', 'थंड साठा'],
        'insurance': ['insurance', 'विमा'],
        'loan': ['loan', 'कर्ज'],
        
    }
    
    for service, keywords in service_hints.items():
        if any(kw in msg_lower for kw in keywords):
            potential_service = service
            reason = 'unknown_service'
            break
    
    # Check for duplicates (increment count if exists)
    try:
        existing = UnknownQuery.objects.filter(
            whatsapp_user=whatsapp_user,
            query_text__icontains=user_message[:50]
        ).first()
        
        if existing:
            existing.similar_queries_count += 1
            existing.save()
            logger.info(f"📊 Incremented unknown query count: {existing.similar_queries_count}")
        else:
            UnknownQuery.objects.create(
                whatsapp_user=whatsapp_user,
                query_text=user_message[:1000],
                query_language=language,
                reason=reason,
                potential_service=potential_service,
                similar_queries_count=1
            )
            logger.info(f"❓ Logged unknown query: {reason}")
    
    except Exception as e:
        logger.error(f"❌ Error logging UnknownQuery: {str(e)}")

def _save_incoming_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """
    Internal helper to route incoming message to the correct handler for saving.
    """
    message_type = msg_data.get('type')
    
    # Check if message already exists (webhook retry)
    if Message.objects.filter(whatsapp_message_id=whatsapp_message_id).exists():
        logger.warning(f"Duplicate message received: {whatsapp_message_id}. Ignoring.")
        return None

    handler_map = {
        'text': handle_text_message,
        'image': handle_image_message,
        'video': handle_video_message,
        'audio': handle_audio_message,
        'sticker': handle_sticker_message,    # ✅ ADD THIS
        'reaction': handle_reaction_message,
        'document': handle_document_message,
        'location': handle_location_message,
        'button': handle_button_message,
        'interactive': handle_interactive_message,
    }
    
    handler = handler_map.get(message_type)
    
    if handler:
        return handler(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
    else:
        logger.warning(f"Unhandled message type: {message_type}")
        # Save as a generic 'text' message to log it
        return handle_unknown_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
    

def handle_audio_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle incoming audio/voice messages"""
    try:
        audio_data = msg_data.get('audio', {})
        audio_id = audio_data.get('id')
        mime_type = audio_data.get('mime_type', 'audio/ogg')
        
        # Save message to DB first
        msg_obj = Message.objects.create(
            conversation=conversation,
            whatsapp_message_id=whatsapp_message_id,
            message_type='audio',
            direction='inbound',
            media_id=audio_id,
            mime_type=mime_type,
            timestamp=timestamp,
            status='delivered'
        )
        download_and_save_media(msg_obj, audio_id)
        # Update conversation preview
        conversation.last_message_preview = "[AUDIO]"
        conversation.unread_count += 1
        conversation.save()
        
        whatsapp_user.last_message_at = timestamp
        whatsapp_user.save()
        
        logger.info(f"🎤 Audio message received from {whatsapp_user.phone_number}")
        return msg_obj
        
    except Exception as e:
        logger.error(f"Error handling audio: {str(e)}")
        return None


def handle_sticker_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle incoming stickers"""
    try:
        sticker_data = msg_data.get('sticker', {})
        sticker_id = sticker_data.get('id')
        mime_type = sticker_data.get('mime_type', 'image/webp')
        
        msg_obj = Message.objects.create(
            conversation=conversation,
            whatsapp_message_id=whatsapp_message_id,
            message_type='sticker',
            direction='inbound',
            media_id=sticker_id,
            mime_type=mime_type,
            timestamp=timestamp,
            status='delivered'
        )
        
        conversation.last_message_preview = "[STICKER]"
        conversation.unread_count += 1
        conversation.save()
        
        whatsapp_user.last_message_at = timestamp
        whatsapp_user.save()
        
        logger.info(f"😀 Sticker received from {whatsapp_user.phone_number}")
        return msg_obj
        
    except Exception as e:
        logger.error(f"Error handling sticker: {str(e)}")
        return None


def handle_reaction_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle message reactions"""
    try:
        reaction_data = msg_data.get('reaction', {})
        emoji = reaction_data.get('emoji', '👍')
        message_id = reaction_data.get('message_id')
        
        msg_obj = Message.objects.create(
            conversation=conversation,
            whatsapp_message_id=whatsapp_message_id,
            message_type='reaction',
            direction='inbound',
            text_content=emoji,
            timestamp=timestamp,
            status='delivered'
        )
        
        logger.info(f"❤️ Reaction {emoji} received from {whatsapp_user.phone_number}")
        return msg_obj
        
    except Exception as e:
        logger.error(f"Error handling reaction: {str(e)}")
        return None
    
    
def handle_text_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle text messages - FIXED"""
    text_content = msg_data.get('text', {}).get('body', '')
    
    # FIX: Only create the message ONCE
    msg_obj = create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        text_content, None, None, None, 'delivered', timestamp
    )
    
    # Update conversation/user for preview
    conversation.last_message_preview = text_content[:]
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()
    
    logger.info(f"Text message: '{text_content}' from {whatsapp_user.phone_number}")
    return msg_obj # Return the created object

def handle_image_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle image messages - FIXED to ensure download"""
    image_data = msg_data.get('image', {})
    media_id = image_data.get('id')
    mime_type = image_data.get('mime_type')
    caption = image_data.get('caption', '')
    
    logger.info(f"🖼️ Image message from {whatsapp_user.phone_number}, media_id: {media_id}")
    
    # Create message first
    message = create_message(
        conversation, whatsapp_message_id, 'image', 'inbound',
        None, media_id, mime_type, caption, 'delivered', timestamp
    )
    
    # ✅ CRITICAL: Download and save media SYNCHRONOUSLY (not async)
    # This ensures the image is saved before AI processes it
    download_and_save_media(message, media_id)
    
    # Refresh message to get updated media_url
    message.refresh_from_db()
    
    # Update preview
    preview = "[IMAGE]"
    if caption:
        preview += f" {caption[:50]}"
    conversation.last_message_preview = preview
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()
    
    logger.info(f"✅ Image saved: {message.media_url}")
    
    return message

def handle_video_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle video messages"""
    video_data = msg_data.get('video', {})
    media_id = video_data.get('id')
    mime_type = video_data.get('mime_type')
    caption = video_data.get('caption', '')
    
    logger.info(f"Video message from {whatsapp_user.phone_number}, media_id: {media_id}")
    
    message = create_message(
        conversation, whatsapp_message_id, 'video', 'inbound',
        None, media_id, mime_type, caption, 'delivered', timestamp
    )
    
    download_and_save_media(message, media_id)
    
    preview = "[VIDEO]"
    if caption:
        preview += f" {caption[:50]}"
    conversation.last_message_preview = preview
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()

# Add at the top
from .audio import AudioTranscriptionService

def handle_audio_transcription(msg_data, conversation, whatsapp_user, from_number, timestamp):
    """
    Download audio → Transcribe → Process like text message
    """
    try:
        audio_data = msg_data.get('audio', {})
        audio_id = audio_data.get('id')
        mime_type = audio_data.get('mime_type', 'audio/ogg')
        
        # ✅ CRITICAL: Save message to DB IMMEDIATELY to prevent duplicates
        msg_obj = Message.objects.create(
            conversation=conversation,
            whatsapp_message_id=msg_data.get('id'),
            message_type='audio',
            direction='inbound',
            media_id=audio_id,
            mime_type=mime_type,
            timestamp=timestamp,
            status='delivered'
        )
        
        logger.info(f"✅ Audio message saved to DB: {audio_id}")
        
        # Download audio from WhatsApp
        logger.info(f"🎤 Downloading audio {audio_id}...")
        audio_bytes, mime_type = WhatsAppService().download_media(audio_id)
        
        if not audio_bytes:
            logger.error("Failed to download audio")
            error_msg = (
                "माफ़ करें, ऑडियो सुनने में समस्या हुई। कृपया फिर से भेजें। 🙏"
                if 'hi' in str(whatsapp_user.name) else
                "Sorry, couldn't process audio. Please try again. 🙏"
            )
            WhatsAppService().send_text_message(from_number, error_msg, conversation)
            return
        
        # Transcribe audio
        logger.info(f"🎧 Transcribing audio...")
        transcription_service = AudioTranscriptionService()
        transcription = transcription_service.transcribe_audio(audio_bytes, mime_type)
        
        if not transcription:
            logger.error("Transcription failed")
            error_msg = (
                "माफ़ करें, ऑडियो समझने में समस्या हुई। कृपया text में लिखें। 🙏"
                if 'hi' in str(whatsapp_user.name) else
                "Sorry, couldn't understand audio. Please send text. 🙏"
            )
            WhatsAppService().send_text_message(from_number, error_msg, conversation)
            return
        
        logger.info(f"✅ Transcribed: {transcription[:100]}...")
        
        # Update message with transcription
        msg_obj.text_content = f"[AUDIO] {transcription}"
        msg_obj.save()
        
        # Detect language
        user_lang = transcription_service.detect_language(transcription)
        user_name = whatsapp_user.name
        
        # Gather history (exclude media)
        history = []
        qs = conversation.messages.filter(timestamp__lt=timestamp).order_by('-timestamp')[:10]
        
        for m in reversed(qs):
            if m.message_type in ('text', 'audio'):
                role = 'user' if m.direction == 'inbound' else 'model'
                content = m.text_content or f'[{m.message_type}]'
                # Remove [AUDIO] prefix for history
                content = content.replace('[AUDIO] ', '')
                history.append({"role": role, "parts": [content]})
        
        # Process like normal text message
        ai_service = get_multi_gemini_service()
        formatted_prompt = SYSTEM_PROMPT.format(
            user_lang=user_lang,
            user_name=user_name
        )
        
        query_type = "general"
        txt_lower = transcription.lower()
        if any(kw in txt_lower for kw in ['hello', 'hi', 'namaste', 'नमस्ते']):
            query_type = "greeting"
        elif any(kw in txt_lower for kw in ['ok', 'thanks', 'धन्यवाद']):
            query_type = "acknowledgment"
        elif any(kw in txt_lower for kw in ['labor', 'majur', 'मजूर']):
            query_type = "labor"
        elif any(kw in txt_lower for kw in ['spray', 'फवारणी']):
            query_type = "rag"
        
        # Generate AI response
        try:
            reply = ai_service.generate_reply(
                system_prompt=formatted_prompt,
                user_message=transcription,
                history=history,
                query_type=query_type
            )
            log_inquiry_details(transcription, reply, whatsapp_user, conversation, user_lang)
        except Exception as e:
            logger.error(f"AI error on audio: {str(e)}")
            reply = "[ESCALATE]"
        
        # Handle response (same logic as text)
        if reply == "[IGNORE]":
            return
        
        if reply == "[ESCALATE]":
            escalation_msg = (
                "हमारी टीम जल्द ही आपसे संपर्क करेगी।" 
                if user_lang == 'hi' else 
                "Our team will reach you soon."
            )
            WhatsAppService().send_text_message(from_number, escalation_msg, conversation)
            return
        
        if reply:
            sent_msg = WhatsAppService().send_text_message(from_number, reply, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True  # ✅ Mark as AI
                sent_msg.save()
    except Exception as e:
        logger.error(f"Audio handling error: {str(e)}", exc_info=True)
        error_msg = "Sorry, audio processing failed. Please send text."
        WhatsAppService().send_text_message(from_number, error_msg, conversation)


def handle_media_not_supported(media_type, from_number, conversation, whatsapp_user):
    """
    Politely inform user we only support text/audio
    """
    # Detect user's preferred language from history
    last_msg = conversation.messages.filter(
        direction='inbound',
        message_type='text'
    ).order_by('-timestamp').first()
    
    user_lang = 'en'
    if last_msg and last_msg.text_content:
        if any(u'\u0900' <= char <= u'\u097f' for char in last_msg.text_content):
            user_lang = 'hi'
    
    media_type_names = {
        'image': ('फोटो', 'Photo'),
        'video': ('वीडियो', 'Video'),
        'document': ('डॉक्यूमेंट', 'Document/PDF')
    }
    
    media_name = media_type_names.get(media_type, ('Media', 'Media'))
    
    if user_lang == 'hi':
        message = f"""धन्यवाद {media_name[0]} भेजने के लिए! 📎

मैं अभी सिर्फ:
✅ टेक्स्ट मैसेज
✅ ऑडियो/वॉइस मैसेज

इन्हें समझ सकता हूँ। कृपया अपना सवाल टेक्स्ट या ऑडियो में भेजें। 🙏

खेती और मजूर के बारे में कुछ भी पूछें! 🌾"""
    else:
        message = f"""Thank you for sending {media_name[1]}! 📎

I currently understand only:
✅ Text messages
✅ Audio/Voice messages

Please send your question as text or audio. 🙏

Ask me anything about farming and labor! 🌾"""
    
    sent_msg = WhatsAppService().send_text_message(from_number, message, conversation)
    if sent_msg:
        sent_msg.is_ai_generated = True
        sent_msg.save()
    logger.info(f"📎 Sent 'media not supported' message for {media_type}")


def handle_sticker_response(conversation, whatsapp_user, from_number):
    """
    Fun response to stickers based on conversation context
    """
    import random
    
    # Check recent conversation tone
    recent_msgs = conversation.messages.filter(
        direction='inbound',
        message_type='text'
    ).order_by('-timestamp')[:3]
    
    user_lang = 'en'
    if recent_msgs.exists():
        last_text = recent_msgs.first().text_content or ''
        if any(u'\u0900' <= char <= u'\u097f' for char in last_text):
            user_lang = 'hi'
    
    responses_hi = [
        "😊 स्टीकर अच्छा है! कोई खेती का सवाल? 🌾",
        "👍 बढ़िया! मजूर या फसल के बारे में कुछ पूछना है? 👨‍🌾",
        "😄 मस्त! खेती में कैसे मदद करूं? 🍇"
    ]
    
    responses_en = [
        "😊 Nice sticker! Any farming questions? 🌾",
        "👍 Great! Need help with labor or crops? 👨‍🌾",
        "😄 Cool! How can I help with farming? 🍇"
    ]
    
    response = random.choice(responses_hi if user_lang == 'hi' else responses_en)
    sent_msg = WhatsAppService().send_text_message(from_number, response, conversation)
    if sent_msg:
        sent_msg.is_ai_generated = True
        sent_msg.save()
    logger.info(f"😀 Sent sticker response")


def handle_reaction_response(msg_data, conversation, whatsapp_user, from_number):
    """
    Smart emoji reaction responses
    """
    import random
    
    reaction_data = msg_data.get('reaction', {})
    emoji = reaction_data.get('emoji', '👍')
    
    # Detect language from recent messages
    recent_msg = conversation.messages.filter(
        direction='inbound',
        message_type='text'
    ).order_by('-timestamp').first()
    
    user_lang = 'en'
    if recent_msg and recent_msg.text_content:
        if any(u'\u0900' <= char <= u'\u097f' for char in recent_msg.text_content):
            user_lang = 'hi'
    
    # Map emojis to responses
    emoji_responses = {
        '❤️': {
            'hi': ["धन्यवाद! ❤️ खेती में और कैसे मदद करूं? 🌾", "बहुत अच्छा! ❤️ कोई और सवाल? 👨‍🌾"],
            'en': ["Thank you! ❤️ How else can I help? 🌾", "Glad to help! ❤️ Any other questions? 👨‍🌾"]
        },
        '👍': {
            'hi': ["बढ़िया! 👍 कुछ और चाहिए? 🌾", "शानदार! 👍 और मदद? 🍇"],
            'en': ["Great! 👍 Anything else? 🌾", "Perfect! 👍 Need more help? 🍇"]
        },
        '🙏': {
            'hi': ["स्वागत है! 🙏 हमेशा यहाँ हैं 🌾", "कोई बात नहीं! 🙏 फिर पूछिएगा 👨‍🌾"],
            'en': ["Welcome! 🙏 Always here to help 🌾", "No problem! 🙏 Ask anytime 👨‍🌾"]
        },
        '😊': {
            'hi': ["😊 खुशी हुई मदद करके! कुछ और? 🌾", "😊 बहुत बढ़िया! और सवाल? 🍇"],
            'en': ["😊 Happy to help! Anything else? 🌾", "😊 Glad you're satisfied! More questions? 🍇"]
        }
    }
    
    # Get response for emoji (or default)
    responses = emoji_responses.get(emoji, emoji_responses['👍'])
    response = random.choice(responses[user_lang])
    
    sent_msg = WhatsAppService().send_text_message(from_number, response, conversation)
    if sent_msg:
        sent_msg.is_ai_generated = True
        sent_msg.save()
    logger.info(f"❤️ Sent reaction response for {emoji}")


def handle_document_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle document messages"""
    document_data = msg_data.get('document', {})
    media_id = document_data.get('id')
    mime_type = document_data.get('mime_type')
    filename = document_data.get('filename', 'document')
    caption = document_data.get('caption', '')
    
    logger.info(f"Document message from {whatsapp_user.phone_number}, file: {filename}")
    
    message = create_message(
        conversation, whatsapp_message_id, 'document', 'inbound',
        None, media_id, mime_type, caption, 'delivered', timestamp
    )
    
    download_and_save_media(message, media_id)
    
    preview = f"[DOCUMENT: {filename}]"
    if caption:
        preview += f" {caption[:30]}"
    conversation.last_message_preview = preview
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()

def handle_location_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle location messages - Save only"""
    location = msg_data.get('location', {})
    latitude = location.get('latitude')
    longitude = location.get('longitude')
    name = location.get('name', '')
    address = location.get('address', '')
    
    logger.info(f"📍 Location from {whatsapp_user.phone_number}: {latitude}, {longitude}")
    
    # Create readable location text
    location_text = f"📍 Location shared:\n"
    if name:
        location_text += f"Name: {name}\n"
    if address:
        location_text += f"Address: {address}\n"
    location_text += f"Coordinates: {latitude}, {longitude}\n"
    location_text += f"Google Maps: https://www.google.com/maps?q={latitude},{longitude}"
    
    msg_obj = create_message(
        conversation, whatsapp_message_id, 'location', 'inbound',
        location_text, None, None, None, 'delivered', timestamp
    )
    
    conversation.last_message_preview = "[LOCATION]"
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()
    
    return msg_obj


def handle_location_with_ai(msg_data, conversation, whatsapp_user, from_number, timestamp, whatsapp_message_id):
    """
    Handle location + Generate AI response
    """
    try:
        # Save location message first
        msg_obj = handle_location_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
        
        if not msg_obj:
            return
        
        location = msg_data.get('location', {})
        latitude = location.get('latitude')
        longitude = location.get('longitude')
        name = location.get('name', '')
        address = location.get('address', '')
        
        # Detect user language
        recent_msg = conversation.messages.filter(
            direction='inbound',
            message_type='text'
        ).order_by('-timestamp').first()
        
        user_lang = 'hi'
        if recent_msg and recent_msg.text_content:
            if any(u'\u0900' <= char <= u'\u097f' for char in recent_msg.text_content):
                user_lang = 'hi'
            else:
                user_lang = 'en'
        
        user_name = whatsapp_user.name
        
        # Prepare location for AI
        ai_message = f"User shared their location: {name or 'Unknown place'}"
        if address:
            ai_message += f" at {address}"
        ai_message += f". Coordinates: {latitude}, {longitude}"
        
        # Get history
        history = []
        qs = conversation.messages.filter(timestamp__lt=timestamp).order_by('-timestamp')[:10]
        
        for m in reversed(qs):
            if m.message_type in ('text', 'audio', 'location'):
                role = 'user' if m.direction == 'inbound' else 'model'
                content = m.text_content or f'[{m.message_type}]'
                history.append({"role": role, "parts": [content]})
        
        # Get AI service
        ai_service = get_multi_gemini_service()
        formatted_prompt = SYSTEM_PROMPT.format(
            user_lang=user_lang,
            user_name=user_name
        )
        
        # Generate response
        reply = ai_service.generate_reply(
            system_prompt=formatted_prompt,
            user_message=ai_message,
            history=history,
            query_type="general"
        )
        
        log_inquiry_details(ai_message, reply, whatsapp_user, conversation, user_lang)
        
        # Send AI response (mark as AI-generated)
        if reply and reply not in ["[IGNORE]", "[ESCALATE]"]:
            sent_msg = WhatsAppService().send_text_message(from_number, reply, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True  # ✅ Mark as AI
                sent_msg.save()
            logger.info(f"✅ AI responded to location")
        elif reply == "[ESCALATE]":
            escalation_msg = (
                "हमारी टीम जल्द ही आपसे संपर्क करेगी।" 
                if user_lang == 'hi' else 
                "location taken.Our team will reach you soon."
            )
            sent_msg = WhatsAppService().send_text_message(from_number, escalation_msg, conversation)
            if sent_msg:
                sent_msg.is_ai_generated = True
                sent_msg.save()
        
    except Exception as e:
        logger.error(f"❌ Error processing location with AI: {str(e)}", exc_info=True)
def handle_button_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle button reply messages"""
    button_data = msg_data.get('button', {})
    button_text = button_data.get('text', '')
    button_payload = button_data.get('payload', '')
    
    logger.info(f"Button reply from {whatsapp_user.phone_number}: {button_text}")
    
    text_content = f"[Button: {button_text}]"
    if button_payload:
        text_content += f"\nPayload: {button_payload}"
    
    create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        text_content, None, None, None, 'delivered', timestamp
    )
    
    conversation.last_message_preview = f"[Button: {button_text}]"
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()


def handle_interactive_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle interactive messages (list replies, button replies, etc.)"""
    interactive = msg_data.get('interactive', {})
    interactive_type = interactive.get('type')
    
    logger.info(f"Interactive message ({interactive_type}) from {whatsapp_user.phone_number}")
    
    text_content = ""
    
    if interactive_type == 'list_reply':
        list_reply = interactive.get('list_reply', {})
        title = list_reply.get('title', '')
        reply_id = list_reply.get('id', '')
        description = list_reply.get('description', '')
        text_content = f"[List Selection: {title}]"
        if description:
            text_content += f"\n{description}"
    
    elif interactive_type == 'button_reply':
        button_reply = interactive.get('button_reply', {})
        title = button_reply.get('title', '')
        reply_id = button_reply.get('id', '')
        text_content = f"[Button: {title}]"
    
    elif interactive_type == 'nfm_reply':
        # WhatsApp Flow response
        nfm_reply = interactive.get('nfm_reply', {})
        name = nfm_reply.get('name', '')
        response_json = nfm_reply.get('response_json', '')
        text_content = f"[Flow Response: {name}]"
        logger.info(f"Flow response data: {response_json}")
    
    else:
        text_content = f"[Interactive: {interactive_type}]"
    
    create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        text_content, None, None, None, 'delivered', timestamp
    )
    
    conversation.last_message_preview = text_content[:]
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()


def process_status_updates(value):
    """Process message status updates"""
    statuses = value.get('statuses', [])
    
    for status_data in statuses:
        try:
            message_id = status_data.get('id')
            status = status_data.get('status')  # sent, delivered, read, failed
            recipient_id = status_data.get('recipient_id')
            
            logger.info(f"Status update: {message_id} -> {status}")
            
            # Update message status
            try:
                message = Message.objects.get(whatsapp_message_id=message_id)
                message.status = status
                
                if status == 'failed':
                    error_info = status_data.get('errors', [{}])[0]
                    message.error_message = error_info.get('message', 'Unknown error')
                    logger.error(f"Message failed: {message.error_message}")
                
                message.save()
                logger.info(f"Updated message {message_id} status to {status}")
                
            except Message.DoesNotExist:
                logger.warning(f"Message with ID {message_id} not found for status update")
                
        except Exception as e:
            logger.error(f"Error processing status update: {str(e)}", exc_info=True)


def create_message(conversation, whatsapp_message_id, message_type, direction, 
                   text_content, media_id, mime_type, caption, status, timestamp):
    """Helper function to create a message"""
    message = Message.objects.create(
        conversation=conversation,
        whatsapp_message_id=whatsapp_message_id,
        message_type=message_type,
        direction=direction,
        text_content=text_content,
        media_id=media_id,
        mime_type=mime_type,
        caption=caption,
        status=status,
        timestamp=timestamp
    )
    
    logger.info(f"Created message: {message.id} ({message_type})")
    return message


def download_and_save_media(message, media_id):
    """Download media from WhatsApp and save locally"""
    try:
        whatsapp_service = WhatsAppService()
        media_content, content_type = whatsapp_service.download_media(media_id)
        
        if media_content:
            # Determine file extension
            ext_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'video/mp4': '.mp4',
                'video/3gpp': '.3gp',
                'audio/mpeg': '.mp3',
                'audio/ogg': '.ogg',
                'audio/aac': '.aac',
                'audio/amr': '.amr',
                'application/pdf': '.pdf',
                'application/msword': '.doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
                'application/vnd.ms-excel': '.xls',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            }
            
            extension = ext_map.get(content_type, '.bin')
            file_name = f"{media_id}{extension}"
            
            # Save media file
            media_file = MediaFile.objects.create(
                message=message,
                file_name=file_name,
                file_size=len(media_content)
            )
            
            media_file.file.save(file_name, ContentFile(media_content))
            message.media_url = media_file.file.url
            message.save()
            
            logger.info(f"Media downloaded and saved: {file_name} ({len(media_content)} bytes)")
        else:
            logger.error(f"Failed to download media: {media_id}")
            
    except Exception as e:
        logger.error(f"Error downloading media {media_id}: {str(e)}", exc_info=True)

def chat_list_view(request):
    conversations = Conversation.objects.select_related('whatsapp_user').all()
    return render(request, 'whatsapp_chat/chat_list.html', {
        'conversations': conversations,
    })


def chat_detail_view(request, user_id):
    whatsapp_user = get_object_or_404(WhatsAppUser, id=user_id)
    conversation = get_object_or_404(Conversation, whatsapp_user=whatsapp_user)
    messages = conversation.messages.all()
    templates = WhatsAppTemplate.objects.filter(status='approved')
    
    conversation.unread_count = 0
    conversation.save()
    
    return render(request, 'whatsapp_chat/chat_detail.html', {
        'whatsapp_user': whatsapp_user,
        'conversation': conversation,
        'messages': messages,
        'templates': templates,
    })


@require_http_methods(["POST"])
def send_message_api(request):
    """API endpoint to send messages"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        user_id = data.get('user_id')
        message_type = data.get('message_type')
        
        logger.info(f"Send message request: type={message_type}, user_id={user_id}")
        
        whatsapp_user = get_object_or_404(WhatsAppUser, id=user_id)
        conversation = get_object_or_404(Conversation, whatsapp_user=whatsapp_user)
        whatsapp_service = WhatsAppService()
        
        message = None
        
        if message_type == 'text':
            text_content = data.get('text', '').strip()
            if not text_content:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Text content is required'
                }, status=400)
            
            logger.info(f"Sending text: '{text_content}' to {whatsapp_user.phone_number}")
            message = whatsapp_service.send_text_message(
                whatsapp_user.phone_number, text_content, conversation
            )
            
        elif message_type == 'template':
            template_name = data.get('template_name', '').strip()
            language_code = data.get('language_code', 'en')
            components = data.get('components', [])
            
            if not template_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Template name is required'
                }, status=400)
            
            logger.info(f"Sending template: {template_name} ({language_code}) to {whatsapp_user.phone_number}")
            logger.info(f"Raw components received: {json.dumps(components, indent=2)}")
            
            # Don't clean components - send them as-is if they exist
            # WhatsApp API will validate them
            if components:
                logger.info(f"Using components as provided: {json.dumps(components, indent=2)}")
            else:
                logger.info("No components provided")
            
            message = whatsapp_service.send_template_message(
                whatsapp_user.phone_number,
                template_name,
                language_code,
                components,  # Send as-is, don't clean
                conversation
            )   
        elif message_type in ['image', 'video', 'audio', 'document']:
            media_id = data.get('media_id', '').strip()
            caption = data.get('caption', '').strip()
            
            if not media_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Media ID is required'
                }, status=400)
            
            logger.info(f"Sending {message_type}: {media_id} to {whatsapp_user.phone_number}")
            message = whatsapp_service.send_media_message(
                whatsapp_user.phone_number,
                message_type,
                media_id,
                caption,
                conversation
            )
        
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Unsupported message type: {message_type}'
            }, status=400)
        
        if message:
            logger.info(f"Message sent successfully: {message.id}")
            return JsonResponse({
                'status': 'success',
                'message_id': message.id,
                'timestamp': message.timestamp.isoformat()
            })
        else:
            logger.error("Failed to send message - no message object returned")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send message. Check logs for details.'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Send error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_http_methods(["POST"])
def upload_media_api(request):
    """API endpoint to upload media files"""
    temp_path = None
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No file provided'
            }, status=400)
        
        file = request.FILES['file']
        mime_type = file.content_type
        
        logger.info(f"Uploading file: {file.name}, type: {mime_type}, size: {file.size}")
        
        # Validate file type
        allowed_types = {
            'image/jpeg', 'image/png', 'image/jpg',
            'video/mp4', 'video/3gpp',
            'audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        if mime_type not in allowed_types:
            return JsonResponse({
                'status': 'error',
                'message': f'File type {mime_type} not supported'
            }, status=400)
        
        # Validate file size
        max_size = 100 * 1024 * 1024 if mime_type.startswith('application/') else 16 * 1024 * 1024
        if file.size > max_size:
            return JsonResponse({
                'status': 'error',
                'message': f'File too large. Max size: {max_size / (1024*1024):.0f}MB'
            }, status=400)
        
        # Create a temporary file with proper extension
        file_extension = os.path.splitext(file.name)[1]
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
        temp_path = temp_file.name
        
        # Write uploaded file to temp file
        for chunk in file.chunks():
            temp_file.write(chunk)
        temp_file.close()
        
        logger.info(f"Saved temp file: {temp_path}")
        
        # Upload to WhatsApp
        whatsapp_service = WhatsAppService()
        media_id = whatsapp_service.upload_media(temp_path, mime_type)
        
        if media_id:
            logger.info(f"Upload successful: {media_id}")
            return JsonResponse({
                'status': 'success',
                'media_id': media_id
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to upload media to WhatsApp'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.info(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


def handle_unknown_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle unknown message types"""
    text_content = f"[Unsupported message type: {msg_data.get('type')}]"
    
    msg_obj = create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        text_content, None, None, None, 'delivered', timestamp
    )
    
    conversation.last_message_preview = text_content
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()
    
    logger.warning(f"Saved unsupported message type from {whatsapp_user.phone_number}")
    return msg_obj