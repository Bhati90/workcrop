# contact_app/views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt # Import csrf_exempt
# from corsheaders.decorators import cors_exempt       # Import cors_exempt
import json

from django.shortcuts import render # Make sure render is imported

# def home_page(request):
#     return render(request, 'contact_app/home.html', {'message': 'Welcome to my Contact App!'})

# from .models import Flow, Message, 
#  # Make sure these are imported
from .models import ChatContact, Message
from .models import Flows as Flow
from .models import UserFlowSessions as UserFlowSession
from .models import Attribute  # <-- Add this import for Attribute model
from .models import ContactAttributeValue  # <-- Add this import for ContactAttributeValue model
from .whats_app import send_whatsapp_message, save_outgoing_message, upload_media_for_template_handle
from django.utils import timezone
import os
import mimetypes
import logging
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import logging
from django.http import HttpResponse
logger = logging.getLogger(__name__)



from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import render

from .models import Flows as Flow
from .models import UserFlowSessions as UserFlowSession
from .whats_app import send_whatsapp_message, save_outgoing_message
from django.utils import timezone
import logging
import requests

logger = logging.getLogger(__name__)

# API_VERSION = 'v19.0'
# META_API_URL = f"https://graph.facebook.com/{API_VERSION}"
# PHONE_NUMBER_ID = 705449502657013
# META_ACCESS_TOKEN="EAAhMBt21QaMBPCyLtJj6gwjDy6Gai4fZApb3MXuZBZCCm0iSEd8ZCZCJdkRt4cOtvhyeFLZCNUwitFaLZA3ZCwv7enN6FBFgDMAOKl7LMx0J2kCjy6Qd6AqnbnhB2bo2tgsdGmn9ZCN5MD6yCgE3shuP62t1spfSB6ZALy1QkNLvIaeWZBcvPH00HHpyW6US4kil2ENZADL4ZCvDLVWV9seSbZCxXYzVCezIenCjhSYtoKTIlJ"
# WABA_ID = "1477047197063313"

def home_page(request):
    return render(request, 'contact_app/home.html', {'message': 'Welcome to my Contact App!'})


# --- Constants ---
API_VERSION = 'v23.0'
META_API_URL = f"https://graph.facebook.com/{API_VERSION}"
PHONE_NUMBER_ID = '694609297073147' # Replace with your Phone Number ID
META_ACCESS_TOKEN = "EAAhMBt21QaMBPvjRpT7P1mhB0xKD1sb7ZCsal0MfRM6yx3p5hInGYHguN70XRCuo18NeuB2BYlM6e1ZBJtpH1ZBmRg6BZB9MeULcfXWdYptZCpzHzSXa0fFBlAzVJh7ZC22njeo5mgIWKY5ZBsiJrryJTh8sOvBp4HZBy51hnZA7hDegmowduSachpXCvH5vLlVMunBAv6ej41X6143kP5pSEKQfqO6NzlVUnA7ZC4HHTj" # Replace with your Meta Access Token
WABA_ID = "1477047197063313" # Replace with your WABA ID

# --- Core Flow Execution Logic ---

# --- Core Flow Execution Logic ---

def substitute_placeholders(text, user_data):
    """Replace {{variable}} with actual values"""
    if not text:
        return text
    
    import re
    
    def replace_placeholder(match):
        key = match.group(1).strip()
        value = user_data.get(key, f"{{{{ {key} }}}}")
        logger.info(f"DEBUG-SUBSTITUTION: Replacing {{{{ {key} }}}} with '{value}'")
        return str(value)
    
    return re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace_placeholder, text)

def extract_json_path(data, path):
    """Extract value from JSON using dot notation"""
    try:
        current = data
        parts = path.split('.')
        for part in parts:
            if part.isdigit():
                current = current[int(part)]
            else:
                current = current[part]
        return current
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    

def execute_flow_node(contact, flow, target_node):
    """
    Central helper function to construct a message payload for a given node,
    send it, and manage the user's session.
    """
    target_node_id = target_node.get('id')
    node_type = target_node.get('type')
    node_data = target_node.get('data', {})
    
    payload = {"messaging_product": "whatsapp", "to": contact.wa_id}
    message_type_to_save = node_type
    text_content_to_save = f"Flow Step: {node_type}"

    if node_type == 'templateNode':
        components = []
        if 'metaMediaId' in node_data and node_data['metaMediaId']:
            header_format = node_data.get('headerComponent', {}).get('format', 'IMAGE').lower()
            components.append({"type": "header", "parameters": [{"type": header_format, header_format: {"id": node_data['metaMediaId']}}]})
        body_params = []
        for i in range(1, 10):
            var_key = f'bodyVar{i}'
            if var_key in node_data and node_data[var_key]:
                body_params.append({"type": "text", "text": node_data[var_key]})
        if body_params:
            components.append({"type": "body", "parameters": body_params})
        payload.update({"type": "template", "template": {"name": node_data.get('selectedTemplateName'), "language": {"code": "en"}, "components": components}})
        message_type_to_save = 'template'
        text_content_to_save = f"Sent template: {node_data.get('selectedTemplateName')}"

    elif node_type == 'textNode':
    # Get user attributes for substitution
        user_attributes = {}
        for attr_value in contact.attribute_values.all():
            user_attributes[attr_value.attribute.name] = attr_value.value
        user_attributes['contact_id'] = contact.wa_id
        
        # Get the original text and substitute placeholders
        original_text = node_data.get('text', '...')
        substituted_text = substitute_placeholders(original_text, user_attributes)
        
        logger.info(f"DEBUG-TEXT-NODE: Original: {original_text}")
        logger.info(f"DEBUG-TEXT-NODE: After substitution: {substituted_text}")
        
        payload.update({"type": "text", "text": {"body": substituted_text}})
        message_type_to_save = 'text'
        text_content_to_save = substituted_text
    elif node_type == 'buttonsNode':
        buttons = [{"type": "reply", "reply": {"id": btn.get('text'), "title": btn.get('text')}} for btn in node_data.get('buttons', [])]
        payload.update({"type": "interactive", "interactive": {"type": "button", "body": {"text": node_data.get('text')}, "action": {"buttons": buttons}}})
        text_content_to_save = node_data.get('text')
        
    elif node_type == 'imageNode':
        payload.update({"type": "image", "image": {"id": node_data.get('metaMediaId'), "caption": node_data.get('caption')}})
        message_type_to_save = 'image'
        text_content_to_save = node_data.get('caption') or "Sent an image"
    
   
    elif node_type == 'interactiveImageNode':
        buttons = [{"type": "reply", "reply": {"id": btn.get('text'), "title": btn.get('text')}} for btn in node_data.get('buttons', [])]
        payload.update({"type": "interactive", "interactive": {"type": "button", "header": {"type": "image", "image": {"id": node_data.get('metaMediaId')}}, "body": {"text": node_data.get('bodyText')}, "action": {"buttons": buttons}}})
        text_content_to_save = node_data.get('bodyText')

    elif node_type == 'interactiveListNode':
        sections_data = []
        for section in node_data.get('sections', []):
            rows_data = [{"id": row.get('id'), "title": row.get('title'), "description": row.get('description', '')} for row in section.get('rows', [])]
            sections_data.append({"title": section.get('title'), "rows": rows_data})
        button_text = node_data.get('buttonText') or 'Select an option'
        payload.update({"type": "interactive", "interactive": {"type": "list", "header": {"type": "text", "text": node_data.get('header', '')}, "body": {"text": node_data.get('body', '')}, "footer": {"text": node_data.get('footer', '')}, "action": {"button": button_text, "sections": sections_data}}})
        text_content_to_save = node_data.get('body')
    
    elif node_type == 'mediaNode':
        media_type = node_data.get('mediaType', 'document')
        media_payload = {"id": node_data.get('metaMediaId')}
        if media_type != 'audio' and node_data.get('caption'):
            media_payload['caption'] = node_data.get('caption')
        if media_type == 'document' and node_data.get('filename'):
            media_payload['filename'] = node_data.get('filename')
        payload.update({"type": media_type, media_type: media_payload})
        message_type_to_save = media_type
        text_content_to_save = node_data.get('caption') or f"Sent a {media_type}"
    elif node_type == 'askQuestionNode':
    # Send the question to the user
        question_text = node_data.get('questionText')
        payload.update({"type": "text", "text": {"body": question_text}})
        message_type_to_save = 'text'
        text_content_to_save = question_text
        
        # FIXED: Convert ID to actual Attribute object
        question_attr = None
        if node_data.get('saveAttributeId'):
            try:
                question_attr = Attribute.objects.get(id=node_data.get('saveAttributeId'))
                logger.info(f"DEBUG-QUESTION-NODE: Found attribute object: {question_attr.name}")
            except Attribute.DoesNotExist:
                logger.error(f"DEBUG-QUESTION-NODE: Attribute ID {node_data.get('saveAttributeId')} not found")
        
        # Set the session to a special "waiting" state
        UserFlowSession.objects.update_or_create(
            contact=contact,
            defaults={
                'flow': flow, 
                'current_node_id': target_node_id,
                'waiting_for_attribute': question_attr  # Use object, not ID
            }
        )
        logger.info(f"DEBUG-QUESTION-NODE: Session for {contact.wa_id} is now waiting for attribute {question_attr}")

    # 2. Fix askLocationNode section:
    elif node_type == 'askLocationNode':
        question_text = node_data.get('questionText')
        
        # This is the specific payload for a Location Request message
        payload.update({
            "type": "interactive",
            "interactive": {
                "type": "location_request_message",
                "body": {
                    "text": question_text or "Please share your location"
                },
                "action": {
                    "name": "send_location"
                }
            }
        })
        
        message_type_to_save = 'interactive'
        text_content_to_save = question_text
        
        # FIXED: Convert IDs to actual Attribute objects
        longitude_attr = None
        latitude_attr = None
        
        if node_data.get('longitudeAttributeId'):
            try:
                longitude_attr = Attribute.objects.get(id=node_data.get('longitudeAttributeId'))
                logger.info(f"DEBUG-LOCATION-NODE: Found longitude attribute: {longitude_attr.name}")
            except Attribute.DoesNotExist:
                logger.error(f"DEBUG-LOCATION-NODE: Longitude attribute ID {node_data.get('longitudeAttributeId')} not found")
        
        if node_data.get('latitudeAttributeId'):
            try:
                latitude_attr = Attribute.objects.get(id=node_data.get('latitudeAttributeId'))
                logger.info(f"DEBUG-LOCATION-NODE: Found latitude attribute: {latitude_attr.name}")
            except Attribute.DoesNotExist:
                logger.error(f"DEBUG-LOCATION-NODE: Latitude attribute ID {node_data.get('latitudeAttributeId')} not found")
        
        # Set the session to a special "waiting for location" state
        UserFlowSession.objects.update_or_create(
            contact=contact,
            defaults={
                'flow': flow, 
                'current_node_id': target_node_id,
                'is_waiting_for_location': True,
                'longitude_attribute': longitude_attr,  # Use object, not ID
                'latitude_attribute': latitude_attr,    # Use object, not ID
                'waiting_for_attribute': None # Clear any text attribute waiting state
            }
        )
        logger.info(f"DEBUG-LOCATION-NODE: Session for {contact.wa_id} is now waiting for location. Long: {longitude_attr}, Lat: {latitude_attr}")

    # 3. Fix askForImageNode section:
    elif node_type == 'askForImageNode': # New node type
        question_text = node_data.get('questionText')
        payload.update({"type": "text", "text": {"body": question_text or "Please send an image."}})
        message_type_to_save = 'text'
        text_content_to_save = question_text
        
        # FIXED: Convert ID to actual Attribute object
        image_attr = None
        if node_data.get('saveAttributeId'):
            try:
                image_attr = Attribute.objects.get(id=node_data.get('saveAttributeId'))
                logger.info(f"DEBUG-IMAGE-NODE: Found image attribute: {image_attr.name}")
            except Attribute.DoesNotExist:
                logger.error(f"DEBUG-IMAGE-NODE: Image attribute ID {node_data.get('saveAttributeId')} not found")
        
        UserFlowSession.objects.update_or_create(
            contact=contact,
            defaults={
                'flow': flow,
                'current_node_id': target_node_id,
                'waiting_for_image_attribute': image_attr,  # Use object, not ID
                'waiting_for_attribute': None,
                'is_waiting_for_location': False
            }
        )
        logger.info(f"DEBUG-IMAGE-NODE: Session for {contact.wa_id} is now waiting for image. Attr: {image_attr}")
    
    elif node_type == 'askApiNode':
   
        api_url = node_data.get('apiUrl')
        method = node_data.get('method', 'GET').upper()
        headers = node_data.get('headers', '{}')
        request_body = node_data.get('requestBody', '{}')
        response_mappings = node_data.get('responseMappings', [])
        status_code_attr_id = node_data.get('statusCodeAttributeId')
        
        logger.info(f"DEBUG-API-REQUEST: Making {method} request to {api_url}")
        
        # Get user attributes
        user_attributes = {}
        for attr_value in contact.attribute_values.all():
            user_attributes[attr_value.attribute.name] = attr_value.value
        user_attributes['contact_id'] = contact.wa_id
        
        logger.info(f"DEBUG-API-REQUEST: Available data: {user_attributes}")
        
        # Replace placeholders
        api_url = substitute_placeholders(api_url, user_attributes)
        headers = substitute_placeholders(headers, user_attributes) 
        request_body = substitute_placeholders(request_body, user_attributes)
        
        logger.info(f"DEBUG-API-REQUEST: URL after substitution: {api_url}")
        logger.info(f"DEBUG-API-REQUEST: Body after substitution: {request_body}")
        
        # Prepare request
        request_config = {
            'method': method,
            'url': api_url,
            'timeout': 8
        }
        
        # Parse headers
        try:
            if headers and headers != '{}':
                request_config['headers'] = json.loads(headers)
            else:
                request_config['headers'] = {}
        except json.JSONDecodeError:
            logger.error(f"DEBUG-API-REQUEST: Invalid headers JSON: {headers}")
            request_config['headers'] = {}
        
        # Parse body for non-GET requests
        if method != 'GET' and request_body and request_body != '{}':
            try:
                request_config['json'] = json.loads(request_body)
            except json.JSONDecodeError:
                logger.error(f"DEBUG-API-REQUEST: Invalid body JSON, sending as text")
                request_config['data'] = request_body
        
        # Make API request
        api_success = False
        response_data = None
        status_code = 0
        
        try:
            logger.info(f"DEBUG-API-REQUEST: Sending request...")
            response = requests.request(**request_config)
            status_code = response.status_code
             # Log the raw response
            # Log the raw response
            logger.info(f"DEBUG-API-REQUEST: Raw response status: {status_code}")
            logger.info(f"DEBUG-API-REQUEST: Raw response headers: {dict(response.headers)}")
            logger.info(f"DEBUG-API-REQUEST: Raw response text: {response.text[:500]}...")  # First 500 chars
                
            # Try to parse response as JSON
            try:
                response_data = response.json()
                logger.info(f"DEBUG-API-REQUEST: Parsed JSON response: {json.dumps(response_data, indent=2)}")
      
            except:
                response_data = response.text
                logger.info(f"DEBUG-API-REQUEST: Response is not JSON, using text")
        
            
            api_success = 200 <= status_code < 300
            logger.info(f"DEBUG-API-REQUEST: Response - Status: {status_code}, Success: {api_success}")
            
        except requests.exceptions.Timeout:
            logger.error(f"DEBUG-API-REQUEST: Request timed out")
            status_code = 408
            response_data = {"error": "Request timed out"}
            
        except requests.exceptions.ConnectionError:
            logger.error(f"DEBUG-API-REQUEST: Connection error")
            status_code = 0
            response_data = {"error": "Connection error"}
            
        except Exception as e:
            logger.error(f"DEBUG-API-REQUEST: Request failed: {e}")
            status_code = 0
            response_data = {"error": str(e)}
        
        # Save status code if specified
        if status_code_attr_id:
            try:
                status_attr = Attribute.objects.get(id=status_code_attr_id)
                ContactAttributeValue.objects.update_or_create(
                    contact=contact, 
                    attribute=status_attr,
                    defaults={'value': str(status_code)}
                )
                logger.info(f"DEBUG-API-REQUEST: Saved status code {status_code}")
            except Attribute.DoesNotExist:
                logger.error(f"DEBUG-API-REQUEST: Status code attribute not found")
        
        # Process response mappings
        if api_success and response_mappings and isinstance(response_data, dict):
            for mapping in response_mappings:
                json_path = mapping.get('jsonPath')
                attribute_id = mapping.get('attributeId')
                
                if not json_path or not attribute_id:
                    continue
                
                try:
                    value = extract_json_path(response_data, json_path)
                    if value is not None:
                        attribute = Attribute.objects.get(id=attribute_id)
                        ContactAttributeValue.objects.update_or_create(
                            contact=contact, 
                            attribute=attribute,
                            defaults={'value': str(value)}
                        )
                        logger.info(f"DEBUG-API-REQUEST: Saved '{value}' from '{json_path}' to '{attribute.name}'")
                except Attribute.DoesNotExist:
                    logger.error(f"DEBUG-API-REQUEST: Attribute {attribute_id} not found")
                except Exception as e:
                    logger.error(f"DEBUG-API-REQUEST: Error processing mapping: {e}")
        
        # Find next node
        edges = flow.flow_data.get('edges', [])
        next_handle = 'onSuccess' if api_success else 'onError'
        next_edge = next((e for e in edges if e.get('source') == target_node_id and e.get('sourceHandle') == next_handle), None)
        
        logger.info(f"DEBUG-API-REQUEST: Looking for '{next_handle}' edge: {next_edge}")
        
        # Continue flow
        if next_edge:
            next_node = next((n for n in flow.flow_data.get('nodes', []) if n.get('id') == next_edge.get('target')), None)
            if next_node:
                logger.info(f"DEBUG-API-REQUEST: Continuing to next node: {next_node.get('id')}")
                UserFlowSession.objects.update_or_create(
                    contact=contact,
                    defaults={'flow': flow, 'current_node_id': target_node_id}
                )
                execute_flow_node(contact, flow, next_node)
            else:
                logger.error(f"DEBUG-API-REQUEST: Next node not found")
                UserFlowSession.objects.filter(contact=contact).delete()
        else:
            logger.info(f"DEBUG-API-REQUEST: No next edge found, ending flow")
            UserFlowSession.objects.filter(contact=contact).delete()
        
        # Don't send WhatsApp message for API node
        return True
    
    elif node_type == 'flowFormNode':
        form_db_id = node_data.get('selectedFormId')
        template_body = node_data.get('templateBody', '')
        button_text = node_data.get('buttonText', 'Open Form')
        
        # if not form_id:
        #     logger.error(f"No form selected for flowFormNode {target_node_id}")
        #     return False
        
        try:
            # Get the form from your database
            from .models import WhatsAppFlowForm  # Adjust import as needed
            flow_form = WhatsAppFlowForm.objects.get(id=form_db_id)
            meta_flow_id = flow_form.meta_flow_id
          
          # Get the ID of the first screen to start the flow
            first_screen_id = "FORM_SCREEN" # A safe default
            if flow_form.screens_data and 'screens_data' in flow_form.screens_data and flow_form.screens_data['screens_data']:
                # --- FIX #2: Access the nested 'screens_data' key ---
                first_screen_id = flow_form.screens_data['screens_data'][0].get('id', first_screen_id)

            # Create the Flow message payload
                payload.update({
                "type": "interactive",
                "interactive": {
                    "type": "flow",
                    "header": {"type": "text", "text": flow_form.name},
                    "body": {"text": template_body or flow_form.template_body},
                    "action": {
                        "name": "flow",
                        "parameters": {
                            "flow_message_version": "3",
                            "flow_id": meta_flow_id,
                            "flow_cta": button_text or flow_form.template_button_text,
                            "flow_action": "navigate",
                            "flow_action_payload": {
                                "screen": first_screen_id
                            }
                        }
                    }
                }
            })
            
            message_type_to_save = 'interactive'
            text_content_to_save = f"Sent Flow Form: {flow_form.name}"
            
            # Set session to wait for flow completion
            UserFlowSession.objects.update_or_create(
                contact=contact,
                defaults={
                    'flow': flow, 
                    'current_node_id': target_node_id,
                    'waiting_for_flow_completion': True,
                    'flow_form_id': meta_flow_id
                }
            )
            
        except WhatsAppFlowForm.DoesNotExist:
            logger.error(f"Flow form with id {meta_flow_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error creating flow form message: {e}")
            return False
    
    else:
        logger.error(f"Message construction for node type '{node_type}' is not implemented.")
        return False

    success, response_data = send_whatsapp_message(payload)

    if success:
        wamid = response_data['messages'][0]['id']
        save_outgoing_message(contact=contact, wamid=wamid, message_type=message_type_to_save, text_content=text_content_to_save, source_node_id=target_node_id)
        
        if node_type not in ['askQuestionNode', 'askLocationNode', 'askForImageNode','askApiNode','flowFormNode']:
            edges = flow.flow_data.get('edges', [])
            target_has_outputs = any(e for e in edges if e.get('source') == target_node_id)
            if target_has_outputs:
                UserFlowSession.objects.update_or_create(
                    contact=contact,
                    defaults={'flow': flow, 'current_node_id': target_node_id, 'waiting_for_attribute': None}
                )
            else:
                 UserFlowSession.objects.filter(contact=contact).delete()
        return True
    
    logger.error(f"Failed to send message via WhatsApp API. Payload: {json.dumps(payload, indent=2)}")
    logger.error(f"Meta API Response: {response_data}")
    return False


def try_execute_status_trigger(wamid, wa_id):
    """Executes a flow step triggered by a 'read' status update."""
    try:
        message = Message.objects.get(wamid=wamid)
        contact = ChatContact.objects.get(wa_id=wa_id)
        session = UserFlowSession.objects.filter(contact=contact).first()
        
        source_node_id = message.source_node_id
        flow = session.flow if session else None

        if not source_node_id and message.message_type == 'template':
            template_name = message.text_content.replace("Sent template: ", "").strip()
            possible_flow = Flow.objects.filter(template_name=template_name, is_active=True).order_by('-updated_at').first()
            if possible_flow:
                flow = possible_flow
                nodes = flow.flow_data.get('nodes', [])
                start_node = next((n for n in nodes if n.get('type') == 'templateNode' and n.get('data', {}).get('selectedTemplateName') == template_name), None)
                if start_node:
                    source_node_id = start_node.get('id')

        if not flow or not source_node_id:
            return False
        
        edges = flow.flow_data.get('edges', [])
        next_edge = next((e for e in edges if e.get('source') == source_node_id and e.get('sourceHandle') == 'onRead'), None)

        if not next_edge:
            return False

        nodes = flow.flow_data.get('nodes', [])
        target_node = next((n for n in nodes if n.get('id') == next_edge.get('target')), None)

        if not target_node:
            return False
            
        return execute_flow_node(contact, flow, target_node)
    except (Message.DoesNotExist, ChatContact.DoesNotExist):
        pass
    except Exception as e:
        logger.error(f"CRITICAL STATUS TRIGGER ERROR: {e}", exc_info=True)
    return False


def try_execute_flow_step(contact, user_input, replied_to_wamid):
    """
    Finds and executes the next step in a flow, with extensive debugging at every stage.
    """
    logger.info(f"--- [START] --- Attempting to execute flow step for contact: {contact.wa_id}")
    logger.info(f"                User Input: '{user_input}', Replied to WAMID: {replied_to_wamid}")

    session = UserFlowSession.objects.filter(contact=contact).first()
    flow = session.flow if session else None
    current_node, next_edge = None, None

    # --- Stage 1: Check for an active session ---
    logger.info("[Stage 1] Checking for an active user session...")
    if session:
        logger.info(f"  [PASS] Active session found. Flow: '{flow.name}', Current Node ID: '{session.current_node_id}'")
        nodes, edges = flow.flow_data.get('nodes', []), flow.flow_data.get('edges', [])
        current_node = next((n for n in nodes if n.get('id') == session.current_node_id), None)
        if current_node:
            logger.info(f"  Found current node in flow data. Type: '{current_node.get('type')}'")
            next_edge = next((e for e in edges if e.get('source') == current_node.get('id') and e.get('sourceHandle') == user_input), None)
            if next_edge:
                logger.info(f"  [SUCCESS] Found a valid next edge from current session: '{current_node.get('id')}' -> '{next_edge.get('target')}' via handle '{user_input}'")
            else:
                logger.warning(f"  [FAIL] No edge found from node '{current_node.get('id')}' with handle '{user_input}'.")
        else:
            logger.error(f"  [CRITICAL] Session points to node '{session.current_node_id}', but it was not found in the flow data!")
    else:
        logger.info("  [INFO] No active session found for this contact.")

    # --- Stage 2: If no path, check historical context ---
    if not next_edge:
        logger.info("[Stage 2] No path from session. Checking historical message context...")
        try:
            original_message = Message.objects.get(wamid=replied_to_wamid, direction='outbound')
            logger.info(f"  Found replied-to message in DB. Source Node ID: '{original_message.source_node_id}'")
            if original_message.source_node_id:
                if not flow:
                    logger.info("  No flow loaded yet. Searching all active flows for the historical node...")
                    active_flows = Flow.objects.filter(is_active=True)
                    for f in active_flows:
                        if any(n.get('id') == original_message.source_node_id for n in f.flow_data.get('nodes', [])):
                            flow = f
                            logger.info(f"  [PASS] Found historical node in flow '{flow.name}'.")
                            break
                if flow:
                    nodes, edges = flow.flow_data.get('nodes', []), flow.flow_data.get('edges', [])
                    current_node = next((n for n in nodes if n.get('id') == original_message.source_node_id), None)
                    if current_node:
                        next_edge = next((e for e in edges if e.get('source') == current_node.get('id') and e.get('sourceHandle') == user_input), None)
                        if next_edge:
                             logger.info(f"  [SUCCESS] Found a valid historical path: '{current_node.get('id')}' -> '{next_edge.get('target')}' via handle '{user_input}'")
                        else:
                            logger.warning(f"  [FAIL] Found historical node, but no edge matches handle '{user_input}'.")
                else:
                    logger.warning("  [FAIL] Historical node ID found, but no active flow contains it.")
            else:
                logger.info("  [INFO] Replied-to message had no source node ID.")
        except Message.DoesNotExist:
            logger.warning("  [FAIL] The replied-to WAMID was not found in the Message database.")

    # --- Stage 3: If still no path, check for a new flow trigger ---
    if not next_edge:
        logger.info("[Stage 3] No historical path found. Checking if this is a trigger for a new flow...")
        try:
            original_message = Message.objects.get(wamid=replied_to_wamid, direction='outbound', message_type='template')
            template_name = original_message.text_content.replace("Sent template: ", "").strip()
            logger.info(f"  Replied-to message is a template: '{template_name}'. Looking for matching flows...")
            possible_flow = Flow.objects.filter(template_name=template_name, is_active=True).order_by('-updated_at').first()
            if possible_flow:
                flow = possible_flow
                logger.info(f"  [PASS] Found matching active flow: '{flow.name}'")
                nodes, edges = flow.flow_data.get('nodes', []), flow.flow_data.get('edges', [])
                current_node = next((n for n in nodes if n.get('type') == 'templateNode' and n.get('data',{}).get('selectedTemplateName') == template_name), None)
                if current_node:
                    next_edge = next((e for e in edges if e.get('source') == current_node.get('id') and e.get('sourceHandle') == user_input), None)
                    if next_edge:
                         logger.info(f"  [SUCCESS] This is a new flow. Path found: '{current_node.get('id')}' -> '{next_edge.get('target')}' via handle '{user_input}'")
                    else:
                        logger.warning(f"  [FAIL] Found trigger template, but no edge matches handle '{user_input}'.")
                else:
                    logger.error("  [CRITICAL] Flow is supposed to be triggered by this template, but no matching start node was found in its data!")
            else:
                logger.info("  [INFO] No active flow is triggered by this template.")
        except Message.DoesNotExist:
            logger.info("  [INFO] Replied-to message is not a trigger template.")
    
    # --- Stage 4: Final check and execution ---
    logger.info("[Stage 4] Final check before execution...")
    if flow and current_node and next_edge:
        logger.info("  [PASS] All components (flow, current_node, next_edge) are valid. Proceeding to execution.")
        target_node = next((n for n in flow.flow_data.get('nodes', []) if n.get('id') == next_edge.get('target')), None)
        if target_node:
            logger.info(f"  Target node found: '{target_node.get('id')}', Type: '{target_node.get('type')}'")
            return execute_flow_node(contact, flow, target_node) # This is where the message is actually sent
        else:
            logger.error(f"  [CRITICAL] Execution failed. The edge points to a target node ID '{next_edge.get('target')}' that does not exist in the flow data.")
            return False
    
    logger.error(f"--- [HALT] --- After all checks, could not determine a valid next step for contact {contact.wa_id} with input '{user_input}'. Flow is stopping.")
    return False


@csrf_exempt
def attribute_list_create_view(request):
    """ API for listing and creating Attributes. """
    if request.method == 'GET':
        attributes = Attribute.objects.all().order_by('name')
        data = [{'id': attr.id, 'name': attr.name, 'description': attr.description} for attr in attributes]
        return JsonResponse(data, safe=False)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        attr = Attribute.objects.create(name=data['name'], description=data.get('description', ''))
        return JsonResponse({'id': attr.id, 'name': attr.name, 'description': attr.description}, status=201)

@csrf_exempt
def attribute_detail_view(request, pk):
    """ API for updating or deleting a specific Attribute. """
    try:
        attr = Attribute.objects.get(pk=pk)
    except Attribute.DoesNotExist:
        return JsonResponse({'error': 'Attribute not found'}, status=404)

    if request.method == 'PUT':
        data = json.loads(request.body)
        attr.name = data.get('name', attr.name)
        attr.description = data.get('description', attr.description)
        attr.save()
        return JsonResponse({'id': attr.id, 'name': attr.name, 'description': attr.description})

    if request.method == 'DELETE':
        attr.delete()
        return JsonResponse({}, status=204)

# --- Webhook and API Views ---
# Add this to your Django views.py file
from .models import WhatsAppFlowForm
from django.utils import timezone
import json


# In contact_app/views.py
from .models import WhatsAppCall # Add this import
from django.views.decorators.http import require_http_methods

# At the top of your views.py file, update your Twilio configuration

import os
from django.conf import settings

# # Twilio Configuration

# Verify credentials are loaded


   # views.py
import json
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
# from twilio.rest import Client
# from twilio.twiml.voice_response import VoiceResponse
import logging

logger = logging.getLogger(__name__)

# Configuration - Add these to your settings.py
ACCESS_TOKEN = 'EAAhMBt21QaMBPCyLtJj6gwjDy6Gai4fZApb3MXuZBZCCm0iSEd8ZCZCJdkRt4cOtvhyeFLZCNUwitFaLZA3ZCwv7enN6FBFgDMAOKl7LMx0J2kCjy6Qd6AqnbnhB2bo2tgsdGmn9ZCN5MD6yCgE3shuP62t1spfSB6ZALy1QkNLvIaeWZBcvPH00HHpyW6US4kil2ENZADL4ZCvDLVWV9seSbZCxXYzVCezIenCjhSYtoKTIlJ'
PHONE_NUMBER_ID = '694609297073147'

# # Twilio Configuration



# Complete fix for your calling system

import json
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
# from twilio.rest import Client
# from twilio.twiml.voice_response import VoiceResponse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration
ACCESS_TOKEN = 'EAAhMBt21QaMBPCyLtJj6gwjDy6Gai4fZApb3MXuZBZCCm0iSEd8ZCZCJdkRt4cOtvhyeFLZCNUwitFaLZA3ZCwv7enN6FBFgDMAOKl7LMx0J2kCjy6Qd6AqnbnhB2bo2tgsdGmn9ZCN5MD6yCgE3shuP62t1spfSB6ZALy1QkNLvIaeWZBcvPH00HHpyW6US4kil2ENZADL4ZCvDLVWV9seSbZCxXYzVCezIenCjhSYtoKTIlJ'
PHONE_NUMBER_ID = '694609297073147'


@csrf_exempt
def whatsapp_webhook_view(request):
    """
    Handles all incoming WhatsApp events from Meta.
    This version correctly processes both messages and status updates in any order.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        logger.info(f"====== INCOMING WEBHOOK ======\n{json.dumps(data, indent=2)}")
        if any('flows' in change.get('value', {}) for entry in data.get('entry', []) for change in entry.get('changes', [])):
            logger.info("DEBUG: FLOWS DATA DETECTED IN WEBHOOK!")
        else:
            logger.info("DEBUG: No flows data in this webhook call")
        
        try:
             for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    
                    # Handle call events
                    if change.get('field') == 'calls':
                        calls = change.get('value', {}).get('calls', [])
                        
                        for call in calls:
                            event = call.get('event')
                            
                            if event == 'connect':
                                success = 'handle_whatsapp_call_connect(call)'
                                if not success:
                                    logger.error(f"Failed to handle call connect: {call.get('id')}")
                                    
                            elif event == 'terminate':
                                "handle_whatsapp_call_terminate(call)"
                                
                    value = change.get('value',{})  # Skip further processing for call webhooks
                    
                    # --- PROCESS MESSAGES ---
                    if 'messages' in value:
                        for msg in value.get('messages', []):
                            contact, _ = ChatContact.objects.get_or_create(wa_id=msg['from'])
                            message_type = msg.get('type')
                            replied_to_wamid = msg.get('context', {}).get('id')
                            user_input = None
                            
                            # Fix the location processing in webhook:
                            if message_type == 'location':
                                location = msg.get('location', {})
                                longitude = location.get('longitude')
                                latitude = location.get('latitude')
                                
                                logger.info(f"DEBUG-LOCATION: Received location from {contact.wa_id}: Long={longitude}, Lat={latitude}")

                                # Check if a session is waiting for this location
                                session = UserFlowSession.objects.filter(contact=contact, is_waiting_for_location=True).first()
                                if session:
                                    logger.info(f"DEBUG-LOCATION: Found session waiting for location: {session}")
                                    
                                    # FIXED: Use the attribute objects directly
                                    # Save longitude attribute
                                    if session.longitude_attribute and longitude is not None:
                                        ContactAttributeValue.objects.update_or_create(
                                            contact=contact, attribute=session.longitude_attribute,
                                            defaults={'value': str(longitude)}
                                        )
                                        logger.info(f"DEBUG-LOCATION: Saved longitude {longitude} to attribute {session.longitude_attribute.name}")
                                        
                                    # Save latitude attribute  
                                    if session.latitude_attribute and latitude is not None:
                                        ContactAttributeValue.objects.update_or_create(
                                            contact=contact, attribute=session.latitude_attribute,
                                            defaults={'value': str(latitude)}
                                        )
                                        logger.info(f"DEBUG-LOCATION: Saved latitude {latitude} to attribute {session.latitude_attribute.name}")
                                    
                                    # Find the next node from the 'onLocationReceived' handle
                                    flow = session.flow
                                    current_node_id = session.current_node_id
                                    edges = flow.flow_data.get('edges', [])
                                    next_edge = next((e for e in edges if e.get('source') == current_node_id and e.get('sourceHandle') == 'onLocationReceived'), None)
                                    
                                    logger.info(f"DEBUG-LOCATION: Looking for next edge from {current_node_id} with handle 'onLocationReceived': {next_edge}")
                                    
                                    # Clear the waiting state
                                    session.is_waiting_for_location = False
                                    session.longitude_attribute = None
                                    session.latitude_attribute = None
                                    session.save()
                                    
                                    if next_edge:
                                        next_node = next((n for n in flow.flow_data.get('nodes', []) if n.get('id') == next_edge.get('target')), None)
                                        logger.info(f"DEBUG-LOCATION: Found next node: {next_node}")
                                        if next_node:
                                            execute_flow_node(contact, flow, next_node)
                                    else:
                                        logger.info("DEBUG-LOCATION: No next edge found, ending flow")
                                        session.delete()
                                else:
                                    logger.info(f"DEBUG-LOCATION: No session found waiting for location for contact {contact.wa_id}")
                                continue

                            # Fix the image processing in webhook:
                            if message_type == 'image':
                                # Get the session first
                                session = UserFlowSession.objects.filter(contact=contact).first()
                                
                                if session and session.waiting_for_image_attribute:
                                    image_id = msg.get('image', {}).get('id')
                                    logger.info(f"DEBUG-IMAGE: Received image from {contact.wa_id}, ID: {image_id}")
                                    
                                    media_url = get_media_url_from_id(image_id)
                                    if media_url:
                                        ContactAttributeValue.objects.update_or_create(
                                            contact=contact, attribute=session.waiting_for_image_attribute,
                                            defaults={'value': media_url}
                                        )
                                        logger.info(f"DEBUG-IMAGE: Saved image URL {media_url} to attribute {session.waiting_for_image_attribute.name}")
                                    else:
                                        logger.error(f"DEBUG-IMAGE: Failed to get media URL for image ID {image_id}")
                                    
                                    # Find next node from 'onImageReceived' handle
                                    flow = session.flow
                                    edges = flow.flow_data.get('edges', [])
                                    next_edge = next((e for e in edges if e.get('source') == session.current_node_id and e.get('sourceHandle') == 'onImageReceived'), None)
                                    
                                    logger.info(f"DEBUG-IMAGE: Looking for next edge with handle 'onImageReceived': {next_edge}")
                                    
                                    # Clear the waiting state
                                    session.waiting_for_image_attribute = None
                                    session.save()
                                    
                                    if next_edge:
                                        next_node = next((n for n in flow.flow_data.get('nodes', []) if n.get('id') == next_edge.get('target')), None)
                                        logger.info(f"DEBUG-IMAGE: Found next node: {next_node}")
                                        if next_node:
                                            execute_flow_node(contact, flow, next_node)
                                    else:
                                        logger.info("DEBUG-IMAGE: No next edge found, ending flow")
                                        session.delete()
                                    continue
                                else:
                                    logger.info(f"DEBUG-IMAGE: No session waiting for image for contact {contact.wa_id}")

                            # 5. ADD TEXT PROCESSING FOR askQuestionNode (INSERT BEFORE EXISTING FLOW LOGIC):
                            if message_type == 'text':
                                user_input = msg.get('text', {}).get('body')
                                logger.info(f"DEBUG-TEXT: Received text message: '{user_input}' from {contact.wa_id}")
                                
                                # FIRST: Check if there's a session waiting for text input (askQuestionNode)
                                session = UserFlowSession.objects.filter(contact=contact, waiting_for_attribute__isnull=False).first()
                                
                                if session and session.waiting_for_attribute:
                                    logger.info(f"DEBUG-QUESTION: Found session waiting for text input. Attribute: {session.waiting_for_attribute.name}")
                                    
                                    # Save the answer to the specified attribute
                                    ContactAttributeValue.objects.update_or_create(
                                        contact=contact, 
                                        attribute=session.waiting_for_attribute,
                                        defaults={'value': user_input}
                                    )
                                    logger.info(f"DEBUG-QUESTION: Successfully saved answer '{user_input}' to attribute '{session.waiting_for_attribute.name}'")
                                    
                                    # Find next node from 'onAnswer' handle
                                    flow = session.flow
                                    edges = flow.flow_data.get('edges', [])
                                    next_edge = next((e for e in edges if e.get('source') == session.current_node_id and e.get('sourceHandle') == 'onAnswer'), None)
                                    
                                    logger.info(f"DEBUG-QUESTION: Looking for next edge with handle 'onAnswer': {next_edge}")
                                    
                                    # Clear the waiting state
                                    session.waiting_for_attribute = None
                                    session.save()
                                    logger.info(f"DEBUG-QUESTION: Cleared waiting_for_attribute state")
                                    
                                    if next_edge:
                                        next_node = next((n for n in flow.flow_data.get('nodes', []) if n.get('id') == next_edge.get('target')), None)
                                        logger.info(f"DEBUG-QUESTION: Found next node: {next_node.get('id') if next_node else 'None'}")
                                        if next_node:
                                            execute_flow_node(contact, flow, next_node)
                                        else:
                                            logger.error(f"DEBUG-QUESTION: Next node not found for target: {next_edge.get('target')}")
                                            session.delete()
                                    else:
                                        logger.info("DEBUG-QUESTION: No next edge found, ending flow")
                                        session.delete()
                                    continue  # Important: Skip further processing for this message
                                
                                else:
                                    logger.info(f"DEBUG-QUESTION: No session waiting for text input from {contact.wa_id}")

                            elif message_type == 'button':
                                user_input = msg.get('button', {}).get('text')
                            elif message_type == 'interactive':
                                interactive = msg.get('interactive', {})
                                if interactive.get('type') == 'list_reply': 
                                    user_input = interactive.get('list_reply', {}).get('id')
                                elif interactive.get('type') == 'button_reply': 
                                    user_input = interactive.get('button_reply', {}).get('title')
                                elif interactive.get('type') == 'nfm_reply':
                                    logger.info(f"DEBUG-FLOW-NFM: Received nfm_reply from {contact.wa_id}")
                                    
                                    # Enhanced debug logging first
                                    enhanced_webhook_debug_logging(data)
                                    
                                    # Process the nfm_reply
                                    success = process_nfm_reply_in_webhook(contact, interactive)
                                    
                                    if success:
                                        logger.info(f"DEBUG-FLOW-NFM: Successfully processed flow completion")
                                        continue  # Skip further processing
                                    else:
                                        logger.error(f"DEBUG-FLOW-NFM: Failed to process flow completion")
                                        continue
                                elif interactive.get('type') == 'call_permission_reply':
                                    call_permission = interactive.get('call_permission_reply', {})
                                    if call_permission.get('response') == 'accept':
                                        logger.info(f"Received call permission from {contact.wa_id}. Triggering outbound call NOW.")
                                        # THIS IS THE MISSING STEP:
                                        initiate_outbound_call(contact.wa_id)
                                    else:
                                        logger.warning(f"User {contact.wa_id} denied call permission.")
                                    continue 

                            logger.info(f"DEBUG-FLOW: Extracted user_input='{user_input}' and replied_to_wamid='{replied_to_wamid}'")
                            flow_handled = False
                            if user_input and replied_to_wamid:
                                flow_handled = try_execute_flow_step(contact, user_input, replied_to_wamid)
                            elif user_input:
                                logger.info(f"User sent input '{user_input}' without replying to a flow message. No action taken.")
                                pass
                                # Go to the next message
                            if flow_handled:
                                logger.info("DEBUG-FLOW: Flow was successfully handled. Skipping fallback logic.")
                                continue

                    # --- PROCESS STATUS UPDATES ---
                    if 'statuses' in value:
                        for status in value.get('statuses', []):
                            if status.get('status') == 'read':
                                try_execute_status_trigger(status.get('id'), status.get('recipient_id'))

        except Exception as e:
            logger.error(f"Error in webhook: {e}", exc_info=True)
            
    return JsonResponse({"status": "success"}, status=200)


from django.http import JsonResponse

def test_view(request):
    return JsonResponse({"status": "ok", "message": "Flow app is working!"})


def get_media_url_from_id(media_id):
    """Uses the Meta API to get a permanent URL for a media object."""
    url = f"{META_API_URL}/{media_id}/"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('url')
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not retrieve media URL for ID {media_id}: {e}")
        return None
    
from .models import WhatsAppFlowForm, Attribute, ContactAttributeValue # Add necessary imports

def handle_flow_completion(contact, response_data):
    """
    Parses the submitted Flow data and saves it to the contact's attributes.
    """
    logger.info(f"=== FLOW COMPLETION DEBUG START ===")
    logger.info(f"Contact: {contact.wa_id}")
    logger.info(f"Response data: {response_data}")
    
    # Find the user's current session to know which flow was just completed
    session = UserFlowSession.objects.filter(contact=contact, waiting_for_flow_completion=True).first()
    logger.info(f"Session found: {session}")
    
    if session:
        logger.info(f"Session flow_form_id: {session.flow_form_id}")
        logger.info(f"Session current_node_id: {session.current_node_id}")
        logger.info(f"Session flow name: {session.flow.name if session.flow else 'None'}")
    
    if not session:
        logger.warning("No session found waiting for flow completion. Cannot map attributes.")
        return

    try:
        # Get the flow form from our database to find its structure
        flow_form = WhatsAppFlowForm.objects.get(meta_flow_id=session.flow_form_id)
        
        # FIXED: Create proper mapping from component ID to attribute
        attribute_map = {}
        screens_data = flow_form.screens_data
        
        # Handle nested structure properly
        if isinstance(screens_data, dict) and 'screens_data' in screens_data:
            screens_list = screens_data['screens_data']
        else:
            screens_list = screens_data if isinstance(screens_data, list) else []

        # Build mapping from component ID to attribute name
        for screen in screens_list:
            for component in screen.get('components', []):
                component_id = component.get('id')
                component_label = component.get('label')
                
                # Map component ID to its label (which should match attribute name)
                if component_id and component_label:
                    attribute_map[component_id] = component_label
                    logger.info(f"Mapped component '{component_id}' to attribute '{component_label}'")

        logger.info(f"Complete attribute map: {attribute_map}")

        # Process the user's submitted data
        saved_count = 0
        for component_id, user_value in response_data.items():
            attribute_name = attribute_map.get(component_id)
            
            if not attribute_name:
                logger.warning(f"No mapping found for component_id '{component_id}'. Skipping.")
                continue

            try:
                # Find the attribute in our database (case-insensitive search)
                attribute_to_save = Attribute.objects.get(name__iexact=attribute_name)
                
                # Handle different data types
                if isinstance(user_value, (list, dict)):
                    value_to_save = json.dumps(user_value)
                else:
                    value_to_save = str(user_value)
                
                # Save the user's submitted value
                ContactAttributeValue.objects.update_or_create(
                    contact=contact,
                    attribute=attribute_to_save,
                    defaults={'value': value_to_save}
                )
                
                logger.info(f"✓ Saved attribute '{attribute_name}' with value '{value_to_save}' for contact {contact.wa_id}")
                saved_count += 1

            except Attribute.DoesNotExist:
                logger.warning(f"Attribute '{attribute_name}' not found in database. Creating it automatically.")
                
                # Auto-create the attribute if it doesn't exist
                try:
                    new_attribute = Attribute.objects.create(
                        name=attribute_name,
                        description=f"Auto-created from form: {flow_form.name}"
                    )
                    
                    value_to_save = json.dumps(user_value) if isinstance(user_value, (list, dict)) else str(user_value)
                    
                    ContactAttributeValue.objects.create(
                        contact=contact,
                        attribute=new_attribute,
                        value=value_to_save
                    )
                    
                    logger.info(f"✓ Created and saved new attribute '{attribute_name}' with value '{value_to_save}'")
                    saved_count += 1
                    
                except Exception as create_error:
                    logger.error(f"Failed to auto-create attribute '{attribute_name}': {create_error}")
                
            except Exception as save_error:
                logger.error(f"Error saving attribute '{attribute_name}': {save_error}")
                
        logger.info(f"Successfully saved {saved_count} attributes from flow completion")
        
        # Find the next node in the visual flow
        flow = session.flow
        current_node_id = session.current_node_id
        edges = flow.flow_data.get('edges', [])

        logger.info(f"=== LOOKING FOR NEXT NODE ===")
        logger.info(f"Current node ID: {current_node_id}")
        logger.info(f"Total edges in flow: {len(edges)}")

        # Look for 'onSuccess' handle first, then fallback to single unnamed edge
        next_edge = next((e for e in edges if e.get('source') == current_node_id and e.get('sourceHandle') == 'onSuccess'), None)
        
        if not next_edge:
            source_edges = [e for e in edges if e.get('source') == current_node_id]
            if len(source_edges) == 1:
                logger.info(f"No 'onSuccess' handle found, using single available edge")
                next_edge = source_edges[0]
        
        # Clear the session BEFORE continuing to next node
        session.delete()
        logger.info("✓ Flow session cleared")

        if next_edge:
            next_node = next((n for n in flow.flow_data.get('nodes', []) if n.get('id') == next_edge.get('target')), None)
            if next_node:
                logger.info(f"✓ Continuing to next node: {next_node.get('id')}")
                execute_flow_node(contact, flow, next_node)
            else:
                logger.warning(f"Next node with ID {next_edge.get('target')} not found in flow data")
        else:
            logger.info(f"✓ Flow completed successfully. No next node found for {current_node_id}")

    except WhatsAppFlowForm.DoesNotExist:
        logger.error(f"Flow form with meta_flow_id '{session.flow_form_id}' not found in database")
    except Exception as e:
        logger.error(f"Error in handle_flow_completion: {e}", exc_info=True)
    
    logger.info(f"=== FLOW COMPLETION DEBUG END ===")
# In your Django views.py, add this endpoint:

@csrf_exempt
def debug_flow_completion(request):
    """Debug endpoint to test flow completion manually"""
    if request.method == 'POST':
        data = json.loads(request.body)
        wa_id = data.get('wa_id')
        response_data = data.get('response_data')
        
        contact = ChatContact.objects.get(wa_id=wa_id)
        handle_flow_completion(contact, response_data)
        
        return JsonResponse({'status': 'success'})
# FIXED: Webhook handler for nfm_reply
def process_nfm_reply_in_webhook(contact, interactive_data):
    """
    Extract and process nfm_reply data from webhook
    """
    logger.info(f"DEBUG-FLOW-NFM: Processing nfm_reply from {contact.wa_id}")
    
    nfm_reply = interactive_data.get('nfm_reply', {})
    response_json_str = nfm_reply.get('response_json', '{}')
    
    logger.info(f"DEBUG-FLOW-NFM: Raw response_json_str = {response_json_str}")
    
    try:
        # Parse the JSON response
        response_json = json.loads(response_json_str)
        logger.info(f"DEBUG-FLOW-NFM: Parsed response_json = {json.dumps(response_json, indent=2)}")
        
        # Call the flow completion handler
        handle_flow_completion(contact, response_json)
        logger.info(f"DEBUG-FLOW-NFM: Successfully processed flow completion")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"DEBUG-FLOW-NFM: Failed to parse response_json: {e}")
        logger.error(f"DEBUG-FLOW-NFM: Raw string was: {repr(response_json_str)}")
        return False
        
    except Exception as e:
        logger.error(f"DEBUG-FLOW-NFM: Error processing nfm_reply: {e}", exc_info=True)
        return False


# ENHANCED: Debug logging for webhook
def enhanced_webhook_debug_logging(data):
    """
    Enhanced logging to debug webhook structure
    """
    logger.info(f"====== ENHANCED WEBHOOK DEBUG ======")
    logger.info(f"Full webhook data: {json.dumps(data, indent=2)}")
    
    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            
            # Log all available keys in the value object
            logger.info(f"Available keys in 'value': {list(value.keys())}")
            
            # Check for messages
            if 'messages' in value:
                for i, msg in enumerate(value['messages']):
                    logger.info(f"Message {i}: type='{msg.get('type')}', keys={list(msg.keys())}")
                    
                    if msg.get('type') == 'interactive':
                        interactive = msg.get('interactive', {})
                        logger.info(f"Interactive type: '{interactive.get('type')}'")
                        logger.info(f"Interactive keys: {list(interactive.keys())}")
                        
                        if interactive.get('type') == 'nfm_reply':
                            nfm_reply = interactive.get('nfm_reply', {})
                            logger.info(f"NFM Reply keys: {list(nfm_reply.keys())}")
                            logger.info(f"Response JSON raw: {repr(nfm_reply.get('response_json'))}")


# INTEGRATION: Updated webhook section for nfm_reply
def handle_nfm_reply_in_webhook(msg, contact):
    """
    Replace the existing nfm_reply handling in your webhook with this
    """
    interactive = msg.get('interactive', {})
    
    if interactive.get('type') == 'nfm_reply':
        logger.info(f"DEBUG-FLOW-NFM: Received nfm_reply from {contact.wa_id}")
        
        # Enhanced debug logging
        enhanced_webhook_debug_logging({'entry': [{'changes': [{'value': {'messages': [msg]}}]}]})
        
        # Process the nfm_reply
        success = process_nfm_reply_in_webhook(contact, interactive)
        
        if success:
            logger.info(f"DEBUG-FLOW-NFM: Successfully processed nfm_reply")
        else:
            logger.error(f"DEBUG-FLOW-NFM: Failed to process nfm_reply")
        
        return True  # Indicate this message was handled
    
    return False  # Not an nfm_reply




from django.shortcuts import get_object_or_404
def flow_form_detail_api(request, form_id):
    """
    Get detailed information about a specific form.
    """
    try:
        form = get_object_or_404(WhatsAppFlowForm, id=form_id)
        
        screens_data = form.screens_data
        if isinstance(screens_data, str):
            try:
                screens_data = json.loads(screens_data)
            except:
                screens_data = []
        
        form_data = {
            'id': str(form.id),
            'name': form.name,
            'template_body': form.template_body,
            'template_button_text': form.template_button_text,
            'template_category': form.template_category,
            'screens_data': screens_data,
            'meta_flow_id': form.meta_flow_id,
            'flow_status': form.flow_status,
            'template_status': form.template_status,
            'created_at': form.created_at.isoformat() if form.created_at else None,
            'updated_at': form.updated_at.isoformat() if form.updated_at else None
        }
        
        return JsonResponse({
            'status': 'success',
            'form': form_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching form detail: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
def update_flow_api(request, flow_id):
    """API endpoint to update an existing flow."""
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            flow = Flow.objects.get(id=flow_id)
            
            # Update fields if provided
            if 'name' in data:
                flow.name = data['name']
            if 'template_name' in data:
                flow.template_name = data['template_name']
            if 'flow' in data:
                flow.flow_data = data['flow']
            if 'is_active' in data:
                flow.is_active = data['is_active']
            
            flow.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Flow updated successfully'
            })
        except Flow.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Flow not found'}, status=404)
        except Exception as e:
            logger.error(f"Error updating flow {flow_id}: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@csrf_exempt
def update_flow_status_api(request, flow_id):
    """API endpoint to toggle the active status of a flow."""
    if request.method == 'POST':
        try:
            flow = Flow.objects.get(pk=flow_id)
            data = json.loads(request.body)
            flow.is_active = data.get('is_active', flow.is_active)
            flow.save()
            return JsonResponse({'status': 'success', 'message': 'Status updated.'})
        except Flow.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Flow not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)



# In your views.py
from .models import WhatsAppFlowForm # Make sure this is imported












def get_whatsapp_forms_api(request):
    """
    API endpoint that returns all saved WhatsApp Flows from the local database.
    This is the single source of truth for your React Flow Builder.
    """
    try:
        forms = WhatsAppFlowForm.objects.all().order_by('-created_at')
        
        forms_data = []
        for form in forms:
            # We map the model fields to the keys the React frontend expects
            forms_data.append({
                'name': form.name,
                'id': form.id,
                'flow_id': form.meta_flow_id,
                'structure': form.screens_data, # Contains the full structure
                
                # We include all other fields for the detailed preview
                'template_category': form.template_category,
                'template_body': form.template_body,
                'template_button_text': form.template_button_text,
                'flow_status': form.flow_status,
                'template_name': form.template_name,
                'template_status': form.template_status,
                'created_at': form.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        return JsonResponse({'status': 'success', 'forms': forms_data})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



def get_flow_details_api_view(request, flow_id):
    """
    API endpoint that fetches the full details of a single WhatsApp Flow from Meta.
    """
    try:
        # Query your new model
        forms = WhatsAppFlowForm.objects.all().order_by('-created_at')
        
        forms_data = []
        for form in forms:
            # We map the model fields to the keys the React frontend expects
            forms_data.append({
                'name': form.name,
                'flow_id': form.meta_flow_id,
                'structure': form.screens_data, # This now contains the full structure
            })

        # The key here is "forms" which your React FlowBuilder expects
        return JsonResponse({'status': 'success', 'forms': forms_data})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
# ... (keep all your other imports: JsonResponse, csrf_exempt, models, etc.)
import logging
logger = logging.getLogger(__name__)

from .models import Flows as Flow


def debug_flow_data(flow_id):
    """Debug utility function to check flow structure."""
    try:
        flow = Flow.objects.get(pk=flow_id)
        print(f"--- Debugging Flow: '{flow.name}' (ID: {flow.id}) ---")
        
        flow_data = flow.flow_data
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])
        
        if not nodes:
            print("This flow has no nodes.")
            return

        print("\nNODES:")
        for node in nodes:
            print(f"- Node ID: {node.get('id')}, Type: {node.get('type')}")
            
        if not edges:
            print("\nThis flow has no edges.")
            return
            
        print("\nEDGES (Connections):")
        for edge in edges:
            print(f"- From Node '{edge.get('source')}' --> To Node '{edge.get('target')}' (Using handle: '{edge.get('sourceHandle')}')")
            
        # Mismatch Check
        print("\nCHECKING FOR MISMATCHES...")
        all_node_ids = {n.get('id') for n in nodes}
        mismatches_found = False
        for edge in edges:
            if edge.get('source') not in all_node_ids:
                print(f"  [!!] MISMATCH FOUND: Edge source '{edge.get('source')}' does not match any known Node ID.")
                mismatches_found = True
            if edge.get('target') not in all_node_ids:
                print(f"  [!!] MISMATCH FOUND: Edge target '{edge.get('target')}' does not match any known Node ID.")
                mismatches_found = True
        
        if not mismatches_found:
            print("  No ID mismatches found between nodes and edges.")
            
    except Flow.DoesNotExist:
        print(f"Error: Flow with ID {flow_id} not found.")


def get_whatsapp_templates_api(request):
    """API endpoint to fetch approved WhatsApp templates for the React frontend."""
    try:
        url = f"https://graph.facebook.com/v19.0/{WABA_ID}/message_templates?fields=name,components,status"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        all_templates = response.json().get('data', [])
        
        templates_data = []
        for t in all_templates:
            if t.get('status') == 'APPROVED':
                buttons = []
                template_components = t.get('components', [])

                # --- THIS IS THE CORRECTED LOGIC ---
                for comp in template_components:
                    # First, find the component with type 'BUTTONS'
                    if comp.get('type') == 'BUTTONS':
                        # Then, loop through the 'buttons' array inside it
                        for btn in comp.get('buttons', []):
                            # Check the type of the INDIVIDUAL button
                            if btn.get('type') == 'QUICK_REPLY':
                                # If it's a quick reply, add it to our list
                                buttons.append({'text': btn.get('text')})

                templates_data.append({
                    'name': t.get('name'),
                    'components': template_components,
                    'buttons': buttons
                })
        
        return JsonResponse(templates_data, safe=False)
    except Exception as e:
        logger.error(f"Failed to fetch templates for API: {e}")
        return JsonResponse({"error": "Could not load templates."}, status=500)


def get_flows_list_api(request):
    """API endpoint to get a list of all saved flows."""
    flows = Flow.objects.all().order_by('-updated_at')
    data = [{
        'id': f.id, 
        'name': f.name, 
        'template_name': f.template_name, 
        'updated_at': f.updated_at.isoformat() if f.updated_at else None,
        'created_at': f.created_at.isoformat() if f.created_at else None,
        'is_active': f.is_active
    } for f in flows]
    return JsonResponse(data, safe=False)



@csrf_exempt
def save_flow_api(request):
    """API endpoint to save a new flow definition from the React frontend."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flow_name = data.get('name')
            trigger_template_name = data.get('template_name')
            flow_data = data.get('flow')
            
            if not all([flow_name, flow_data]):
                return JsonResponse({'status': 'error', 'message': 'Missing flow name or flow data.'}, status=400)

            # Create new flow
            flow_obj = Flow.objects.create(
                name=flow_name,
                template_name=trigger_template_name,
                flow_data=flow_data,
                is_active=True
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Flow created successfully.',
                'flow_id': flow_obj.id
            })
        except Exception as e:
            logger.error(f"Error saving flow: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

# --- UPDATE THIS VIEW ---
def get_flows_list_api(request):
    """API endpoint to get a list of all saved flows."""
    flows = Flow.objects.all().order_by('-updated_at')
    # Add the new is_active field to the response
    data = [{
        'id': f.id, 
        'name': f.name, 
        'template_name': f.template_name, 
        'updated_at': f.updated_at,
        'is_active': f.is_active # <-- NEW
    } for f in flows]
    return JsonResponse(data, safe=False)

# --- ADD THESE THREE NEW VIEWS ---
def get_flow_detail_api(request, flow_id):
    """API endpoint to get the full data for a single flow for editing."""
    try:
        flow = Flow.objects.get(pk=flow_id)
        data = {
            'id': flow.id,
            'name': flow.name,
            'template_name': flow.template_name,
            'flow_data': flow.flow_data,
            'is_active': flow.is_active,
            'created_at': flow.created_at.isoformat() if flow.created_at else None,
            'updated_at': flow.updated_at.isoformat() if flow.updated_at else None,
        }
        return JsonResponse({'status': 'success', 'flow': data})
    except Flow.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Flow not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching flow {flow_id}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def delete_flow_api(request, flow_id):
    """API endpoint to delete a flow."""
    if request.method == 'DELETE':
        try:
            flow = Flow.objects.get(pk=flow_id)
            flow.delete()
            return JsonResponse({'status': 'success', 'message': 'Flow deleted successfully.'})
        except Flow.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Flow not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting flow {flow_id}: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


import requests
import mimetypes # Add this import if not already present
from django.core.files.uploadedfile import InMemoryUploadedFile # Add this import




import google.generativeai as genai

# Configure Gemini API
GEMINI_API_KEY = 'AIzaSyBwgjwmBlcQp2W5pX5UlopmKUOqVjWLcYg'  # Add to settings.py
genai.configure(api_key=GEMINI_API_KEY)




@csrf_exempt
def generate_flow_with_ai(request):
    """
    AI-powered flow generation endpoint.
    Accepts user info and generates an optimal flow.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_info = data.get('user_info', '')
        
        if not user_info:
            return JsonResponse({
                'status': 'error',
                'message': 'User info is required'
            }, status=400)
        
        # Step 1: Fetch all available templates
        templates = fetch_whatsapp_templates()
        if not templates:
            return JsonResponse({
                'status': 'error',
                'message': 'No templates available'
            }, status=400)
        
        # Step 2: Fetch available flow forms
        flow_forms = list(WhatsAppFlowForm.objects.all().values(
            'id', 'name', 'template_body', 'template_button_text',
            'template_category', 'screens_data'
        ))
        
        # Step 3: Fetch available attributes
        attributes = list(Attribute.objects.all().values('id', 'name', 'description'))
        
        # Step 4: Generate flow using Gemini AI
        max_attempts = 3
        generated_flow = None
        
        for attempt in range(max_attempts):
            logger.info(f"AI Generation attempt {attempt + 1}/{max_attempts}")
            
            generated_flow = generate_flow_with_gemini(
                user_info=user_info,
                templates=templates,
                flow_forms=flow_forms,
                attributes=attributes
            )
            
            if generated_flow and validate_generated_flow(generated_flow, templates):
                logger.info("Flow generated and validated successfully")
                break
            else:
                logger.warning(f"Attempt {attempt + 1} failed validation")
                generated_flow = None
        
        if not generated_flow:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate flow'
            }, status=500)
        
        # Step 5: Create missing attributes if needed
        created_attributes = create_missing_attributes(generated_flow)
        if created_attributes:
            logger.info(f"Auto-created {len(created_attributes)} attributes: {created_attributes}")
        
        # Step 6: Save the generated flow to database
        flow_obj = Flow.objects.create(
            name=generated_flow['name'],
            template_name=generated_flow['template_name'],
            flow_data=generated_flow['flow_data'],
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Flow generated successfully',
            'flow': {
                'id': flow_obj.id,
                'name': flow_obj.name,
                'template_name': flow_obj.template_name,
                'explanation': generated_flow.get('explanation', ''),
                'flow_data': generated_flow['flow_data'],
                'created_attributes': created_attributes
            }
        })
        
    except Exception as e:
        logger.error(f"Error in AI flow generation: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


import json
import logging
import requests
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai

logger = logging.getLogger(__name__)

@csrf_exempt
def generate_multiple_templates(request):
    """
    Generates 3-4 template options based on user requirements.
    Includes existing templates if they match the requirements.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        requirements = data.get('requirements', '')
        
        if not requirements:
            return JsonResponse({
                'status': 'error',
                'message': 'Requirements are needed'
            }, status=400)
        
        # Fetch existing templates
        # existing_templates = fetch_whatsapp_templates()
        
        # Generate multiple template options
        template_options = generate_template_options_with_ai(requirements)
        
        if not template_options:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate template options'
            }, status=500)
        
        return JsonResponse({
            'status': 'success',
            'templates': template_options
        })
        
    except Exception as e:
        logger.error(f"Error generating templates: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def generate_template_options_with_ai(requirements):
    """
    Uses Gemini to generate 3-4 template variations based on requirements.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
You are a WhatsApp Business API template expert. Generate 3-4 different template options based on user requirements.

USER REQUIREMENTS:
{requirements}



META'S TEMPLATE GUIDELINES:
- UTILITY category: Transactional, account updates, order status
- MARKETING category: Promotional offers, announcements
- Variables: {{{{1}}}}, {{{{2}}}} for personalization
- Body: Max 1024 characters
- Header: Optional (TEXT, IMAGE, VIDEO, DOCUMENT)
- Footer: Optional (max 60 characters)
- Buttons: Max 3 QUICK_REPLY or 2 CALL_TO_ACTION buttons
- Language: en, hi, es, pt_BR, etc.

TASK:
1. Check if any EXISTING template matches requirements (include 1 if found)
2. Generate 2-3 NEW template variations:
   - Variation A: Simple text-only (no media)
   - Variation B: With IMAGE header (suggest but mark as optional)
   - Variation C: More detailed version with buttons

OUTPUT FORMAT (JSON):
{{
  "templates": [
    {{
      "id": "generated_1",
      "source": "generated",
      "name": "template_name_lowercase_underscores",
      "language": "hi" or "en",
      "category": "UTILITY" or "MARKETING",
      "match_score": 85 (only for existing),
      "description": "Brief description of this template option",
      "has_media": false,
      "media_type": null or "IMAGE" or "VIDEO",
      "media_optional": true/false,
      "components": [
        {{
          "type": "HEADER",
          "format": "TEXT" or "IMAGE",
          "text": "हेडर मजकूर" (if TEXT),
          "optional": false
        }},
        {{
          "type": "BODY",
          "text": "नमस्कार {{{{1}}}},\\n\\nमुख्य मजकूर येथे...",
          "example": {{
            "body_text": [["उदाहरण १", "उदाहरण २"]]
          }}
        }},
        {{
          "type": "FOOTER",
          "text": "फूटर मजकूर",
          "optional": true
        }},
        {{
          "type": "BUTTONS",
          "buttons": [
            {{"type": "QUICK_REPLY", "text": "बटण १"}},
            {{"type": "QUICK_REPLY", "text": "बटण २"}}
          ],
          "optional": true
        }}
      ],
      "variables_needed": [
        {{"name": "farmer_name", "description": "शेतकऱ्याचे नाव", "example": "राजू पाटील", "position": 1}},
        {{"name": "location", "description": "स्थान", "example": "नाशिक", "position": 2}}
      ],
      "pros": ["फायदा १", "फायदा २"],
      "cons": ["तोटा १", "तोटा २"]
    }}
  ]
}}

IMPORTANT RULES:
1. Use Marathi देवनागरी for Indian farmers
2. Include personalization {{{{1}}}}, {{{{2}}}} with examples
3. Professional but friendly tone
4. Mark media and optional components clearly
5. Provide pros/cons for each option
6. Generate ONLY valid JSON, no markdown.
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        result = json.loads(response_text)
        return result.get('templates', [])
        
    except Exception as e:
        logger.error(f"Error in template generation: {e}", exc_info=True)
        return None


@csrf_exempt
def submit_customized_template(request):
    """
    Submits user-customized template to Meta.
    Handles dynamic media addition/removal.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    
    try:
        # Parse multipart or JSON
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            template_data_str = request.POST.get('template_data')
            media_file = request.FILES.get('media_file')
        else:
            body_data = json.loads(request.body)
            template_data_str = body_data.get('template_data')
            media_file = None

        if not template_data_str:
            return JsonResponse({
                'status': 'error', 
                'message': 'template_data is missing'
            }, status=400)
        
        template_data = json.loads(template_data_str)
        
        # Check if user wants to remove media
        remove_media = template_data.get('remove_media', False)
        
        # Upload media if provided
        media_id = None
        if media_file and not remove_media:
            media_id = upload_media_to_meta(media_file)
            if not media_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Media upload failed'
                }, status=500)
        
        # Build Meta API payload dynamically
        meta_payload = build_meta_payload(template_data, media_id, remove_media)
        
        # Submit to Meta
        url = f"https://graph.facebook.com/v23.0/{WABA_ID}/message_templates"
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Submitting to Meta: {json.dumps(meta_payload, indent=2)}")
        response = requests.post(url, json=meta_payload, headers=headers)
        response_data = response.json()
        
        logger.info(f"Meta Response: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200 and 'id' in response_data:
            return JsonResponse({
                'status': 'success',
                'message': 'Template submitted for approval',
                'template_id': response_data.get('id'),
                'template_name': template_data.get('name'),
                'meta_response': response_data
            })
        else:
            error_details = response_data.get('error', {})
            error_message = error_details.get('message', 'Submission failed')
            
            return JsonResponse({
                'status': 'error',
                'message': error_message,
                'meta_response': response_data,
                'suggestion': get_fix_suggestion(error_details)
            }, status=response.status_code)
            
    except Exception as e:
        logger.error(f"Error submitting template: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def build_meta_payload(template_data, media_id, remove_media):
    """
    Dynamically builds Meta API payload based on user customizations.
    """
    meta_payload = {
        "name": template_data['name'],
        "category": template_data['category'],
        "language": template_data['language'],
        "components": []
    }
    
    for component in template_data['components']:
        # Skip optional components if user removed them
        if component.get('removed', False):
            continue
        
        meta_component = {"type": component['type']}
        
        if component['type'] == 'HEADER':
            meta_component['format'] = component.get('format', 'IMAGE')
            
            # If user removed media, skip HEADER with media
           
            
        if component['format'] == 'TEXT':
            meta_component['text'] = component.get('text', '')

        elif component['type'] == 'BODY':
            body_text = component['text']
            meta_component['text'] = body_text
            
            # Extract variables
            variables = re.findall(r'\{\{(\d+)\}\}', body_text)
            
            if variables and 'example' in component:
                example_values = component['example'].get('body_text', [[]])[0]
                if example_values:
                    meta_component['example'] = {'body_text': [example_values]}
        
        elif component['type'] == 'FOOTER':
            meta_component['text'] = component.get('text', '')
        
        elif component['type'] == 'BUTTONS':
            buttons = component.get('buttons', [])
            if buttons:  # Only add if buttons exist
                meta_component['buttons'] = buttons
        
        meta_payload['components'].append(meta_component)
    
    return meta_payload


@csrf_exempt
def upload_image_to_meta_api(request):
    """
    API endpoint to upload an image file directly to Meta's WhatsApp Business API
    and return the Meta Media ID.
    """
    if request.method == 'POST':
        if 'image' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No image file provided.'}, status=400)

        image_file: InMemoryUploadedFile = request.FILES['image']
        
        # Determine content type (e.g., image/jpeg, image/png)
        content_type, _ = mimetypes.guess_type(image_file.name)
        if not content_type or not content_type.startswith('image/'):
            return JsonResponse({'status': 'error', 'message': 'Invalid file type. Only images are allowed.'}, status=400)

        upload_url = f"{META_API_URL}/{PHONE_NUMBER_ID}/media"
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        }
        files = {
            'file': (image_file.name, image_file.read(), content_type),
            'type': (None, content_type), # Important for Meta API
            'messaging_product': (None, 'whatsapp'),
        }

        try:
            response = requests.post(upload_url, headers=headers, files=files)
            response.raise_for_status() # Raise an exception for HTTP errors
            meta_response = response.json()
            
            media_id = meta_response.get('id')
            if media_id:
                logger.info(f"Image uploaded to Meta, Media ID: {media_id}")
                return JsonResponse({'status': 'success', 'media_id': media_id})
            else:
                logger.error(f"Meta upload response missing media ID: {meta_response}")
                return JsonResponse({'status': 'error', 'message': 'Meta did not return a media ID.'}, status=500)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error uploading image to Meta: {e}. Response: {response.text if 'response' in locals() else 'No response.'}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'Failed to upload image to Meta: {e}'}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error in upload_image_to_meta_api: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {e}'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)




def fetch_whatsapp_templates():
    """Fetch approved templates from Meta."""
    try:
        url = f"{META_API_URL}/{WABA_ID}/message_templates"
        params = {"fields": "name,components,status,language,category"}
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        all_templates = response.json().get('data', [])
        approved_templates = [t for t in all_templates if t.get('status') == 'APPROVED']
        
        return approved_templates
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        return []


def get_fix_suggestion(error_details):
    """Provides actionable fix suggestions."""
    error_msg = error_details.get('error_user_msg', '').lower()
    
    if 'body_text' in error_msg and 'example' in error_msg:
        return "Add example values for all variables in body text"
    elif 'header_handle' in error_msg:
        return "Upload media file and ensure media ID is valid"
    elif 'category' in error_msg:
        return "Specify valid category: UTILITY or MARKETING"
    elif 'language' in error_msg:
        return "Specify valid language code: en, hi, es, etc."
    else:
        return "Check Meta's template documentation for details"



@csrf_exempt
def analyze_and_generate_template(request):
    """
    Analyzes user requirements and either suggests existing template
    or generates a new template that meets Meta's approval guidelines.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_requirements = data.get('requirements', '')
        
        if not user_requirements:
            return JsonResponse({
                'status': 'error',
                'message': 'Requirements are needed'
            }, status=400)
        
        # Step 1: Fetch existing templates
        # existing_templates = fetch_whatsapp_templates()
        
        # Step 2: Analyze with Gemini
        analysis = analyze_requirements_with_ai(user_requirements)
        
        if not analysis:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to analyze requirements'
            }, status=500)
        
        # Step 3: Return analysis with recommendation
        return JsonResponse({
            'status': 'success',
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error in template analysis: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
def submit_template_to_meta(request):
    """
    Submits the approved template design to Meta for review.
    Handles media upload if needed. Uses correct Meta API v23.0 format.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    
    try:
        # Check if it's multipart (with image) or JSON only
        if request.content_type.startswith('multipart/form-data'):
            # Has image upload
            template_data_str = request.POST.get('template_data')
            media_file = request.FILES.get('media_file')
        else:
            # JSON only (no image)
            body_data = json.loads(request.body)
            template_data_str = body_data.get('template_data')
            media_file = None

        if not template_data_str:
            return JsonResponse({
                'status': 'error', 
                'message': 'template_data is missing'
            }, status=400)
        
        template_data = json.loads(template_data_str)
        
        # Upload media to Meta if provided
        media_id = None
        if media_file:
            media_id = upload_media_to_meta(media_file)
            if not media_id:
                logger.warning("Media upload failed, proceeding without header image")
        
        # Build Meta API v23.0 compliant payload
        meta_payload = {
            "name": template_data['name'],
            "category": template_data['category'],
            "language": template_data['language'],
            "components": []
        }
        
        # Process components for Meta API format
        for component in template_data['components']:
            meta_component = {"type": component['type']}
            
            if component['type'] == 'HEADER':
                meta_component['format'] = component.get('format', 'IMAGE')
                
                if component['format'] == 'TEXT':
                    meta_component['text'] = component.get('text', '')
                
            
            elif component['type'] == 'BODY':
                body_text = component['text']
                meta_component['text'] = body_text
                
                import re
                variables = re.findall(r'\{\{(\d+)\}\}', body_text)
                
                if variables and 'example' in component:
                    example_values = component['example'].get('body_text', [[]])[0]
                    if example_values:
                        meta_component['example'] = {'body_text': [example_values]}
            
            elif component['type'] == 'FOOTER':
                meta_component['text'] = component.get('text', '')
            
            elif component['type'] == 'BUTTONS':
                meta_component['buttons'] = component.get('buttons', [])
            
            meta_payload['components'].append(meta_component)
        
        # Submit to Meta API
        url = f"https://graph.facebook.com/v23.0/{WABA_ID}/message_templates"
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Submitting to Meta: {json.dumps(meta_payload, indent=2)}")
        response = requests.post(url, json=meta_payload, headers=headers)
        response_data = response.json()
        
        logger.info(f"Meta Response: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200 and 'id' in response_data:
            return JsonResponse({
                'status': 'success',
                'message': 'Template submitted for approval',
                'template_id': response_data.get('id'),
                'template_name': template_data.get('name'),
                'meta_response': response_data
            })
        else:
            error_details = response_data.get('error', {})
            error_message = error_details.get('message', 'Submission failed')
            logger.error(f"Meta Error: {json.dumps(error_details, indent=2)}")
            
            return JsonResponse({
                'status': 'error',
                'message': error_message,
                'meta_response': response_data,
            }, status=response.status_code)
            
    except Exception as e:
        logger.error(f"Error submitting template: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)



def upload_media_to_meta(media_file):
    """
    Uploads an image/media file to Meta and returns the media ID.
    """
    try:
        url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/media"
        
        files = {
            'file': (media_file.name, media_file, media_file.content_type),
        }
        
        data = {
            'messaging_product': 'whatsapp',
            'type': media_file.content_type.split('/')[0]  # 'image', 'video', etc.
        }
        
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        }
        
        logger.info(f"Uploading media: {media_file.name}, type: {media_file.content_type}")
        
        response = requests.post(url, files=files, data=data, headers=headers)
        response_data = response.json()
        
        logger.info(f"Media upload response: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200 and 'id' in response_data:
            return response_data['id']
        else:
            logger.error(f"Media upload failed: {response_data}")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading media: {e}", exc_info=True)
        return None

def analyze_requirements_with_ai(requirements):
    """
    Uses Gemini to analyze requirements and decide whether to use existing
    template or generate a new one.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
You are a WhatsApp Business API template expert. Analyze the user's requirements and decide:
1. Can an existing approved template be used?
2. Or should a new template be created?

USER REQUIREMENTS:
{requirements}


META'S TEMPLATE APPROVAL GUIDELINES:
- Templates must provide value to users
- No promotional content in UTILITY category
- Use MARKETING category for promotional content
- Variables {{{{1}}}}, {{{{2}}}} etc. for dynamic content
- Keep body under 1024 characters
- Header optional (TEXT, IMAGE, VIDEO, or DOCUMENT)
- Footer optional (up to 60 characters)
- Buttons optional (max 3 quick reply buttons OR 2 call-to-action buttons)
- Language must be specified (en, hi, es, etc.)

DECISION TASK:
If an existing template is suitable, recommend it.
If not, generate a NEW template following Meta's guidelines.

OUTPUT FORMAT (JSON):
{{
  "recommendation": "use_existing" or "create_new",
  "reasoning": "Why this decision was made",
  "existing_template": "template_name" (if use_existing),
  "new_template": {{
    "name": "descriptive_lowercase_with_underscores",
    "language": "hi" (for Marathi/Hindi) or "en",
    "category": "UTILITY" or "MARKETING",
    "components": [
      {{
        "type": "HEADER",
        "format": "TEXT" or "IMAGE",
        "text": "⭐ हेडर मजकूर" (if TEXT format)
      }},
      {{
        "type": "BODY",
        "text": "⭐ नमस्कार {{{{1}}}},\n\nआम्ही {{{{2}}}} मधील द्राक्ष उत्पादक शेतकऱ्यांसाठी कुशल मजूर थेट उपलब्ध करून देण्यासाठी एक नवीन लेबर प्लॅटफॉर्म सुरू केले आहे.\n\n🍇 आमच्या प्रशिक्षित टीम्स सप्टेंबर छाटणी हंगामासाठी सज्ज आहेत – बांधणी, डिपिंग, पातळणी, घड निवड आणि आणखी बरेच काही.\n\n✅ कुशल आणि विश्वासार्ह मजूर\n✅ संपूर्ण सेवा आमच्याकडून व्यवस्थापित\n✅ तुमच्यासाठी कोणताही त्रास नाही\n\nइच्छुक असल्यास खाली क्लिक करा 👇👇👇",
        "example": {{
          "body_text": [["शेतकरी नाव", "तालुका नाव"]]
        }}
      }},
      {{
        "type": "BUTTONS",
        "buttons": [
          {{
            "type": "QUICK_REPLY",
            "text": "मजूर हवे आहेत"
          }},
          {{
            "type": "QUICK_REPLY",
            "text": "सेवा पहा"
          }}
        ]
      }}
    ]
  }} (if create_new),
  "variables_needed": [
    {{"name": "farmer_name", "description": "शेतकऱ्याचे नाव", "example": "राजू पाटील"}},
    {{"name": "location", "description": "तालुका/गाव", "example": "नाशिक"}}
  ],
  "needs_media": true/false,
  "media_type": "image" (if needs_media),
  "suggested_flow": {{
    "description": "Flow काय करेल",
    "steps": ["स्टेप 1", "स्टेप 2", "स्टेप 3"]
  }}
}}
TEMPLATE WRITING GUIDELINES:
1. Use Marathi देवनागरी script (not English)
2. ALWAYS include personalization variables {{1}}, {{2}} etc.
   - {{1}} for farmer name
   - {{2}} for location/village
   - Use these in the greeting!
3. Start with ⭐ नमस्कार {{1}},
4. Write 4-6 lines in body (detailed, not short)
5. Mention specific services: बांधणी, डिपिंग, पातळणी, घड निवड
6. Use bullet points with ✅ for benefits
7. End with call-to-action: "इच्छुक असल्यास खाली क्लिक करा 👇"
8. Professional farmer language
9. Button text in Marathi: "मजूर हवे आहेत", "सेवा पहा", "संपर्क करा"
10. CRITICAL: If you use {{1}}, MUST provide example like ["राजू पाटील"]
11. If you use {{1}} and {{2}}, MUST provide examples like ["राजू पाटील", "नाशिक"]

EXAMPLE WITH VARIABLES (CORRECT):
Body: "⭐ नमस्कार {{1}},\n\nआम्ही {{2}} मधील शेतकऱ्यांसाठी..."
Example: {{"body_text": [["राजू पाटील", "नाशिक"]]}}

NO VARIABLES = NO EXAMPLE FIELD (also acceptable but less personal)

Generate ONLY valid JSON, no markdown.
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        analysis = json.loads(response_text)
        return analysis
        
    except Exception as e:
        logger.error(f"Error in AI analysis: {e}", exc_info=True)
        return None
@csrf_exempt
def upload_media_to_meta_api(request):
    """
    API endpoint to upload any media file (image, video, document, etc.) 
    directly to Meta's WhatsApp Business API and return the Meta Media ID.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    if 'media' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'No media file provided.'}, status=400)

    media_file = request.FILES['media']
    media_id = upload_media_to_meta_helper(media_file)
    
    if not media_id:
        return JsonResponse({'status': 'error', 'message': 'Media upload failed'}, status=500)

    return JsonResponse({'status': 'success', 'media_id': media_id})

def upload_media_to_meta_helper(media_file):
    """
    Helper function (non-view) to upload a file to Meta and return its media_id.
    Can be used internally in other views.
    """
    try:
        content_type, _ = mimetypes.guess_type(media_file.name)
        if not content_type:
            logger.error("Could not determine file type for upload.")
            return None

        upload_url = f"{META_API_URL}/{PHONE_NUMBER_ID}/media"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        files = {
            'file': (media_file.name, media_file.read(), content_type),
            'type': (None, content_type),
            'messaging_product': (None, 'whatsapp'),
        }

        response = requests.post(upload_url, headers=headers, files=files)
        logger.info(f"Meta upload response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            return data.get('id')
        else:
            logger.error(f"Meta upload failed ({response.status_code}): {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error in upload_media_to_meta_helper: {e}", exc_info=True)
        return None

# @csrf_exempt
# def upload_media_to_meta_api(request):
#     """
#     API endpoint to upload any media file (image, video, document, etc.) 
#     directly to Meta's WhatsApp Business API and return the Meta Media ID.
#     """
#     if request.method == 'POST':
#         # The key for the file in the form data should be 'media'
#         if 'media' not in request.FILES:
#             return JsonResponse({'status': 'error', 'message': 'No media file provided.'}, status=400)

#         media_file: InMemoryUploadedFile = request.FILES['media']
        
#         # Determine the file's content type (e.g., 'image/jpeg', 'application/pdf')
#         content_type, _ = mimetypes.guess_type(media_file.name)
#         if not content_type:
#             return JsonResponse({'status': 'error', 'message': 'Could not determine the file type.'}, status=400)

#         upload_url = f"{META_API_URL}/{PHONE_NUMBER_ID}/media"
#         headers = {
#             "Authorization": f"Bearer {META_ACCESS_TOKEN}",
#         }
#         files = {
#             'file': (media_file.name, media_file.read(), content_type),
#             'type': (None, content_type),  # Important for Meta API
#             'messaging_product': (None, 'whatsapp'),
#         }

#         try:
#             response = requests.post(upload_url, headers=headers, files=files)
#             response.raise_for_status()  # Raise an exception for HTTP errors (like 4xx or 5xx)
#             meta_response = response.json()
            
#             media_id = meta_response.get('id')
#             if media_id:
#                 logger.info(f"Media uploaded to Meta, Media ID: {media_id}")
#                 return JsonResponse({'status': 'success', 'media_id': media_id})
#             else:
#                 logger.error(f"Meta upload response missing media ID: {meta_response}")
#                 return JsonResponse({'status': 'error', 'message': 'Meta did not return a media ID.'}, status=500)

#         except requests.exceptions.RequestException as e:
#             logger.error(f"Error uploading media to Meta: {e}. Response: {e.response.text if e.response else 'No response.'}", exc_info=True)
#             return JsonResponse({'status': 'error', 'message': f'Failed to upload media to Meta: {e}'}, status=500)
#         except Exception as e:
#             logger.error(f"Unexpected error in upload_media_to_meta_api: {e}", exc_info=True)
#             return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {e}'}, status=500)

#     return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@csrf_exempt
def upload_image_to_meta_api(request):
    """
    API endpoint to upload an image file directly to Meta's WhatsApp Business API
    and return the Meta Media ID.
    """
    if request.method == 'POST':
        if 'image' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No image file provided.'}, status=400)

        image_file: InMemoryUploadedFile = request.FILES['image']
        
        # Determine content type (e.g., image/jpeg, image/png)
        content_type, _ = mimetypes.guess_type(image_file.name)
        if not content_type or not content_type.startswith('image/'):
            return JsonResponse({'status': 'error', 'message': 'Invalid file type. Only images are allowed.'}, status=400)

        upload_url = f"{META_API_URL}/{PHONE_NUMBER_ID}/media"
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        }
        files = {
            'file': (image_file.name, image_file.read(), content_type),
            'type': (None, content_type), # Important for Meta API
            'messaging_product': (None, 'whatsapp'),
        }

        try:
            response = requests.post(upload_url, headers=headers, files=files)
            response.raise_for_status() # Raise an exception for HTTP errors
            meta_response = response.json()
            
            media_id = meta_response.get('id')
            if media_id:
                logger.info(f"Image uploaded to Meta, Media ID: {media_id}")
                return JsonResponse({'status': 'success', 'media_id': media_id})
            else:
                logger.error(f"Meta upload response missing media ID: {meta_response}")
                return JsonResponse({'status': 'error', 'message': 'Meta did not return a media ID.'}, status=500)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error uploading image to Meta: {e}. Response: {response.text if 'response' in locals() else 'No response.'}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'Failed to upload image to Meta: {e}'}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error in upload_image_to_meta_api: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {e}'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@csrf_exempt
def check_template_status(request, template_name):
    """
    Checks the approval status of a template.
    """
    try:
        url = f"{META_API_URL}/{WABA_ID}/message_templates"
        params = {
            'name': template_name,
            'fields': 'name,status,id'
        }
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        templates = response.json().get('data', [])
        if templates:
            template = templates[0]
            return JsonResponse({
                'status': 'success',
                'template_status': template.get('status'),
                'template_id': template.get('id'),
                'template_name': template.get('name')
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Template not found'
            }, status=404)
        
    except Exception as e:
        logger.error(f"Error checking template status: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
def auto_create_flow_after_approval(request):
    """
    Automatically creates a flow once the template is approved.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        template_name = data.get('template_name')
        original_requirements = data.get('original_requirements')
        suggested_flow = data.get('suggested_flow')
        
        if not all([template_name, original_requirements]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required data'
            }, status=400)
        
        # Fetch all available resources
        templates = fetch_whatsapp_templates()
        flow_forms = list(WhatsAppFlowForm.objects.all().values(
            'id', 'name', 'template_body', 'template_button_text',
            'template_category', 'screens_data'
        ))
        attributes = list(Attribute.objects.all().values('id', 'name', 'description'))
        
        # Generate flow with the new template
        flow_requirements = f"""
Original Requirements: {original_requirements}

Suggested Flow Structure: {json.dumps(suggested_flow, indent=2)}

IMPORTANT: Use template '{template_name}' as the first node (trigger).
Build the complete flow based on the original requirements and suggested structure.
"""
        
        generated_flow = generate_flow_with_gemini(
            user_info=flow_requirements,
            templates=templates,
            flow_forms=flow_forms,
            attributes=attributes
        )
        
        if not generated_flow:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate flow'
            }, status=500)
        
        # Validate and create attributes
        if not validate_generated_flow(generated_flow, templates):
            return JsonResponse({
                'status': 'error',
                'message': 'Generated flow validation failed'
            }, status=500)
        
        created_attributes = create_missing_attributes(generated_flow)
        
        # Save flow
        flow_obj = Flow.objects.create(
            name=generated_flow['name'],
            template_name=generated_flow['template_name'],
            flow_data=generated_flow['flow_data'],
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Flow created successfully',
            'flow': {
                'id': flow_obj.id,
                'name': flow_obj.name,
                'template_name': flow_obj.template_name,
                'explanation': generated_flow.get('explanation', ''),
                'flow_data': generated_flow['flow_data'],
                'created_attributes': created_attributes
            }
        })
        
    except Exception as e:
        logger.error(f"Error auto-creating flow: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# def fetch_whatsapp_templates():
#     """Fetch approved WhatsApp templates from Meta API."""
#     try:
#         url = f"{META_API_URL}/{WABA_ID}/message_templates"
#         params = {"fields": "name,components,status,language,category"}
#         headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        
#         response = requests.get(url, headers=headers, params=params)
#         response.raise_for_status()
        
#         all_templates = response.json().get('data', [])
#         approved_templates = [t for t in all_templates if t.get('status') == 'APPROVED']
        
#         processed_templates = []
#         for t in approved_templates:
#             buttons = []
#             for comp in t.get('components', []):
#                 if comp.get('type') == 'BUTTONS':
#                     for btn in comp.get('buttons', []):
#                         if btn.get('type') == 'QUICK_REPLY':
#                             buttons.append({'text': btn.get('text')})
            
#             processed_templates.append({
#                 'name': t.get('name'),
#                 'components': t.get('components', []),
#                 'buttons': buttons,
#                 'language': t.get('language', 'en'),
#                 'category': t.get('category', 'UTILITY')
#             })
        
#         return processed_templates
#     except Exception as e:
#         logger.error(f"Error fetching templates: {e}")
#         return []


# def get_fix_suggestion(error_details):
#     """Provides actionable fix suggestions based on Meta API error."""
#     error_msg = error_details.get('error_user_msg', '').lower()
    
#     if 'body_text' in error_msg and 'example' in error_msg:
#         return "Add example values: If text has {{1}} and {{2}}, add example: {'body_text': [['Example1', 'Example2']]}"
#     elif 'header_handle' in error_msg:
#         return "Upload image/video first and use the returned media ID in header_handle"
#     elif 'category' in error_msg:
#         return "Add 'category': 'UTILITY' or 'MARKETING' to template"
#     elif 'language' in error_msg:
#         return "Add 'language': 'hi' for Marathi or 'en' for English"
#     elif 'button' in error_msg:
#         return "Check button text (max 20 chars) and ensure type is 'QUICK_REPLY'"
#     else:
#         return "Check Meta's template requirements: https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates"



def generate_flow_with_gemini(user_info, templates, flow_forms, attributes):
    """
    Use Gemini AI to analyze user info and generate optimal flow.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Create the prompt for Gemini
        prompt = f"""
You are an expert WhatsApp chatbot flow designer. Analyze the user requirements and create an optimal conversation flow.

USER REQUIREMENTS:
{user_info}

AVAILABLE WHATSAPP TEMPLATES:
{json.dumps(templates, indent=2)}

AVAILABLE FLOW FORMS (Pre-built forms):
{json.dumps(flow_forms, indent=2)}

AVAILABLE ATTRIBUTES (For storing user data):
{json.dumps(attributes, indent=2)}

IMPORTANT NODE TYPE USAGE RULES:

1. **askQuestionNode**: Use this to ask the user ANY question and save their text response
   - ALWAYS set "questionText" with the question you want to ask
   - ALWAYS set "saveAttributeId" to an attribute ID from the available attributes list
   - If no suitable attribute exists, use the attribute name (e.g., "user_name", "email", "phone_number") - the system will create it
   - Example data: {{"questionText": "What is your email address?", "saveAttributeId": "email"}}

2. **askLocationNode**: Use to request location and save coordinates
   - Set "questionText" with the location request message
   - Set "longitudeAttributeId" and "latitudeAttributeId" with attribute IDs or names
   - Example: {{"questionText": "Share your location", "longitudeAttributeId": "user_longitude", "latitudeAttributeId": "user_latitude"}}

3. **askForImageNode**: Use to request an image from user
   - Set "questionText" with the image request message
   - Set "saveAttributeId" to store the image URL
   - Example: {{"questionText": "Upload a photo of the document", "saveAttributeId": "document_image"}}

4. **textNode**: Use ONLY for sending information, NOT for asking questions
   - Set "text" with the message content
   - Use for confirmations, instructions, or information delivery
   - Example: {{"text": "Thank you! We have received your information."}}

5. **buttonsNode**: Use to present choices with buttons
   - Set "text" with the message
   - Set "buttons" array with button objects
   - Example: {{"text": "Choose an option:", "buttons": [{{"text": "Option 1"}}, {{"text": "Option 2"}}]}}

6. **flowFormNode**: Use to trigger WhatsApp Flow forms
   - Set "selectedFormId" to a form ID from available forms
   - Forms handle complex data collection
   - Use when you need structured multi-field forms

7. **askApiNode**: Use to make external API calls
   - Set "method" (GET, POST, etc.)
   - Set "apiUrl" with the endpoint
   - Set "responseMappings" to save API response data to attributes

CRITICAL RULES:
- DO NOT use textNode for questions - use askQuestionNode, askLocationNode, or askForImageNode
- ALWAYS set questionText when using ask* nodes
- ALWAYS specify which attribute to save data to (use attribute ID or name)
- If an attribute doesn't exist but is needed (like "email", "phone", "age"), just use the name - it will be auto-created
- First node MUST be templateNode
- Use meaningful attribute names (e.g., "customer_email", "user_age", "delivery_address")

TASK:
1. Analyze the user requirements carefully
2. Select the BEST template that matches the use case
3. Design a conversation flow with appropriate nodes
4. Use askQuestionNode for ALL user input collection (not textNode)
5. Specify attributes for saving data (create new ones if needed)
6. Create a meaningful flow name
7. Explain your design decisions

OUTPUT FORMAT (JSON):
{{
  "name": "Descriptive Flow Name",
  "template_name": "selected_template_name",
  "explanation": "Why this flow design works for the user requirements",
  "flow_data": {{
    "nodes": [
      {{
        "id": "dndnode_0",
        "type": "templateNode",
        "position": {{"x": 0, "y": 100}},
        "data": {{
          "selectedTemplateName": "template_name_here"
        }}
      }},
      {{
        "id": "dndnode_1",
        "type": "askQuestionNode",
        "position": {{"x": 350, "y": 100}},
        "data": {{
          "questionText": "What is your email address?",
          "saveAttributeId": "customer_email"
        }}
      }},
      {{
        "id": "dndnode_2",
        "type": "askLocationNode",
        "position": {{"x": 700, "y": 100}},
        "data": {{
          "questionText": "Please share your location",
          "longitudeAttributeId": "user_longitude",
          "latitudeAttributeId": "user_latitude"
        }}
      }},
      {{
        "id": "dndnode_3",
        "type": "askForImageNode",
        "position": {{"x": 1050, "y": 100}},
        "data": {{
          "questionText": "Upload a photo",
          "saveAttributeId": "user_photo"
        }}
      }},
      {{
        "id": "dndnode_4",
        "type": "textNode",
        "position": {{"x": 1400, "y": 100}},
        "data": {{
          "text": "Thank you! We will contact you soon."
        }}
      }}
    ],
    "edges": [
      {{
        "id": "edge_0",
        "source": "dndnode_0",
        "target": "dndnode_1",
        "sourceHandle": "onRead"
      }},
      {{
        "id": "edge_1",
        "source": "dndnode_1",
        "target": "dndnode_2",
        "sourceHandle": "onAnswer"
      }},
      {{
        "id": "edge_2",
        "source": "dndnode_2",
        "target": "dndnode_3",
        "sourceHandle": "onLocationReceived"
      }},
      {{
        "id": "edge_3",
        "source": "dndnode_3",
        "target": "dndnode_4",
        "sourceHandle": "onImageReceived"
      }}
    ]
  }}
}}

IMPORTANT: Generate ONLY valid JSON, no markdown, no additional text. Use correct sourceHandle values for each node type.

EDGE EXAMPLES:
- Template to next node: {{"sourceHandle": "onRead"}} or {{"sourceHandle": "Button Text"}}
- askQuestionNode to next: {{"sourceHandle": "onAnswer"}}
- askLocationNode to next: {{"sourceHandle": "onLocationReceived"}}
- askForImageNode to next: {{"sourceHandle": "onImageReceived"}}
- buttonsNode to next: {{"sourceHandle": "Button 1"}} (exact button text)
- flowFormNode to next: {{"sourceHandle": "onSuccess"}}
- askApiNode to success: {{"sourceHandle": "onSuccess"}}
- askApiNode to error: {{"sourceHandle": "onError"}}

DOUBLE CHECK YOUR EDGES BEFORE OUTPUTTING!
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        generated_flow = json.loads(response_text)
        
        # Validate the generated flow
        if not validate_generated_flow(generated_flow, templates):
            logger.error("Generated flow validation failed")
            return None
        
        return generated_flow
        
    except Exception as e:
        logger.error(f"Error in Gemini generation: {e}", exc_info=True)
        return None


def create_missing_attributes(flow_data):
    """
    Automatically create attributes that are referenced in the flow but don't exist yet.
    Returns list of created attribute names.
    """
    created_attributes = []
    
    try:
        # Get existing attributes
        existing_attributes = {attr.name: attr.id for attr in Attribute.objects.all()}
        existing_ids = {attr.id for attr in Attribute.objects.all()}
        
        # Scan through all nodes looking for attribute references
        for node in flow_data['flow_data']['nodes']:
            node_data = node.get('data', {})
            
            # Check various attribute fields
            attribute_fields = [
                'saveAttributeId',
                'longitudeAttributeId', 
                'latitudeAttributeId',
                'waiting_for_attribute',
                'statusCodeAttributeId'
            ]
            
            for field in attribute_fields:
                attr_ref = node_data.get(field)
                if not attr_ref:
                    continue
                    
                # Check if it's a string name (needs to be created/converted)
                if isinstance(attr_ref, str) and not attr_ref.isdigit():
                    # Check if attribute exists by name
                    if attr_ref in existing_attributes:
                        # Use existing attribute ID
                        node_data[field] = existing_attributes[attr_ref]
                    else:
                        # Create new attribute
                        new_attr = Attribute.objects.create(
                            name=attr_ref,
                            description=f"Auto-created for {flow_data['name']}"
                        )
                        created_attributes.append(attr_ref)
                        existing_attributes[attr_ref] = new_attr.id
                        existing_ids.add(new_attr.id)
                        
                        # Update node data with actual ID
                        node_data[field] = new_attr.id
                        logger.info(f"Created attribute '{attr_ref}' with ID {new_attr.id}")
                
                # If it's already a valid integer ID, leave it
                elif isinstance(attr_ref, int) or (isinstance(attr_ref, str) and attr_ref.isdigit()):
                    attr_id = int(attr_ref)
                    if attr_id not in existing_ids:
                        logger.warning(f"Attribute ID {attr_id} referenced but doesn't exist")
            
            # Check response mappings in API nodes
            if 'responseMappings' in node_data:
                for mapping in node_data['responseMappings']:
                    attr_ref = mapping.get('attributeId')
                    if not attr_ref:
                        continue
                        
                    if isinstance(attr_ref, str) and not attr_ref.isdigit():
                        if attr_ref in existing_attributes:
                            mapping['attributeId'] = existing_attributes[attr_ref]
                        else:
                            new_attr = Attribute.objects.create(
                                name=attr_ref,
                                description=f"Auto-created for API response in {flow_data['name']}"
                            )
                            created_attributes.append(attr_ref)
                            existing_attributes[attr_ref] = new_attr.id
                            mapping['attributeId'] = new_attr.id
                            logger.info(f"Created attribute '{attr_ref}' for API mapping with ID {new_attr.id}")
        
        return created_attributes
        
    except Exception as e:
        logger.error(f"Error creating missing attributes: {e}", exc_info=True)
        return []


def validate_generated_flow(flow, templates):
    """Validate the AI-generated flow structure."""
    try:
        # Check required fields
        if not all(key in flow for key in ['name', 'template_name', 'flow_data']):
            logger.error("Missing required fields in generated flow")
            return False
        
        # Check template exists
        template_names = [t['name'] for t in templates]
        if flow['template_name'] not in template_names:
            logger.error(f"Template {flow['template_name']} not found in available templates")
            return False
        
        # Check flow_data structure
        flow_data = flow['flow_data']
        if 'nodes' not in flow_data or 'edges' not in flow_data:
            logger.error("Flow data missing nodes or edges")
            return False
        
        # Check first node is templateNode
        if not flow_data['nodes'] or flow_data['nodes'][0]['type'] != 'templateNode':
            logger.error("First node must be templateNode")
            return False
        
        # Validate that ask nodes have required fields and correct sourceHandles
        for i, node in enumerate(flow_data['nodes']):
            node_type = node.get('type')
            node_data = node.get('data', {})
            
            # Validate data fields
            if node_type == 'askQuestionNode':
                if not node_data.get('questionText'):
                    logger.warning(f"askQuestionNode {node['id']} missing questionText")
                if not node_data.get('saveAttributeId'):
                    logger.warning(f"askQuestionNode {node['id']} missing saveAttributeId")
            
            elif node_type == 'askLocationNode':
                if not node_data.get('questionText'):
                    logger.warning(f"askLocationNode {node['id']} missing questionText")
                if not node_data.get('longitudeAttributeId'):
                    logger.warning(f"askLocationNode {node['id']} missing longitudeAttributeId")
                if not node_data.get('latitudeAttributeId'):
                    logger.warning(f"askLocationNode {node['id']} missing latitudeAttributeId")
            
            elif node_type == 'askForImageNode':
                if not node_data.get('questionText'):
                    logger.warning(f"askForImageNode {node['id']} missing questionText")
                if not node_data.get('saveAttributeId'):
                    logger.warning(f"askForImageNode {node['id']} missing saveAttributeId")
        
        # Validate sourceHandles in edges
        for edge in flow_data.get('edges', []):
            source_node = next((n for n in flow_data['nodes'] if n['id'] == edge['source']), None)
            if source_node:
                node_type = source_node.get('type')
                source_handle = edge.get('sourceHandle')
                
                # Check if sourceHandle matches node type
                if node_type == 'askLocationNode' and source_handle != 'onLocationReceived':
                    logger.error(f"INVALID: askLocationNode must use sourceHandle='onLocationReceived', got '{source_handle}'")
                    return False
                elif node_type == 'askForImageNode' and source_handle != 'onImageReceived':
                    logger.error(f"INVALID: askForImageNode must use sourceHandle='onImageReceived', got '{source_handle}'")
                    return False
                elif node_type == 'askQuestionNode' and source_handle != 'onAnswer':
                    logger.error(f"INVALID: askQuestionNode must use sourceHandle='onAnswer', got '{source_handle}'")
                    return False
                elif node_type == 'flowFormNode' and source_handle not in ['onSuccess', 'onError']:
                    logger.error(f"INVALID: flowFormNode must use sourceHandle='onSuccess', got '{source_handle}'")
                    return False
        
        return True
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


def get_ai_generated_flows(request):
    """Get list of all flows with metadata."""
    try:
        flows = Flow.objects.all().order_by('-created_at')
        
        flows_data = []
        for flow in flows:
            flows_data.append({
                'id': flow.id,
                'name': flow.name,
                'template_name': flow.template_name,
                'is_active': flow.is_active,
                'created_at': flow.created_at.isoformat(),
                'updated_at': flow.updated_at.isoformat(),
                'node_count': len(flow.flow_data.get('nodes', [])),
                'edge_count': len(flow.flow_data.get('edges', []))
            })
        
        return JsonResponse({
            'status': 'success',
            'flows': flows_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching flows: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    


@csrf_exempt
def generate_flow_with_smart_template_detection(request):
    """
    Enhanced flow generation that identifies missing templates during flow design.
    Pauses to request template creation when needed.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_info = data.get('user_info', '')
        
        if not user_info:
            return JsonResponse({
                'status': 'error',
                'message': 'User info is required'
            }, status=400)
        
        # Step 1: Fetch all available resources
        templates = fetch_whatsapp_templates()
        flow_forms = list(WhatsAppFlowForm.objects.all().values(
            'id', 'name', 'template_body', 'template_button_text',
            'template_category', 'screens_data'
        ))
        attributes = list(Attribute.objects.all().values('id', 'name', 'description'))
        
        # Step 2: Analyze requirements and identify template gaps
        analysis = analyze_flow_requirements_with_template_gaps(
            user_info=user_info,
            templates=templates,
            flow_forms=flow_forms,
            attributes=attributes
        )
        
        if not analysis:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to analyze requirements'
            }, status=500)
        
        # Step 3: Check if templates are missing
        if analysis.get('missing_templates'):
            # Pause and request template creation
            return JsonResponse({
                'status': 'templates_needed',
                'message': 'Some templates need to be created first',
                'analysis': analysis,
                'missing_templates': analysis['missing_templates'],
                'flow_plan': analysis['flow_plan']
            })
        
        # Step 4: Generate complete flow (all templates available)
        generated_flow = analysis.get('generated_flow')
        
        if not generated_flow or not validate_generated_flow(generated_flow, templates):
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate valid flow'
            }, status=500)
        
        # Step 5: Create missing attributes
        created_attributes = create_missing_attributes(generated_flow)
        
        # Step 6: Save flow
        flow_obj = Flow.objects.create(
            name=generated_flow['name'],
            template_name=generated_flow['template_name'],
            flow_data=generated_flow['flow_data'],
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Flow generated successfully',
            'flow': {
                'id': flow_obj.id,
                'name': flow_obj.name,
                'template_name': flow_obj.template_name,
                'explanation': generated_flow.get('explanation', ''),
                'flow_data': generated_flow['flow_data'],
                'created_attributes': created_attributes
            }
        })
        
    except Exception as e:
        logger.error(f"Error in enhanced flow generation: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
def analyze_flow_with_language_preference(request):
    """
    Analyzes requirements and returns ALL missing templates at once.
    User can choose which to create and which to skip.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_info = data.get('user_info', '')
        preferred_language = data.get('preferred_language', 'hi')  # hi, en, en_US
        
        if not user_info:
            return JsonResponse({
                'status': 'error',
                'message': 'User info required'
            }, status=400)
        
        # Fetch resources
        templates = fetch_whatsapp_templates()
        flow_forms = list(WhatsAppFlowForm.objects.all().values(
            'id', 'name', 'template_body', 'template_button_text',
            'template_category', 'screens_data'
        ))
        attributes = list(Attribute.objects.all().values('id', 'name', 'description'))
        
        # Analyze and get ALL missing templates at once
        analysis = analyze_all_template_needs(
            user_info=user_info,
            templates=templates,
            flow_forms=flow_forms,
            attributes=attributes,
            language=preferred_language
        )
        
        if not analysis:
            return JsonResponse({
                'status': 'error',
                'message': 'Analysis failed'
            }, status=500)
        
        return JsonResponse({
            'status': 'success',
            'analysis': analysis.get('analysis', ''),
            'missing_templates': analysis.get('missing_templates', []),
            'flow_plan': analysis.get('flow_plan', {}),
            'can_proceed_without_templates': True  # User always has choice
        })
        
    except Exception as e:
        logger.error(f"Error in language-aware analysis: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


                
def analyze_all_template_needs(user_info, templates, flow_forms, attributes, language='hi'):
    """
    Returns ALL missing templates at once, not one by one.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Language-specific instructions
        language_guide = {
            'hi': {
                'script': 'देवनागरी (Marathi/Hindi)',
                'greeting': 'नमस्कार',
                'examples': ['राजू पाटील', 'नाशिक'],
                'buttons': ['मजूर हवे', 'सेवा पहा', 'संपर्क करा']
            },
            'en': {
                'script': 'English',
                'greeting': 'Hello',
                'examples': ['John Doe', 'Mumbai'],
                'buttons': ['Need Workers', 'View Services', 'Contact Us']
            }
        }
        
        lang_config = language_guide.get(language, language_guide['hi'])
        
        prompt = f"""
You are designing WhatsApp flows for a FARMER-LABOR PLATFORM.

USER REQUIREMENTS:
{user_info}

PREFERRED LANGUAGE: {language} ({lang_config['script']})

AVAILABLE TEMPLATES:
{json.dumps(templates, indent=2)}

TASK: Return ALL missing templates needed for this flow.

LANGUAGE RULES for {language}:
- Script: {lang_config['script']}
- Greeting: {lang_config['greeting']}
- Example names: {lang_config['examples']}
- Button examples: {lang_config['buttons']}
- Always include variables {{{{1}}}}, {{{{2}}}} for personalization
- 4-6 lines in body text
- Use emojis: ⭐, 🍇, ✅, 👇
- Professional but friendly tone

OUTPUT FORMAT (JSON):
{{
  "analysis": "Brief analysis of what's needed",
  "missing_templates": [
    {{
      "purpose": "What this template does",
      "reason": "Why we need it",
      "suggested_name": "descriptive_name_lowercase",
      "template_requirements": {{
        "category": "UTILITY" or "MARKETING",
        "language": "{language}",
        "body_text": "Full template text with {{{{1}}}} variables",
        "needs_buttons": true/false,
        "button_options": ["Button 1", "Button 2"],
        "needs_media": false,
        "variables": [
          {{"name": "farmer_name", "example": "{lang_config['examples'][0]}"}},
          {{"name": "location", "example": "{lang_config['examples'][1]}"}}
        ]
      }}
    }}
  ],
  "flow_plan": {{
    "steps": [
      {{
        "step": 1,
        "type": "template",
        "status": "missing" or "exists",
        "template_name": "name if exists",
        "action": "What happens"
      }}
    ]
  }}
}}

RETURN ALL MISSING TEMPLATES IN ONE RESPONSE.
Generate ONLY valid JSON.
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"Error in batch template analysis: {e}", exc_info=True)
        return None

def analyze_flow_requirements_with_template_gaps(user_info, templates, flow_forms, attributes):
    """
    Analyzes flow requirements and identifies which templates exist vs which need creation.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
You are designing WhatsApp chatbot flows for a farmer-labor connection platform. 
Analyze the requirements and create an optimal flow plan.

COMPANY CONTEXT: 
We connect farmers with laborers and provide farming-related services.

USER REQUIREMENTS:
{user_info}

AVAILABLE APPROVED TEMPLATES:
{json.dumps(templates, indent=2)}

AVAILABLE FLOW FORMS:
{json.dumps(flow_forms, indent=2)}

AVAILABLE ATTRIBUTES:
{json.dumps(attributes, indent=2)}

TASK:
Analyze the requirements step by step:

1. Identify the INITIAL engagement message needed
   - Check if existing template works
   - If not, flag it as "MISSING TEMPLATE"

2. Break down the flow into conversation steps:
   - Step 1: Initial engagement (template)
   - Step 2: Gather info (ask nodes, forms, etc.)
   - Step 3: Process/response
   - etc.

3. For EACH step, determine if it needs:
   - Existing template (specify which)
   - New template (describe requirements)
   - Ask node (question, location, image)
   - Form (if multi-field collection)
   - Other node type

4. List ALL missing templates with their requirements

OUTPUT FORMAT (JSON):
{{
  "analysis": "Overall analysis of the requirements",
  "missing_templates": [
    {{
      "purpose": "Initial farmer engagement",
      "reason": "Need to welcome farmer and present options",
      "suggested_name": "farmer_welcome_service",
      "template_requirements": {{
        "category": "UTILITY",
        "body_text": "Welcome message content",
        "needs_buttons": true,
        "button_options": ["View Services", "Contact Support"],
        "needs_media": false,
        "variables": []
      }}
    }}
  ],
  "flow_plan": {{
    "steps": [
      {{
        "step": 1,
        "type": "template",
        "status": "missing" or "exists",
        "template_name": "template_name" (if exists),
        "action": "User receives welcome message"
      }},
      {{
        "step": 2,
        "type": "askQuestionNode",
        "status": "ready",
        "action": "Ask about crop type",
        "save_to_attribute": "crop_type"
      }},
      {{
        "step": 3,
        "type": "askLocationNode",
        "status": "ready",
        "action": "Request farm location"
      }}
    ]
  }},
  "can_proceed": false (if templates missing) or true (if all ready),
  "generated_flow": {{}} (ONLY include if can_proceed is true)
}}

IMPORTANT:
- Be conservative - if no exact template match, mark as missing
- For farmer/labor platform, templates should be professional and clear
- Use forms for complex data collection (multiple fields)
- Use ask nodes for single questions
- Generate complete flow ONLY if all templates exist

Generate ONLY valid JSON.
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        analysis = json.loads(response_text)
        
        # If can proceed, generate the actual flow
        if analysis.get('can_proceed') and not analysis.get('missing_templates'):
            flow = generate_flow_with_gemini(user_info, templates, flow_forms, attributes)
            analysis['generated_flow'] = flow
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error in template gap analysis: {e}", exc_info=True)
        return None


@csrf_exempt
def create_templates_and_resume_flow(request):
    """
    After templates are created and approved, resume flow generation.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        original_requirements = data.get('original_requirements')
        flow_plan = data.get('flow_plan')
        created_template_names = data.get('created_templates', [])
        
        if not all([original_requirements, flow_plan]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required data'
            }, status=400)
        
        # Fetch updated templates (including newly approved ones)
        templates = fetch_whatsapp_templates()
        
        # Verify all required templates now exist
        missing = []
        for step in flow_plan.get('steps', []):
            if step.get('status') == 'missing' and step.get('type') == 'template':
                template_name = step.get('template_name')
                if not any(t['name'] == template_name for t in templates):
                    missing.append(template_name)
        
        if missing:
            return JsonResponse({
                'status': 'waiting',
                'message': f'Still waiting for templates: {", ".join(missing)}',
                'missing_templates': missing
            })
        
        # All templates ready - generate flow
        flow_forms = list(WhatsAppFlowForm.objects.all().values(
            'id', 'name', 'template_body', 'template_button_text',
            'template_category', 'screens_data'
        ))
        attributes = list(Attribute.objects.all().values('id', 'name', 'description'))
        
        generated_flow = generate_flow_with_gemini(
            user_info=original_requirements,
            templates=templates,
            flow_forms=flow_forms,
            attributes=attributes
        )
        
        if not generated_flow or not validate_generated_flow(generated_flow, templates):
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate flow'
            }, status=500)
        
        created_attributes = create_missing_attributes(generated_flow)
        
        flow_obj = Flow.objects.create(
            name=generated_flow['name'],
            template_name=generated_flow['template_name'],
            flow_data=generated_flow['flow_data'],
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Flow created successfully',
            'flow': {
                'id': flow_obj.id,
                'name': flow_obj.name,
                'template_name': flow_obj.template_name,
                'explanation': generated_flow.get('explanation', ''),
                'flow_data': generated_flow['flow_data'],
                'created_attributes': created_attributes
            }
        })
        
    except Exception as e:
        logger.error(f"Error resuming flow creation: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    

@csrf_exempt
def create_flow_with_refined_requirements(request):
    """
    Creates flow with potentially refined requirements after template review.
    Allows user to edit original input before final flow generation.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        original_requirements = data.get('original_requirements', '')
        refined_requirements = data.get('refined_requirements', original_requirements)
        created_templates = data.get('created_templates', [])
        flow_plan = data.get('flow_plan', {})
        
        # Use refined requirements if user edited them
        final_requirements = refined_requirements if refined_requirements != original_requirements else original_requirements
        
        # Fetch updated templates
        templates = fetch_whatsapp_templates()
        flow_forms = list(WhatsAppFlowForm.objects.all().values(
            'id', 'name', 'template_body', 'template_button_text',
            'template_category', 'screens_data'
        ))
        attributes = list(Attribute.objects.all().values('id', 'name', 'description'))
        
        # Generate flow with potentially refined requirements
        generated_flow = generate_flow_with_gemini(
            user_info=final_requirements,
            templates=templates,
            flow_forms=flow_forms,
            attributes=attributes
        )
        
        if not generated_flow or not validate_generated_flow(generated_flow, templates):
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate flow'
            }, status=500)
        
        created_attributes = create_missing_attributes(generated_flow)
        
        flow_obj = Flow.objects.create(
            name=generated_flow['name'],
            template_name=generated_flow['template_name'],
            flow_data=generated_flow['flow_data'],
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Flow created successfully',
            'flow': {
                'id': flow_obj.id,
                'name': flow_obj.name,
                'template_name': flow_obj.template_name,
                'explanation': generated_flow.get('explanation', ''),
                'flow_data': generated_flow['flow_data'],
                'created_attributes': created_attributes,
                'was_refined': refined_requirements != original_requirements
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating flow with refined requirements: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def batch_template_analysis(user_info, templates, language='hi'):
    """
    Returns ALL missing templates at once, not one by one.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Language-specific instructions
        language_guide = {
            'hi': {
                'script': 'देवनागरी (Marathi/Hindi)',
                'greeting': 'नमस्कार',
                'examples': ['राजू पाटील', 'नाशिक'],
                'buttons': ['मजूर हवे', 'सेवा पहा', 'संपर्क करा']
            },
            'en': {
                'script': 'English',
                'greeting': 'Hello',
                'examples': ['John Doe', 'Mumbai'],
                'buttons': ['Need Workers', 'View Services', 'Contact Us']
            }
        }
        
        lang_config = language_guide.get(language, language_guide['hi'])
        
        prompt = f"""
You are designing WhatsApp flows for a FARMER-LABOR PLATFORM.

USER REQUIREMENTS:
{user_info}

PREFERRED LANGUAGE: {language} ({lang_config['script']})

AVAILABLE TEMPLATES:
{json.dumps(templates, indent=2)}

TASK: Return ALL missing templates needed for this flow.

LANGUAGE RULES for {language}:
- Script: {lang_config['script']}
- Greeting: {lang_config['greeting']}
- Example names: {lang_config['examples']}
- Button examples: {lang_config['buttons']}
- Always include variables {{{{1}}}}, {{{{2}}}} for personalization
- 4-6 lines in body text
- Use emojis: ⭐, 🍇, ✅, 👇
- Professional but friendly tone

OUTPUT FORMAT (JSON):
{{
  "analysis": "Brief analysis of what's needed",
  "missing_templates": [
    {{
      "purpose": "What this template does",
      "reason": "Why we need it",
      "suggested_name": "descriptive_name_lowercase",
      "template_requirements": {{
        "category": "UTILITY" or "MARKETING",
        "language": "{language}",
        "body_text": "Full template text with {{{{1}}}} variables",
        "needs_buttons": true/false,
        "button_options": ["Button 1", "Button 2"],
        "needs_media": false,
        "variables": [
          {{"name": "farmer_name", "example": "{lang_config['examples'][0]}"}},
          {{"name": "location", "example": "{lang_config['examples'][1]}"}}
        ]
      }}
    }}
  ],
  "flow_plan": {{
    "steps": [
      {{
        "step": 1,
        "type": "template",
        "status": "missing" or "exists",
        "template_name": "name if exists",
        "action": "What happens"
      }}
    ]
  }}
}}

RETURN ALL MISSING TEMPLATES IN ONE RESPONSE.
Generate ONLY valid JSON.
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"Error in batch template analysis: {e}", exc_info=True)
        return None