import re
import logging
from .models import Attribute, ContactAttributeValue

logger = logging.getLogger(__name__)

def substitute_variables(text, contact):
    """
    Finds all {{variable}} placeholders and replaces them with contact attribute values.
    """
    if not text or not isinstance(text, str):
        return text

    placeholders = re.findall(r"\{\{([a-zA-Z0-9_.-]+)\}\}", text)
    
    for placeholder in placeholders:
        # Special keywords for contact's own fields
        if placeholder.lower() == 'contact_id':
            value = contact.id
        elif placeholder.lower() == 'wa_id':
            value = contact.wa_id
        else:
            # Look up the value from the database
            try:
                # Case-insensitive lookup for the attribute name
                attribute = Attribute.objects.get(name__iexact=placeholder)
                contact_attr = ContactAttributeValue.objects.get(contact=contact, attribute=attribute)
                value = contact_attr.value
            except (Attribute.DoesNotExist, ContactAttributeValue.DoesNotExist):
                value = "" # Default to empty string if no value is found
                logger.warning(f"Attribute '{placeholder}' not found for contact {contact.wa_id}")

        text = text.replace(f"{{{{{placeholder}}}}}", str(value))
        
    return text

def extract_json_path(data, path):
    """
    Extracts a value from a nested dictionary/list using a dot-separated path.
    """
    try:
        current = data
        parts = path.split('.')
        for part in parts:
            if isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                return None
        return current
    except (KeyError, IndexError, TypeError):
        return None