import requests
import os
import logging
from django.utils import timezone
from .models import ChatContact, Message
from django.core.files.base import ContentFile
from dotenv import load_dotenv
import mimetypes

API_VERSION = 'v19.0'
META_API_URL = f"https://graph.facebook.com/{API_VERSION}"

META_ACCESS_TOKEN ="EAAhMBt21QaMBPCyLtJj6gwjDy6Gai4fZApb3MXuZBZCCm0iSEd8ZCZCJdkRt4cOtvhyeFLZCNUwitFaLZA3ZCwv7enN6FBFgDMAOKl7LMx0J2kCjy6Qd6AqnbnhB2bo2tgsdGmn9ZCN5MD6yCgE3shuP62t1spfSB6ZALy1QkNLvIaeWZBcvPH00HHpyW6US4kil2ENZADL4ZCvDLVWV9seSbZCxXYzVCezIenCjhSYtoKTIlJ"
PHONE_NUMBER_ID = 694609297073147
WABA_ID =  1477047197063313

waba_id =  1477047197063313



# registration/services.py
logger = logging.getLogger(__name__)


# services.py or whats_app.py
# (Make sure requests, logger, etc. are imported)

def upload_media_for_template_handle(file_object):
    """
    Uploads a file to Meta's template asset endpoint and returns a handle.
    """
    try:
        url = f"https://graph.facebook.com/v19.0/{WABA_ID}/message_template_assets"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        file_object.seek(0)
        
        files = {'file': (file_object.name, file_object, file_object.content_type)}
        data = {'messaging_product': 'whatsapp'}
        
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        
        # The response contains a 'handle' key
        return response.json().get('handle')

    except Exception as e:
        logger.error(f"Failed to upload media for handle: {e}", exc_info=True)
        return None

def send_whatsapp_template(to_number, template_name, components):
    """
    Sends a WhatsApp template message using the Meta Graph API.
    """ 
    access_token ="EAAhMBt21QaMBPCyLtJj6gwjDy6Gai4fZApb3MXuZBZCCm0iSEd8ZCZCJdkRt4cOtvhyeFLZCNUwitFaLZA3ZCwv7enN6FBFgDMAOKl7LMx0J2kCjy6Qd6AqnbnhB2bo2tgsdGmn9ZCN5MD6yCgE3shuP62t1spfSB6ZALy1QkNLvIaeWZBcvPH00HHpyW6US4kil2ENZADL4ZCvDLVWV9seSbZCxXYzVCezIenCjhSYtoKTIlJ"

    phone_id = 705449502657013
    
    if not all([access_token, phone_id]):
        logger.error("WhatsApp API credentials are not set.")
        return False, {"error": "Server not configured for messages."}

    api_url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": components,
        },
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        message_id = response.json().get('messages', [{}])[0].get('id')
        logger.info(f"Successfully sent template '{template_name}' to {to_number}.")
        return True, response.json()
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send WhatsApp template to {to_number}: {e}")
        error_details = e.response.json() if e.response else str(e)
        return False, {"error": error_details}



def download_media_from_meta(media_id):
    try:
        url = f"{META_API_URL}/{media_id}/"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        media_info = response.json()
        media_url = media_info.get('url')
        if not media_url: return None, None
        media_response = requests.get(media_url, headers=headers)
        media_response.raise_for_status()
        content_type = media_response.headers.get('Content-Type', 'application/octet-stream')
        extension = content_type.split('/')[-1]
        file_name = f"{media_id}.{extension}"
        return file_name, ContentFile(media_response.content)
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download media {media_id}: {e}")
        return None, None

import mimetypes # <-- Add this import at the top of your file
import os      # <-- Also add this import

def upload_media_to_meta(file_object):
    """
    Uploads a file object to the Meta API and returns the media ID.
    Works with both UploadedFile and standard File objects.
    """
    try:
        url = f"{META_API_URL}/{PHONE_NUMBER_ID}/media"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        
        # Ensure the file pointer is at the beginning
        file_object.seek(0)

        # --- THIS IS THE FIX ---
        # Get the filename from the file object's name attribute
        file_name = os.path.basename(file_object.name)
        
        # Guess the content type from the filename
        content_type, _ = mimetypes.guess_type(file_name)
        if content_type is None:
            # Provide a fallback for unknown file types
            content_type = 'application/octet-stream'
        # --- END OF FIX ---

        files = {
            'file': (file_name, file_object, content_type),
        }
        data = {
            'messaging_product': 'whatsapp',
        }
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json().get('id')
        
    except Exception as e:
        logger.error(f"Failed to upload media: {e}", exc_info=True)
        return None

import json
def send_whatsapp_message(payload):
    url = f"{META_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        error_details = "No response from server."
        if e.response is not None:
            try:
                error_details = e.response.json() # Try to get the detailed JSON error
            except json.JSONDecodeError:
                error_details = e.response.text # Fallback to raw text if not JSON
        
        # This new log will show the specific reason for the failure
        logger.error(f"Error from Meta API. Status: {e.response.status_code if e.response else 'N/A'}. Details: {error_details}")
        
        return False, error_details
    

def save_outgoing_message(contact, wamid, message_type, text_content="", caption="", raw_data={}, replied_to_wamid=None, media_file=None, source_node_id=None):
    """
    Saves an outgoing message to the database, now including the source_node_id from a flow.
    """
    defaults = {
        'contact': contact,
        'direction': 'outbound',
        'message_type': message_type,
        'text_content': text_content,
        'caption': caption,
        'timestamp': timezone.now(),
        'raw_data': raw_data,
        'status': 'sent',
        'source_node_id': source_node_id  # <-- ADDED THIS LINE
    }
    
    if replied_to_wamid:
        try:
            defaults['replied_to'] = Message.objects.get(wamid=replied_to_wamid)
        except Message.DoesNotExist:
            pass
    
    message, created = Message.objects.update_or_create(wamid=wamid, defaults=defaults)

    if media_file and not message.media_file:
        # We use the wamid to create a unique file name
        file_name = f"outbound/{contact.wa_id}/{wamid}_{media_file.name}"
        message.media_file.save(file_name, media_file, save=True)

    contact.last_contact_at = timezone.now()
    contact.save()
    """
    # Sends a WhatsApp template message using the Meta Graph API.
    # """ 