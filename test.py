# test_mukadam_receiver.py
from flask import Flask, request, jsonify
import json
from datetime import datetime
import requests

app = Flask(__name__)

# Store all received notifications
notifications_log = []

# In simulate_bid_submission function, update the URL:
def simulate_bid_submission():
    bid_data = request.get_json()
    
    # Use your actual Django endpoint
    django_bid_url = "http://localhost:8000/api/bids/submit_bid/"  # Real URL
    
    try:
        print(f"\n🚀 Submitting bid to Django: {django_bid_url}")
        
        django_response = requests.post(
            django_bid_url,
            json=bid_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"📊 Django Response Status: {django_response.status_code}")
        print(f"📋 Django Response:")
        print(json.dumps(django_response.json(), indent=2))
        
        return jsonify({
            "status": "success",
            "django_response": django_response.json(),
            "submitted_bid": bid_data
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400
# Add this to your test_mukadam_receiver.py

@app.route('/api/webhooks/job-notification', methods=['POST'])
def receive_job_notification():
    """Enhanced to handle different notification types"""
    
    notification_time = datetime.now()
    notification_data = request.get_json()
    notification_type = notification_data.get('notification_type', 'unknown')
    
    print(f"\n{'='*80}")
    print(f"🔔 {notification_type.upper()} NOTIFICATION RECEIVED")
    print(f"{'='*80}")
    
    if notification_type == "new_job_assignment":
        handle_job_assignment_notification(notification_data)
    elif notification_type == "job_selection_winner":
        handle_winner_notification(notification_data)
    elif notification_type == "job_selection_rejected":
        handle_rejection_notification(notification_data)
    else:
        print(f"❓ Unknown notification type: {notification_type}")
    
    return jsonify({
        "status": "received",
        "notification_type": notification_type,
        "processed_at": notification_time.isoformat()
    }), 200

def handle_winner_notification(data):
    """Handle 'YOU WON' notification"""
    target_mukadam = data.get('target_mukadam', {})
    selection_result = data.get('selection_result', {})
    job_execution = data.get('job_execution', {})
    
    print(f"🎉 CONGRATULATIONS {target_mukadam.get('mukadam_name')}!")
    print(f"✅ Your bid has been SELECTED!")
    print(f"💰 Final Price: ₹{selection_result.get('final_price_per_acre')}/acre")
    print(f"💵 Total Amount: ₹{selection_result.get('total_amount'):,.2f}")
    
    farmer = job_execution.get('farmer_contact', {})
    work = job_execution.get('work_details', {})
    
    print(f"\n📞 FARMER CONTACT:")
    print(f"   Name: {farmer.get('name')}")
    print(f"   Phone: {farmer.get('phone')}")
    print(f"   Location: {farmer.get('location')}")
    
    print(f"\n🌾 WORK DETAILS:")
    print(f"   Activity: {work.get('activity')}")
    print(f"   Farm Size: {work.get('farm_size_acres')} acres")
    print(f"   Date: {work.get('scheduled_date')}")
    print(f"   Time: {work.get('scheduled_time')}")
    print(f"   Duration: {work.get('estimated_duration')}h")
    
    print(f"\n📋 NEXT STEPS:")
    for step in data.get('next_steps', []):
        print(f"   • {step}")

def handle_rejection_notification(data):
    """Handle rejection notification"""
    target_mukadam = data.get('target_mukadam', {})
    selection_result = data.get('selection_result', {})
    feedback = data.get('feedback', {})
    
    print(f"😔 Sorry {target_mukadam.get('mukadam_name')}")
    print(f"❌ Your bid was not selected this time")
    print(f"💰 Your bid: ₹{selection_result.get('your_bid_price')}/acre")
    print(f"📝 Reason: {selection_result.get('reason')}")
    
    print(f"\n💡 FEEDBACK:")
    print(f"   {feedback.get('message')}")
    print(f"\n🎯 TIPS FOR NEXT TIME:")
    for tip in feedback.get('tips', []):
        print(f"   • {tip}")

def handle_job_assignment_notification(data):
    """Handle new job assignment (original logic)"""
    target_mukadam = data.get('target_mukadam', {})
    job_details = data.get('job_details', {})
    farmer = data.get('farmer', {})
    
    print(f"🎯 NEW JOB FOR: {target_mukadam.get('mukadam_name')}")
    print(f"👨‍🌾 Farmer: {farmer.get('name')}")
    print(f"🌾 Activity: {job_details.get('activity')}")
    print(f"📏 Size: {job_details.get('farm_size_acres')} acres")
    print(f"📍 Location: {job_details.get('location')}")

@app.route('/api/notifications/history', methods=['GET'])
def get_notifications_history():
    """View all received notifications"""
    return jsonify({
        "total_notifications": len(notifications_log),
        "notifications": notifications_log
    })

@app.route('/api/test/submit-bid', methods=['POST'])
def simulate_bid_submission():
    """Simulate mukadam submitting a bid back to your Django app"""
    
    bid_data = request.get_json()
    print(f"\n{'='*60}")
    print(f"💰 SIMULATING BID SUBMISSION")
    print(f"{'='*60}")
    print(f"📋 Bid Data Received:")
    print(json.dumps(bid_data, indent=2))
    
    # Simulate calling your Django API
    django_bid_url = "http://localhost:8000/api/bids/submit_bid/"
    
    try:
        print(f"\n🚀 Submitting bid to Django: {django_bid_url}")
        
        django_response = requests.post(
            django_bid_url,
            json=bid_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"📊 Django Response Status: {django_response.status_code}")
        print(f"📋 Django Response:")
        try:
            print(json.dumps(django_response.json(), indent=2))
        except:
            print(django_response.text)
            
        return jsonify({
            "status": "forwarded_to_django",
            "django_status": django_response.status_code,
            "original_bid": bid_data
        })
        
    except Exception as e:
        print(f"❌ Error submitting to Django: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "original_bid": bid_data
        }), 400

if __name__ == '__main__':
    print("🚀 Mock Mukadam App started on http://localhost:5000")
    print("📝 Test Endpoints:")
    print("   POST /api/webhooks/job-notification - Receive job notifications from Django")
    print("   GET  /api/notifications/history - View all received notifications")
    print("   POST /api/test/submit-bid - Simulate bid submission to Django")
    print("\n✅ Ready to receive webhook notifications!")
    app.run(debug=True, port=5000, use_reloader=False)