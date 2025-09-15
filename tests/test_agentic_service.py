#!/usr/bin/env python3
"""
Test script for AgenticService - Testing agentic response processing
ONLY MOCKS REDIS - EVERYTHING ELSE IS REAL
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables from the main project's env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', 'env'))

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Mock Redis module BEFORE any imports that use it
import json

class MockRedis:
    def __init__(self, *args, **kwargs):
        self.data = {}
    
    def ping(self):
        return True
    
    def get(self, key):
        return self.data.get(key)
    
    def set(self, key, value):
        self.data[key] = value
    
    def keys(self, pattern):
        if pattern == "download_request:*":
            return [k for k in self.data.keys() if k.startswith("download_request:")]
        return []
    
    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
    
    def zadd(self, key, mapping):
        pass
    
    def zrevrange(self, key, start, end):
        return []
    
    def zrem(self, key, member):
        pass
    
    def hset(self, name, key=None, value=None, mapping=None):
        """Mock hset for Redis hash operations"""
        if not hasattr(self, 'hashes'):
            self.hashes = {}
        if name not in self.hashes:
            self.hashes[name] = {}
        
        if mapping:
            self.hashes[name].update(mapping)
        elif key is not None and value is not None:
            self.hashes[name][key] = value
    
    def hget(self, name, key):
        """Mock hget for Redis hash operations"""
        if not hasattr(self, 'hashes'):
            return None
        return self.hashes.get(name, {}).get(key)
    
    def hgetall(self, name):
        """Mock hgetall for Redis hash operations"""
        if not hasattr(self, 'hashes'):
            return {}
        return self.hashes.get(name, {})

class MockRedisModule:
    def Redis(self, *args, **kwargs):
        return MockRedis()

# Replace redis module in sys.modules
sys.modules['redis'] = MockRedisModule()

# Configuration for testing
RADARR_URL = 'http://192.168.0.10:7878'
RADARR_API_KEY = '5a71ac347fb845da90e2284762335a1a'

# Import everything first, then patch
from src.services.agentic_service import AgenticService
from src.clients.openai_client import OpenAIClient
from src.services.movie_identification_service import MovieIdentificationService
from src.services.movie_library_service import MovieLibraryService
from src.services.radarr_service import RadarrService
from src.services.notification_service import NotificationService
from src.clients.PROMPTS import SMS_RESPONSE_PROMPT
from src.clients.tmdb_client import TMDBClient

# Create config instance with default values (not using Redis)
test_config = None

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Debug: Print what we got from config
print(f"DEBUG: Radarr API Key: {'✅ Configured' if RADARR_API_KEY else '❌ Missing'}")
print(f"DEBUG: OpenAI API Key: {'✅ Configured' if OPENAI_API_KEY else '❌ Missing'}")

def test_casual_conversation():
    """Test AgenticService with casual conversation - REAL OpenAI calls"""

    # Test parameters
    conversation_history = ["USER: yo"]
    
    # Create services
    openai_client = OpenAIClient(OPENAI_API_KEY)
    movie_identification_service = MovieIdentificationService(openai_client)
    # Create TMDB client for movie library service
    tmdb_client = TMDBClient(os.getenv('TMDB_API_KEY', ''))
    movie_library_service = MovieLibraryService(tmdb_client)
    radarr_service = RadarrService()
    notification_service = NotificationService()
    
    # Create agentic service
    agentic_service = AgenticService(openai_client)
    
    # Prepare services dictionary
    services = {
        'movie_identification': movie_identification_service,
        'movie_library': movie_library_service,
        'radarr': radarr_service,
        'notification': notification_service,
        'sms_response_prompt': SMS_RESPONSE_PROMPT
    }
    
    # Test the agentic service
    result = agentic_service.process_agentic_response(conversation_history, services)
    
    # Get the response message
    response_message = result.get('response_message', '')
    success = result.get('success', False)
    function_results = result.get('function_results', [])
    
    print(f"📱 Agent Response: {response_message}")
    print(f"✅ Success: {success}")
    print(f"🔧 Function Results: {len(function_results)} functions called")
    
    # Log function results
    for fr in function_results:
        function_name = fr['function_name']
        result_data = fr['result']
        print(f"  - {function_name}: {result_data.get('success', False)}")
    
    print()
    
    # Step 2: Validate the response with REAL OpenAI
    print("🔍 Step 2: Validating response with REAL OpenAI...")
    
    validation_prompt = f"""
    Analyze this SMS response to a casual greeting "yo". 
    
    Response to analyze: "{response_message}"
    
    Does this response correctly:
    1. Respond naturally and warmly to the casual greeting?
    2. Use appropriate tone for SMS communication?
    3. Show personality and be friendly?
    4. Not immediately ask for movie requests?
    
    Answer with YES or NO and explain why.
    """
    
    # Use REAL OpenAI for validation
    validation_result = openai_client.client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": validation_prompt}],
        max_tokens=200,
        temperature=0.3
    )
    
    validation_text = validation_result.choices[0].message.content.strip()
    print(f"🔍 OpenAI Validation: {validation_text}")
    print()
    
    # Results
    print("=" * 60)
    print("✅ TEST RESULTS:")
    print("=" * 60)
    print(f"📱 Agent Response: {response_message}")
    print(f"🔍 Validation: {validation_text}")
    
    # Check if validation is positive
    if "YES" in validation_text.upper():
        print("\n✅ SUCCESS: OpenAI confirms the response correctly handles casual conversation!")
    else:
        print("\n❌ FAILURE: OpenAI indicates the response needs improvement")
    
    return {
        'agent_response': response_message,
        'validation_result': validation_text,
        'success': "YES" in validation_text.upper(),
        'function_results': function_results
    }

def test_movie_request():
    """Test AgenticService with movie request - REAL OpenAI calls"""
    
    print("🎬 Testing AgenticService with movie request")
    print("=" * 60)
    
    # Check if OpenAI API key is available
    if not OPENAI_API_KEY:
        print("❌ ERROR: OpenAI API key not found!")
        print("Please set OPENAI_API_KEY environment variable")
        return {'success': False, 'error': 'No OpenAI API key'}
    
    # Test parameters
    conversation_history = ["USER: Can you get me The Dark Knight?"]
    
    print(f"📱 Request: Can you get me The Dark Knight?")
    print(f"🔑 OpenAI API Key: {'✅ Configured' if OPENAI_API_KEY else '❌ Missing'}")
    print()
    
    # Create services
    openai_client = OpenAIClient(OPENAI_API_KEY)
    movie_identification_service = MovieIdentificationService(openai_client)
    # Create TMDB client for movie library service
    from src.clients.tmdb_client import TMDBClient
    tmdb_client = TMDBClient(os.getenv('TMDB_API_KEY', ''))
    movie_library_service = MovieLibraryService(tmdb_client)
    radarr_service = RadarrService()
    notification_service = NotificationService()
    
    # Create agentic service
    agentic_service = AgenticService(openai_client)
    
    # Prepare services dictionary
    services = {
        'movie_identification': movie_identification_service,
        'movie_library': movie_library_service,
        'radarr': radarr_service,
        'notification': notification_service,
        'sms_response_prompt': SMS_RESPONSE_PROMPT
    }
    
    # Test the agentic service
    print("🤖 Step 1: Running AgenticService with REAL OpenAI calls...")
    result = agentic_service.process_agentic_response(conversation_history, services)
    
    # Get the response message
    response_message = result.get('response_message', '')
    success = result.get('success', False)
    function_results = result.get('function_results', [])
    
    print(f"📱 Agent Response: {response_message}")
    print(f"✅ Success: {success}")
    print(f"🔧 Function Results: {len(function_results)} functions called")
    
    # Log function results in detail
    for fr in function_results:
        function_name = fr['function_name']
        result_data = fr['result']
        print(f"  - {function_name}: {result_data.get('success', False)}")
        if not result_data.get('success', False):
            print(f"    Error: {result_data.get('error', 'Unknown error')}")
    
    print()
    
    # Step 2: Validate the response with REAL OpenAI
    print("🔍 Step 2: Validating response with REAL OpenAI...")
    
    validation_prompt = f"""
    Analyze this SMS response about a movie request for "The Dark Knight". 
    
    Response to analyze: "{response_message}"
    
    Does this response correctly:
    1. Acknowledge the movie request?
    2. Provide appropriate information about the movie status?
    3. Use appropriate tone for SMS communication?
    4. Handle the request professionally?
    
    Answer with YES or NO and explain why.
    """
    
    # Use REAL OpenAI for validation
    validation_result = openai_client.client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": validation_prompt}],
        max_tokens=200,
        temperature=0.3
    )
    
    validation_text = validation_result.choices[0].message.content.strip()
    print(f"🔍 OpenAI Validation: {validation_text}")
    print()
    
    # Results
    print("=" * 60)
    print("✅ TEST RESULTS:")
    print("=" * 60)
    print(f"📱 Agent Response: {response_message}")
    print(f"🔍 Validation: {validation_text}")
    
    # Check if validation is positive
    if "YES" in validation_text.upper():
        print("\n✅ SUCCESS: OpenAI confirms the response correctly handles movie request!")
    else:
        print("\n❌ FAILURE: OpenAI indicates the response needs improvement")
    
    return {
        'agent_response': response_message,
        'validation_result': validation_text,
        'success': "YES" in validation_text.upper(),
        'function_results': function_results
    }

def test_agentic_service_debug():
    """Test AgenticService with debug output to see the full workflow"""
    
    print("🔍 Testing AgenticService with Debug Output")
    print("=" * 60)
    
    # Check if OpenAI API key is available
    if not OPENAI_API_KEY:
        print("❌ ERROR: OpenAI API key not found!")
        print("Please set OPENAI_API_KEY environment variable")
        return {'success': False, 'error': 'No OpenAI API key'}
    
    # Test parameters
    conversation_history = ["USER: hey there"]
    
    print(f"📱 Request: hey there")
    print(f"🔑 OpenAI API Key: {'✅ Configured' if OPENAI_API_KEY else '❌ Missing'}")
    print()
    
    # Create services
    openai_client = OpenAIClient(OPENAI_API_KEY)
    movie_identification_service = MovieIdentificationService(openai_client)
    # Create TMDB client for movie library service
    from src.clients.tmdb_client import TMDBClient
    tmdb_client = TMDBClient(os.getenv('TMDB_API_KEY', ''))
    movie_library_service = MovieLibraryService(tmdb_client)
    radarr_service = RadarrService()
    notification_service = NotificationService()
    
    # Create agentic service
    agentic_service = AgenticService(openai_client)
    
    # Prepare services dictionary
    services = {
        'movie_identification': movie_identification_service,
        'movie_library': movie_library_service,
        'radarr': radarr_service,
        'notification': notification_service,
        'sms_response_prompt': SMS_RESPONSE_PROMPT
    }
    
    print("🤖 Running AgenticService with DEBUG OUTPUT...")
    print("=" * 40)
    print("🔍 You should see detailed debug logs below:")
    print("=" * 40)
    
    # Test the agentic service
    result = agentic_service.process_agentic_response(conversation_history, services)
    
    print("=" * 40)
    print("🔍 Debug output complete")
    print("=" * 40)
    
    # Get the response message
    response_message = result.get('response_message', '')
    success = result.get('success', False)
    function_results = result.get('function_results', [])
    
    print(f"📱 Final Response: {response_message}")
    print(f"✅ Success: {success}")
    print(f"🔧 Functions Called: {len(function_results)}")
    
    return {
        'agent_response': response_message,
        'success': success,
        'function_results': function_results
    }

def main():
    """Run AgenticService tests with command line options."""
    parser = argparse.ArgumentParser(description='Test AgenticService functionality')
    parser.add_argument('--casual-only', action='store_true', 
                       help='Run only casual conversation test')
    parser.add_argument('--movie-only', action='store_true', 
                       help='Run only movie request test')
    parser.add_argument('--debug-only', action='store_true', 
                       help='Run only debug output test')
    
    args = parser.parse_args()
    
    print("🎬 AgenticService Test Suite")
    print("=" * 50)
    print("⚠️  ONLY Redis is mocked - everything else is REAL")
    print()
    
    # Determine which tests to run
    run_casual = args.casual_only or (not args.movie_only and not args.debug_only)
    run_movie = args.movie_only or (not args.casual_only and not args.debug_only)
    run_debug = args.debug_only or (not args.casual_only and not args.movie_only)
    
    results = []
    
    # Run selected tests
    if run_casual:
        print("=" * 60)
        print("TEST 1: Casual Conversation Handling")
        print("=" * 60)
        result1 = test_casual_conversation()
        results.append(('casual', result1))
    
    if run_movie:
        print("\n" + "=" * 60)
        print("TEST 2: Movie Request Handling")
        print("=" * 60)
        result2 = test_movie_request()
        results.append(('movie', result2))
    
    if run_debug:
        print("\n" + "=" * 60)
        print("TEST 3: Debug Output Test")
        print("=" * 60)
        result3 = test_agentic_service_debug()
        results.append(('debug', result3))
    
    # Final summary
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)
    
    for test_name, result in results:
        if test_name == 'casual':
            if result.get('success'):
                print("✅ Test 1: The agent correctly handles casual conversation!")
            else:
                print("❌ Test 1: The agent needs improvement for casual conversation handling.")
        elif test_name == 'movie':
            if result.get('success'):
                print("✅ Test 2: The agent correctly handles movie requests!")
            else:
                print("❌ Test 2: The agent needs improvement for movie request handling.")
        elif test_name == 'debug':
            if result.get('success'):
                print("✅ Test 3: Debug output is working correctly!")
            else:
                print("❌ Test 3: Debug output needs improvement.")

if __name__ == '__main__':
    main()
