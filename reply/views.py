import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
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


def process_incoming_messages(value, full_webhook_data):
    """Process incoming messages from customers"""
    messages = value.get('messages', [])
    contacts = value.get('contacts', [])
    
    for msg_data in messages:
        try:
            from_number = msg_data['from']
            message_type = msg_data.get('type')
            whatsapp_message_id = msg_data['id']
            timestamp = timezone.datetime.fromtimestamp(int(msg_data['timestamp']))
            
            logger.info(f"Processing {message_type} message from {from_number}")
            
            # Get contact name from webhook
            contact_name = from_number
            for contact in contacts:
                if contact.get('wa_id') == from_number:
                    contact_name = contact.get('profile', {}).get('name', from_number)
                    break
            
            # Get or create WhatsApp user
            whatsapp_user, created = WhatsAppUser.objects.get_or_create(
                phone_number=from_number,
                defaults={'name': contact_name}
            )
            
            if not created and whatsapp_user.name != contact_name:
                whatsapp_user.name = contact_name
                whatsapp_user.save()
            
            # Get or create conversation
            conversation, _ = Conversation.objects.get_or_create(
                whatsapp_user=whatsapp_user
            )
            
            # Process based on message type
            if message_type == 'text':
                handle_text_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'image':
                handle_image_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'video':
                handle_video_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'audio':
                handle_audio_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'document':
                handle_document_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'location':
                handle_location_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'button':
                handle_button_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            elif message_type == 'interactive':
                handle_interactive_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp)
            
            else:
                logger.warning(f"Unsupported message type: {message_type}")
                create_message(
                    conversation, whatsapp_message_id, 'text', 'inbound',
                    f"[Unsupported message type: {message_type}]", None, None, None,
                    'delivered', timestamp
                )
            
            # Mark message as read
            whatsapp_service = WhatsAppService()
            whatsapp_service.mark_message_as_read(whatsapp_message_id)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)


def handle_text_message(msg_data, conversation, whatsapp_user, whatsapp_message_id, timestamp):
    """Handle text messages"""
    text_content = msg_data.get('text', {}).get('body', '')
    logger.info(f"Text message: '{text_content}' from {whatsapp_user.phone_number}")
    
    create_message(
        conversation, whatsapp_message_id, 'text', 'inbound',
        text_content, None, None, None, 'delivered', timestamp
    )
    
    conversation.last_message_preview = text_content[:100]
    conversation.unread_count += 1
    conversation.save()
    
    whatsapp_user.last_message_at = timestamp
    whatsapp_user.save()


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
    try:
        data = json.loads(request.body.decode('utf-8'))
        user_id = data.get('user_id')
        message_type = data.get('message_type')
        
        whatsapp_user = get_object_or_404(WhatsAppUser, id=user_id)
        conversation = get_object_or_404(Conversation, whatsapp_user=whatsapp_user)
        whatsapp_service = WhatsAppService()
        
        if message_type == 'text':
            text_content = data.get('text')
            message = whatsapp_service.send_text_message(
                whatsapp_user.phone_number, text_content, conversation
            )
        elif message_type == 'template':
            template_name = data.get('template_name')
            language_code = data.get('language_code', 'en')
            components = data.get('components', [])
            message = whatsapp_service.send_template_message(
                whatsapp_user.phone_number, template_name, 
                language_code, components, conversation
            )
        elif message_type in ['image', 'video', 'audio', 'document']:
            media_id = data.get('media_id')
            caption = data.get('caption', '')
            message = whatsapp_service.send_media_message(
                whatsapp_user.phone_number, message_type, 
                media_id, caption, conversation
            )
        
        if message:
            return JsonResponse({
                'status': 'success',
                'message_id': message.id
            })
        else:
            return JsonResponse({'status': 'error'}, status=500)
    except Exception as e:
        logger.error(f"Send error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_http_methods(["POST"])
def upload_media_api(request):
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No file'}, status=400)
        
        file = request.FILES['file']
        mime_type = file.content_type
        
        temp_path = f'/tmp/{file.name}'
        with open(temp_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        whatsapp_service = WhatsAppService()
        media_id = whatsapp_service.upload_media(temp_path, mime_type)
        
        if media_id:
            return JsonResponse({'status': 'success', 'media_id': media_id})
        else:
            return JsonResponse({'status': 'error'}, status=500)
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JsonResponse({'status': 'error'}, status=500)