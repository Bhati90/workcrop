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

from .models import WhatsAppUser, Conversation, Message, MediaFile, WebhookLog, WhatsAppTemplate
from .service import WhatsAppService

logger = logging.getLogger(__name__)


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

SPAM_KEYWORDS = ['xxx', 'bank', 'password', 'joke', 'random', 'movie', 'cricket']  # Expand as needed

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
        logger.info("🚀 Created NEW GeminiService and cached it")
    else:
        logger.info("♻️ Reusing CACHED GeminiService instance")
    
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

        # --- 3. Save the Incoming Message to DB ---
        msg_obj = _save_incoming_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
        
        if not msg_obj:
            return

        # --- 4. Send "Read" Receipt ---
        WhatsAppService().mark_message_as_read(whatsapp_message_id)

        # --- 5. We ONLY respond to 'text' messages with AI ---
        if message_type != 'text':
            logger.info(f"Ignoring non-text message type '{message_type}' for AI reply.")
            return

        # --- 6. Prepare data for Gemini ---
        txt = msg_data.get('text', {}).get('body', '').strip()
        if not txt:
            logger.info("Ignoring empty text message.")
            return

        user_lang = 'hi' if any(u'\u0900' <= char <= u'\u097f' for char in txt) else 'en'
        user_name = whatsapp_user.name

        # --- 7. Gather History ---
        history = []
        qs = conversation.messages.filter(timestamp__lt=timestamp).order_by('-timestamp')[:10]
        
        for m in reversed(qs):
            if m.message_type not in ('document'):
                role = 'user' if m.direction == 'inbound' else 'model'
                content = m.text_content or m.caption or f'[{m.message_type}]'
                history.append({"role": role, "parts": [content]})
        
        # --- 8. Get CACHED GeminiService instance ---
        gemini = get_gemini_service()
        
        # --- 9. Handle quota errors gracefully ---
        try:
            reply = gemini.generate_reply(history, txt, user_lang, user_name)
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
            elif recent_redirects >= 1 or recent_escalations >= 1:
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
        if reply:
            WhatsAppService().send_text_message(from_number, reply, conversation)
        else:
            logger.error("Gemini returned empty reply.")
            fallback_msg = (
                "हमारी टीम जल्द ही आपसे संपर्क करेगी।" 
                if user_lang == 'hi' else 
                "Our team will reach you soon."
            )
            WhatsAppService().send_text_message(from_number, fallback_msg, conversation)

    except Exception as e:
        logger.error(f"CRITICAL Error: {str(e)}", exc_info=True)


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
    
    # Only log if we detected something or it's an escalation
    if not detected_services and '[escalate]' not in str(bot_reply).lower():
        return
    
    try:
        # Extract numbers
        numbers = re.findall(r'\d+', user_message)
        quantity = numbers[0] if numbers else None
        
        # Detect urgency
        urgent_keywords = ['urgent', 'तुरंत', 'आज', 'today', 'अभी', 'now', 'जल्दी', 'emergency']
        is_urgent = any(kw in msg_lower for kw in urgent_keywords)
        
        # Detect location
        locations = ['satara', 'सातारा', 'pune', 'पुणे', 'mumbai', 'मुंबई', 'nashik', 'नाशिक']
        detected_location = next((loc for loc in locations if loc in msg_lower), None)
        
        # Check if price was requested
        asked_price = any(kw in msg_lower for kw in ['price', 'rate', 'किंमत', 'दर', 'रेट', 'cost'])
        
        # Truncate long responses
        ai_response_truncated = str(bot_reply)[:500] if bot_reply else ''
        
        # Create inquiry record
        ServiceInquiry.objects.create(
            whatsapp_user=whatsapp_user,
            conversation=conversation,
            service_type=', '.join(detected_services) if detected_services else 'general',
            service_description=user_message[:500],  # Truncate long messages
            service_language=service_lang,
            quantity_needed=str(quantity) if quantity else None,
            location_mentioned=detected_location,
            urgency='high' if is_urgent else 'medium',
            original_query=user_message[:1000],  # Limit size
            ai_response=ai_response_truncated,
            requested_price_info=asked_price,
            needs_human_review=('[escalate]' in str(bot_reply).lower() or not detected_services),
            status='new' if '[escalate]' not in str(bot_reply).lower() else 'reviewing'
        )
        
        logger.info(f"✅ Logged inquiry: {', '.join(detected_services) if detected_services else 'general'}")
        
    except Exception as e:
        logger.error(f"❌ Error logging ServiceInquiry: {str(e)}")
        # Don't crash the webhook if logging fails

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
    

def handle_text_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle text messages - FIXED"""
    text_content = msg_data.get('text', {}).get('body', '')
    
    # FIX: Only create the message ONCE
    msg_obj = create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        text_content, None, None, None, 'delivered', timestamp
    )
    
    # Update conversation/user for preview
    conversation.last_message_preview = text_content[:100]
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()
    
    logger.info(f"Text message: '{text_content}' from {whatsapp_user.phone_number}")
    return msg_obj # Return the created object

def handle_image_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle image messages"""
    image_data = msg_data.get('image', {})
    media_id = image_data.get('id')
    mime_type = image_data.get('mime_type')
    caption = image_data.get('caption', '')
    
    logger.info(f"Image message from {whatsapp_user.phone_number}, media_id: {media_id}")
    
    message = create_message(
        conversation, whatsapp_message_id, 'image', 'inbound',
        None, media_id, mime_type, caption, 'delivered', timestamp
    )
    
    # Download media asynchronously
    download_and_save_media(message, media_id)
    
    preview = "[IMAGE]"
    if caption:
        preview += f" {caption[:50]}"
    conversation.last_message_preview = preview
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()


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


def handle_audio_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle audio messages"""
    audio_data = msg_data.get('audio', {})
    media_id = audio_data.get('id')
    mime_type = audio_data.get('mime_type')
    
    logger.info(f"Audio message from {whatsapp_user.phone_number}, media_id: {media_id}")
    
    message = create_message(
        conversation, whatsapp_message_id, 'audio', 'inbound',
        None, media_id, mime_type, None, 'delivered', timestamp
    )
    
    download_and_save_media(message, media_id)
    
    conversation.last_message_preview = "[AUDIO]"
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()


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
    """Handle location messages"""
    location = msg_data.get('location', {})
    latitude = location.get('latitude')
    longitude = location.get('longitude')
    name = location.get('name', '')
    address = location.get('address', '')
    
    logger.info(f"Location from {whatsapp_user.phone_number}: {latitude}, {longitude}")
    
    location_text = f"📍 Location: {name or 'Unnamed'}\n"
    if address:
        location_text += f"Address: {address}\n"
    location_text += f"Coordinates: {latitude}, {longitude}"
    
    create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        location_text, None, None, None, 'delivered', timestamp
    )
    
    conversation.last_message_preview = "[LOCATION]"
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()


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
    
    conversation.last_message_preview = text_content[:100]
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

