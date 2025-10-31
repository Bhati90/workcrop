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

@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        from django.conf import settings
        verify_token = settings.WHATSAPP_CONFIG['VERIFY_TOKEN']
        
        if mode == 'subscribe' and token == verify_token:
            logger.info("Webhook verified")
            return HttpResponse(challenge, status=200)
        else:
            logger.warning("Webhook verification failed")
            return HttpResponse('Forbidden', status=403)
    
    elif request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8'))
            WebhookLog.objects.create(payload=body)
            process_webhook_data(body)
            return JsonResponse({"status": "success"}, status=200)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({"status": "error"}, status=500)


def process_webhook_data(data):
    try:
        entry = data.get('entry', [])
        if not entry:
            return
        
        for item in entry:
            changes = item.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                if 'messages' in value:
                    process_incoming_messages(value)
                if 'statuses' in value:
                    process_status_updates(value)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")


def process_incoming_messages(value):
    messages = value.get('messages', [])
    contacts = value.get('contacts', [])
    
    for msg_data in messages:
        try:
            from_number = msg_data['from']
            contact_name = from_number
            
            for contact in contacts:
                if contact['wa_id'] == from_number:
                    contact_name = contact['profile']['name']
                    break
            
            whatsapp_user, created = WhatsAppUser.objects.get_or_create(
                phone_number=from_number,
                defaults={'name': contact_name}
            )
            
            conversation, _ = Conversation.objects.get_or_create(
                whatsapp_user=whatsapp_user
            )
            
            message_type = msg_data.get('type')
            whatsapp_message_id = msg_data['id']
            timestamp = timezone.datetime.fromtimestamp(int(msg_data['timestamp']))
            
            if message_type == 'text':
                text_content = msg_data['text']['body']
                
                Message.objects.create(
                    conversation=conversation,
                    whatsapp_message_id=whatsapp_message_id,
                    message_type='text',
                    direction='inbound',
                    text_content=text_content,
                    status='delivered',
                    timestamp=timestamp
                )
                
                conversation.last_message_preview = text_content[:100]
                conversation.unread_count += 1
                conversation.save()
                
                whatsapp_user.last_message_at = timestamp
                whatsapp_user.save()
                
            elif message_type in ['image', 'video', 'audio', 'document']:
                media_data = msg_data[message_type]
                media_id = media_data['id']
                mime_type = media_data.get('mime_type')
                caption = media_data.get('caption', '')
                
                Message.objects.create(
                    conversation=conversation,
                    whatsapp_message_id=whatsapp_message_id,
                    message_type=message_type,
                    direction='inbound',
                    media_id=media_id,
                    mime_type=mime_type,
                    caption=caption,
                    status='delivered',
                    timestamp=timestamp
                )
                
                preview = f"[{message_type.upper()}]"
                if caption:
                    preview += f" {caption[:50]}"
                conversation.last_message_preview = preview
                conversation.unread_count += 1
                conversation.save()
                
                whatsapp_user.last_message_at = timestamp
                whatsapp_user.save()
            
            whatsapp_service = WhatsAppService()
            whatsapp_service.mark_message_as_read(whatsapp_message_id)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")


def process_status_updates(value):
    statuses = value.get('statuses', [])
    
    for status_data in statuses:
        try:
            message_id = status_data['id']
            status = status_data['status']
            
            try:
                message = Message.objects.get(whatsapp_message_id=message_id)
                message.status = status
                
                if status == 'failed':
                    error_info = status_data.get('errors', [{}])[0]
                    message.error_message = error_info.get('message', 'Unknown error')
                
                message.save()
            except Message.DoesNotExist:
                pass
        except Exception as e:
            logger.error(f"Error processing status: {str(e)}")



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