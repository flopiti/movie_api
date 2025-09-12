#!/usr/bin/env python3
"""
Test script to set up default SMS reply templates and settings.
This script can be run to initialize the SMS reply system with some default templates.
"""

import requests
import json
import sys

# Configuration
BASE_URL = 'http://192.168.0.10:5000'

def test_sms_reply_setup():
    """Test and set up SMS reply templates and settings."""
    
    print("🧪 Testing SMS Reply Management Setup")
    print("=" * 50)
    
    # Test 1: Check if the endpoints are available
    print("\n1. Testing endpoint availability...")
    try:
        response = requests.get(f"{BASE_URL}/api/sms/reply-templates", timeout=5)
        if response.status_code == 200:
            print("✅ Reply templates endpoint is available")
        else:
            print(f"❌ Reply templates endpoint returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to reply templates endpoint: {e}")
        return False
    
    try:
        response = requests.get(f"{BASE_URL}/api/sms/reply-settings", timeout=5)
        if response.status_code == 200:
            print("✅ Reply settings endpoint is available")
        else:
            print(f"❌ Reply settings endpoint returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to reply settings endpoint: {e}")
        return False
    
    # Test 2: Create default templates
    print("\n2. Creating default reply templates...")
    
    default_templates = [
        {
            "name": "default",
            "template": "Thanks for your message! I received: '{message}' from {sender} at {timestamp}",
            "description": "Default reply template for all messages",
            "keywords": [],
            "enabled": True
        },
        {
            "name": "movie_request",
            "template": "Movie request received! I'll look into '{message}' for you. Thanks!",
            "description": "Template for movie-related requests",
            "keywords": ["movie", "film", "watch", "download", "request"],
            "enabled": True
        },
        {
            "name": "help_request",
            "template": "I received your help request: '{message}'. I'll get back to you soon!",
            "description": "Template for help requests",
            "keywords": ["help", "support", "assist", "question"],
            "enabled": True
        },
        {
            "name": "status_check",
            "template": "System status check received from {sender}. All systems operational!",
            "description": "Template for status check messages",
            "keywords": ["status", "check", "ping", "alive"],
            "enabled": True
        }
    ]
    
    created_templates = []
    for template in default_templates:
        try:
            response = requests.post(
                f"{BASE_URL}/api/sms/reply-templates",
                json=template,
                timeout=10
            )
            if response.status_code == 201:
                template_data = response.json()
                created_templates.append(template_data['template'])
                print(f"✅ Created template: {template['name']}")
            else:
                print(f"❌ Failed to create template {template['name']}: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"❌ Error creating template {template['name']}: {e}")
    
    # Test 3: Set up default settings
    print("\n3. Setting up default reply settings...")
    
    default_settings = {
        "auto_reply_enabled": True,
        "fallback_message": "Message received: '{message}'",
        "reply_delay_seconds": 2,
        "max_replies_per_day": 50,
        "blocked_numbers": []
    }
    
    try:
        response = requests.put(
            f"{BASE_URL}/api/sms/reply-settings",
            json=default_settings,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Default settings configured successfully")
        else:
            print(f"❌ Failed to configure settings: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error configuring settings: {e}")
    
    # Test 4: Verify the setup
    print("\n4. Verifying the setup...")
    
    try:
        # Get templates
        response = requests.get(f"{BASE_URL}/api/sms/reply-templates", timeout=5)
        if response.status_code == 200:
            templates_data = response.json()
            print(f"✅ Found {templates_data['count']} reply templates")
            for template in templates_data['templates']:
                print(f"   - {template['name']}: {'Enabled' if template['enabled'] else 'Disabled'}")
        else:
            print(f"❌ Failed to retrieve templates: {response.status_code}")
        
        # Get settings
        response = requests.get(f"{BASE_URL}/api/sms/reply-settings", timeout=5)
        if response.status_code == 200:
            settings = response.json()
            print(f"✅ Auto-reply: {'Enabled' if settings['auto_reply_enabled'] else 'Disabled'}")
            print(f"✅ Max replies per day: {settings['max_replies_per_day']}")
            print(f"✅ Reply delay: {settings['reply_delay_seconds']} seconds")
        else:
            print(f"❌ Failed to retrieve settings: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error verifying setup: {e}")
    
    # Test 5: Test webhook endpoint
    print("\n5. Testing webhook endpoint...")
    
    test_webhook_data = {
        'MessageSid': 'test123',
        'From': '+1234567890',
        'To': '+0987654321',
        'Body': 'test message',
        'NumMedia': '0'
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/sms/webhook",
            data=test_webhook_data,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Webhook endpoint is working")
            print(f"   Response type: {response.headers.get('Content-Type', 'unknown')}")
        else:
            print(f"❌ Webhook endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 SMS Reply Management Setup Complete!")
    print("\nNext steps:")
    print("1. Configure your Twilio webhook URL to point to: http://your-server:5000/api/sms/webhook")
    print("2. Test by sending SMS messages to your Twilio number")
    print("3. Use the web interface to customize templates and settings")
    
    return True

if __name__ == "__main__":
    try:
        test_sms_reply_setup()
    except KeyboardInterrupt:
        print("\n\n⏹️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        sys.exit(1)
