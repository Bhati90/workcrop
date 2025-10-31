import requests
import logging
from django.conf import settings
from .models import Message

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self):
        self.access_token = settings.WHATSAPP_CONFIG['ACCESS_TOKEN']
        self.phone_number_id = settings.WHATSAPP_CONFIG['PHONE_NUMBER_ID']
        self.api_version = settings.WHATSAPP_CONFIG['API_VERSION']
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def send_text_message(self, to_phone, message_text, conversation):
        url = f"{self.base_url}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": message_text
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            message = Message.objects.create(
                conversation=conversation,
                whatsapp_message_id=result['messages'][0]['id'],
                message_type='text',
                direction='outbound',
                text_content=message_text,
                status='sent'
            )
            
            conversation.last_message_preview = message_text[:100]
            conversation.save()
            
            logger.info(f"Text message sent to {to_phone}")
            return message
            
        except Exception as e:
            logger.error(f"Error sending text: {str(e)}")
            Message.objects.create(
                conversation=conversation,
                message_type='text',
                direction='outbound',
                text_content=message_text,
                status='failed',
                error_message=str(e)
            )
            return None

    def send_media_message(self, to_phone, media_type, media_id, caption, conversation):
        url = f"{self.base_url}/messages"
        
        media_object = {"id": media_id}
        if caption and media_type in ['image', 'video', 'document']:
            media_object['caption'] = caption
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": media_type,
            media_type: media_object
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            message = Message.objects.create(
                conversation=conversation,
                whatsapp_message_id=result['messages'][0]['id'],
                message_type=media_type,
                direction='outbound',
                media_id=media_id,
                caption=caption,
                status='sent'
            )
            
            preview = f"[{media_type.upper()}]"
            if caption:
                preview += f" {caption[:50]}"
            conversation.last_message_preview = preview
            conversation.save()
            
            logger.info(f"{media_type} sent to {to_phone}")
            return message
            
        except Exception as e:
            logger.error(f"Error sending media: {str(e)}")
            return None

    def send_template_message(self, to_phone, template_name, language_code, components, conversation):
        url = f"{self.base_url}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            message = Message.objects.create(
                conversation=conversation,
                whatsapp_message_id=result['messages'][0]['id'],
                message_type='template',
                direction='outbound',
                template_name=template_name,
                template_language=language_code,
                template_params=components,
                status='sent'
            )
            
            conversation.last_message_preview = f"[Template: {template_name}]"
            conversation.save()
            
            logger.info(f"Template sent to {to_phone}")
            return message
            
        except Exception as e:
            logger.error(f"Error sending template: {str(e)}")
            return None

    def upload_media(self, file_path, mime_type):
        url = f"{self.base_url}/media"
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        files = {
            'file': open(file_path, 'rb'),
            'messaging_product': (None, 'whatsapp'),
            'type': (None, mime_type)
        }
        
        try:
            response = requests.post(url, headers=headers, files=files)
            response.raise_for_status()
            result = response.json()
            return result['id']
        except Exception as e:
            logger.error(f"Error uploading media: {str(e)}")
            return None

    def download_media(self, media_id):
        url = f"https://graph.facebook.com/{self.api_version}/{media_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            media_url = response.json()['url']
            
            media_response = requests.get(media_url, headers=self.headers)
            media_response.raise_for_status()
            
            return media_response.content, media_response.headers.get('Content-Type')
        except Exception as e:
            logger.error(f"Error downloading media: {str(e)}")
            return None, None

    def mark_message_as_read(self, message_id):
        url = f"{self.base_url}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error marking as read: {str(e)}")
            return False