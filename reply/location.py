"""
Location Extraction Utility for WhatsApp Bot
Intelligently extracts location from:
1. Last shared GPS coordinates
2. Conversation history (text mentions)
3. Current message
"""

import re
import logging

logger = logging.getLogger(__name__)


def extract_location_from_conversation(current_message, conversation):
    """
    Extracts location from multiple sources with priority:
    1. GPS location (most recent)
    2. Location mentioned in conversation history
    3. Location in current message
    
    Returns: String with location or None
    """
    
    # ====== PRIORITY 1: Check for GPS Location ======
    gps_location = get_last_gps_location(conversation)
    if gps_location:
        logger.info(f"📍 Using GPS location: {gps_location}")
        return gps_location
    
    # ====== PRIORITY 2: Check conversation history ======
    history_location = extract_from_history(conversation)
    if history_location:
        logger.info(f"💬 Found location in history: {history_location}")
        return history_location
    
    # ====== PRIORITY 3: Check current message ======
    current_location = extract_from_text(current_message)
    if current_location:
        logger.info(f"📝 Found location in current message: {current_location}")
        return current_location
    
    logger.info("🔍 No location found in conversation")
    return None


def get_last_gps_location(conversation):
    """
    Get the most recent GPS location shared by user
    """
    try:
        # Find last location message
        location_msg = conversation.messages.filter(
            message_type='location',
            direction='inbound'
        ).order_by('-timestamp').first()
        
        if location_msg and location_msg.text_content:
            # Extract readable location from text_content
            text = location_msg.text_content
            
            # Try to extract name/address
            if 'Name:' in text:
                name = re.search(r'Name:\s*(.+)', text)
                if name:
                    return name.group(1).strip()
            
            if 'Address:' in text:
                address = re.search(r'Address:\s*(.+)', text)
                if address:
                    return address.group(1).strip()
            
            # Extract coordinates as fallback
            coords = re.search(r'Coordinates:\s*([\d.]+),\s*([\d.]+)', text)
            if coords:
                lat, lon = coords.groups()
                return f"GPS: {lat}, {lon}"
        
        return None
    
    except Exception as e:
        logger.error(f"Error getting GPS location: {e}")
        return None


def extract_from_history(conversation, lookback=20):
    """
    Search last N messages for location mentions
    """
    try:
        # Get recent messages (text and audio transcriptions)
        recent_msgs = conversation.messages.filter(
            direction='inbound',
            message_type__in=['text', 'audio']
        ).order_by('-timestamp')[:lookback]
        
        # Combine all text
        combined_text = ' '.join([
            msg.text_content or '' 
            for msg in recent_msgs
        ])
        
        return extract_from_text(combined_text)
    
    except Exception as e:
        logger.error(f"Error extracting from history: {e}")
        return None


def extract_from_text(text):
    """
    Extract location from text using multiple strategies:
    1. Known cities/districts (multilingual)
    2. Pattern matching (near X, at Y, in Z)
    3. Pin codes
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # ===== STRATEGY 1: Known Locations (Expanded List) =====
    known_locations = {
        # Major cities
        'mumbai': 'Mumbai', 'मुंबई': 'Mumbai',
        'pune': 'Pune', 'पुणे': 'Pune',
        'nashik': 'Nashik', 'नाशिक': 'Nashik',
        'satara': 'Satara', 'सातारा': 'Satara',
        'kolhapur': 'Kolhapur', 'कोल्हापूर': 'Kolhapur',
        'sangli': 'Sangli', 'सांगली': 'Sangli',
        'solapur': 'Solapur', 'सोलापूर': 'Solapur',
        'aurangabad': 'Aurangabad', 'औरंगाबाद': 'Aurangabad',
        'nagpur': 'Nagpur', 'नागपूर': 'Nagpur',
        'ahmednagar': 'Ahmednagar', 'अहमदनगर': 'Ahmednagar',
        
        # Talukas
        'karad': 'Karad', 'कराड': 'Karad',
        'wai': 'Wai', 'वाई': 'Wai',
        'phaltan': 'Phaltan', 'फलटण': 'Phaltan',
        'koregaon': 'Koregaon', 'कोरेगाव': 'Koregaon',
        
        # Common patterns
        'village': 'Village', 'gaon': 'Village', 'गाव': 'Village',
        'taluka': 'Taluka', 'तालुका': 'Taluka',
    }
    
    # Check for direct matches
    for location_key, location_name in known_locations.items():
        if location_key in text_lower:
            # Try to get more context
            context = extract_location_context(text, location_key)
            if context:
                return context
            return location_name
    
    # ===== STRATEGY 2: Pattern Matching =====
    
    # "near X", "at Y", "in Z" patterns (English/Hindi/Marathi)
    patterns = [
        r'(?:near|at|in|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # near Mumbai
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:में|मध्ये|च्या)',  # Mumbai में
        r'([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+)?)\s+(?:गाव|शहर|तालुका)',  # सातारा गाव
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:village|taluka|city)',  # Satara village
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            location = match.group(1).strip()
            if len(location) > 2:  # Avoid single letters
                return location
    
    # ===== STRATEGY 3: Pin Code Detection =====
    pincode = re.search(r'\b\d{6}\b', text)
    if pincode:
        return f"Pincode: {pincode.group()}"
    
    return None


def extract_location_context(text, location_keyword):
    """
    Extract fuller location context (e.g., "Satara taluka" instead of just "Satara")
    """
    try:
        # Find the location and 2-3 words around it
        pattern = r'(\w+\s+)?' + re.escape(location_keyword) + r'(\s+\w+)?(\s+\w+)?'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            full_context = match.group().strip()
            # Clean up
            full_context = re.sub(r'\s+', ' ', full_context)
            if len(full_context) > 3:
                return full_context.title()
        
        return None
    
    except Exception as e:
        logger.error(f"Error extracting context: {e}")
        return None


# ===== Testing Function =====
def test_location_extraction():
    """Test the location extractor with sample messages"""
    test_cases = [
        "मुझे 20 मजूर चाहिए सातारा में",
        "I need workers in Pune near Hinjewadi",
        "मला मजूर पाहिजेत कराड गाव",
        "35 workers needed at Mumbai 400001",
        "Koregaon taluka workers",
    ]
    
    print("🧪 Testing Location Extraction:")
    for msg in test_cases:
        location = extract_from_text(msg)
        print(f"Message: {msg}")
        print(f"Extracted: {location}\n")


if __name__ == "__main__":
    test_location_extraction()