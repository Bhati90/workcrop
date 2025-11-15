from firebase_admin import messaging

def send_push_notification(fcm_token, title, body, data=None):
    """Send push notification to a single mukadam"""
    if not fcm_token:
        print("⚠️ No FCM token")
        return False
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=fcm_token,
        )
        
        response = messaging.send(message)
        print(f"✅ Push sent: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Push failed: {e}")
        return False