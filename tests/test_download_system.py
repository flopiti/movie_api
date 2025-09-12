#!/usr/bin/env python3
"""
Test script for the download monitoring system
"""

import os
import sys
import time
from datetime import datetime

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from download_monitor import download_monitor
from config import config

def test_download_system():
    """Test the download monitoring system"""
    print("🧪 Testing Download Monitoring System")
    print("=" * 50)
    
    # Test 1: Check if Radarr client is available
    print("\n1. Testing Radarr Client Connection...")
    radarr_client = config.get_radarr_client()
    if radarr_client and radarr_client.test_connection():
        print("✅ Radarr client connection successful")
        
        # Get system status
        status = radarr_client.get_system_status()
        if status:
            print(f"   Radarr version: {status.get('version', 'Unknown')}")
            print(f"   Radarr app name: {status.get('appName', 'Unknown')}")
    else:
        print("❌ Radarr client connection failed")
        return False
    
    # Test 2: Check if Twilio client is available
    print("\n2. Testing Twilio Client...")
    if download_monitor.twilio_client.is_configured():
        print("✅ Twilio client configured")
        print(f"   Phone number: {download_monitor.twilio_client.phone_number}")
    else:
        print("❌ Twilio client not configured")
        return False
    
    # Test 3: Check Redis connection
    print("\n3. Testing Redis Connection...")
    if download_monitor.redis_client:
        try:
            download_monitor.redis_client.ping()
            print("✅ Redis connection successful")
        except Exception as e:
            print(f"❌ Redis connection failed: {str(e)}")
            return False
    else:
        print("❌ Redis client not available")
        return False
    
    # Test 4: Test adding a download request
    print("\n4. Testing Download Request...")
    test_tmdb_id = 550  # Fight Club (1999)
    test_phone = "+1234567890"  # Test phone number
    
    success = download_monitor.add_download_request(
        tmdb_id=test_tmdb_id,
        movie_title="Fight Club",
        movie_year="1999",
        phone_number=test_phone
    )
    
    if success:
        print("✅ Download request added successfully")
        
        # Check if the request was stored
        request = download_monitor.get_download_request(test_tmdb_id)
        if request:
            print(f"   Movie: {request['movie_title']} ({request['movie_year']})")
            print(f"   Phone: {request['phone_number']}")
            print(f"   Status: {request['status']}")
            print(f"   Requested at: {request['requested_at']}")
        else:
            print("❌ Failed to retrieve download request")
    else:
        print("❌ Failed to add download request")
        return False
    
    # Test 5: Test monitoring service
    print("\n5. Testing Monitoring Service...")
    try:
        download_monitor.start_monitoring()
        print("✅ Monitoring service started")
        
        # Wait a bit to see if it processes the request
        print("   Waiting 5 seconds for processing...")
        time.sleep(5)
        
        # Check the status again
        request = download_monitor.get_download_request(test_tmdb_id)
        if request:
            print(f"   Updated status: {request['status']}")
            if request.get('radarr_movie_id'):
                print(f"   Radarr movie ID: {request['radarr_movie_id']}")
        
        # Stop monitoring
        download_monitor.stop_monitoring()
        print("✅ Monitoring service stopped")
        
    except Exception as e:
        print(f"❌ Monitoring service test failed: {str(e)}")
        return False
    
    # Test 6: Test API endpoints (simulation)
    print("\n6. Testing API Endpoints...")
    requests = download_monitor.get_download_requests()
    print(f"✅ Retrieved {len(requests)} download requests")
    
    status = {
        'running': download_monitor.running,
        'radarr_available': download_monitor.radarr_client is not None,
        'twilio_available': download_monitor.twilio_client.is_configured(),
        'redis_available': download_monitor.redis_client is not None,
        'active_requests': len(download_monitor.download_requests)
    }
    print(f"✅ System status: {status}")
    
    print("\n🎉 All tests completed successfully!")
    return True

if __name__ == "__main__":
    try:
        success = test_download_system()
        if success:
            print("\n✅ Download monitoring system is working correctly!")
        else:
            print("\n❌ Some tests failed. Please check the configuration.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        sys.exit(1)
