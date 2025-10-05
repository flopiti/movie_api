#!/usr/bin/env python3
"""
Test OpenAI Client functionality
Test individual OpenAI client methods to verify they return expected results.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from the main project's env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', 'env'))

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from clients.openai_client import OpenAIClient
from test_openai_expectations import (
    MOVIE_DETECTION_TEST_CASES,
    SMS_RESPONSE_TEST_CASES,
    FILENAME_CLEANING_TEST_CASES,
    AGENTIC_RESPONSE_TEST_CASES,
    EXPECTED_RESPONSE_PATTERNS,
    VALIDATION_RULES
)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def flexible_movie_match(detected_movie, expected_movie):
    """Compare movie titles flexibly, accepting both with and without year formats."""
    if detected_movie == expected_movie:
        return True
    
    # Normalize both titles for flexible comparison
    def normalize_title(title):
        """Normalize title for flexible comparison."""
        if not title:
            return ""
        
        # Convert to lowercase
        normalized = title.lower()
        
        # Remove extra spaces
        import re
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Handle possessive forms before removing apostrophes
        # Convert possessive forms like "Tiffany's" to "Tiffany"
        normalized = re.sub(r"'s\b", "", normalized)
        
        # Remove common punctuation differences (apostrophes, quotes)
        normalized = normalized.replace("'", "").replace("'", "").replace("'", "").replace("'", "")
        
        # Remove "The" prefix
        if normalized.startswith('the '):
            normalized = normalized[4:]
        
        return normalized
    
    # Compare normalized titles
    normalized_detected = normalize_title(detected_movie)
    normalized_expected = normalize_title(expected_movie)
    
    if normalized_detected == normalized_expected:
        return True
    
    # If expected has year but detected doesn't, check if base titles match
    if expected_movie and '(' in expected_movie:
        expected_base = expected_movie.split(' (')[0]
        if normalize_title(detected_movie) == normalize_title(expected_base):
            return True
    
    # If detected has year but expected doesn't, check if base titles match
    if detected_movie and '(' in detected_movie:
        detected_base = detected_movie.split(' (')[0]
        if normalize_title(detected_base) == normalize_title(expected_movie):
            return True
    
    # Also check if one has year and the other doesn't, with normalized titles
    if expected_movie and '(' in expected_movie:
        expected_base = normalize_title(expected_movie.split(' (')[0])
        if normalized_detected == expected_base:
            return True
    
    if detected_movie and '(' in detected_movie:
        detected_base = normalize_title(detected_movie.split(' (')[0])
        if detected_base == normalized_expected:
            return True
    
    # Handle possessive forms - check if one ends with 's' and the other doesn't
    if normalized_detected.endswith('s') and not normalized_expected.endswith('s'):
        # Try removing the 's' from detected
        if normalized_detected[:-1] == normalized_expected:
            return True
    elif normalized_expected.endswith('s') and not normalized_detected.endswith('s'):
        # Try removing the 's' from expected
        if normalized_expected[:-1] == normalized_detected:
            return True
    
    return False
 
def test_openai_connection():
    """Test if OpenAI client can be initialized and connected."""
    print("🔧 Testing OpenAI Client Connection...")
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key not configured in environment")
        return False
    
    try:
        client = OpenAIClient(OPENAI_API_KEY)
        if client.client:
            print("✅ OpenAI client initialized successfully")
            return True
        else:
            print("❌ OpenAI client failed to initialize")
            return False
    except Exception as e:
        print(f"❌ Error initializing OpenAI client: {str(e)}")
        return False

def test_movie_detection():
    """Test movie detection from conversation history."""
    print("\n🎬 Testing Movie Detection...")
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key not configured")
        return False
    
    client = OpenAIClient(OPENAI_API_KEY)
    test_cases = MOVIE_DETECTION_TEST_CASES
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            result = client.getMovieName(test_case['conversation'])
            
            if result.get('success'):
                detected_movie = result.get('movie_name')
                if detected_movie == "No movie identified":
                    detected_movie = None
                
                if flexible_movie_match(detected_movie, test_case['expected_movie']):
                    print(f"  ✅ {test_case['name']}")
                    passed += 1
                else:
                    print(f"  ❌ {test_case['name']}: Expected '{test_case['expected_movie']}', got '{detected_movie}'")
            else:
                print(f"  ❌ {test_case['name']}: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ {test_case['name']}: {str(e)}")
    
    print(f"\n📊 Movie Detection: {passed}/{total} passed")
    return passed == total

def test_sms_response_generation():
    """Test SMS response generation."""
    print("\n💬 Testing SMS Response Generation...")
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key not configured")
        return False
    
    client = OpenAIClient(OPENAI_API_KEY)
    test_cases = SMS_RESPONSE_TEST_CASES
    passed = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        try:
            from clients.PROMPTS import SMS_RESPONSE_PROMPT
            
            result = client.generate_sms_response(
                message=test_case['message'],
                sender=test_case['sender'],
                prompt_template=SMS_RESPONSE_PROMPT,
                movie_context=test_case['movie_context']
            )
            
            if result.get('success'):
                response = result.get('response', '')
                expected_keywords = test_case.get('expected_keywords', [])
                if expected_keywords:
                    found_keywords = [kw for kw in expected_keywords if kw.lower() in response.lower()]
                    if len(found_keywords) == len(expected_keywords):
                        print(f"  ✅ {test_case['name']}")
                        passed += 1
                    else:
                        missing_keywords = [kw for kw in expected_keywords if kw.lower() not in response.lower()]
                        print(f"  ❌ {test_case['name']}: Missing keywords {missing_keywords}")
                else:
                    print(f"  ✅ {test_case['name']}")
                    passed += 1
            else:
                print(f"  ❌ {test_case['name']}: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ {test_case['name']}: {str(e)}")
    
    print(f"  📊 SMS Response: {passed}/{total} passed")
    return passed == total

def test_filename_cleaning():
    """Test filename cleaning functionality."""
    print("\n📁 Testing Filename Cleaning...")
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key not configured")
        return False
    
    client = OpenAIClient(OPENAI_API_KEY)
    test_cases = FILENAME_CLEANING_TEST_CASES
    passed = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        filename = test_case['filename']
        expected_title = test_case['expected_title']
        
        try:
            result = client.clean_filename(filename)
            
            if result.get('success'):
                cleaned_title = result.get('cleaned_title', '')
                if cleaned_title == expected_title:
                    print(f"  ✅ {filename}")
                    passed += 1
                else:
                    print(f"  ❌ {filename}: Expected '{expected_title}', got '{cleaned_title}'")
            else:
                print(f"  ❌ {filename}: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ {filename}: {str(e)}")
    
    print(f"  📊 Filename Cleaning: {passed}/{total} passed")
    return passed == total

def test_generate_agentic_response():
    """Test generate_agentic_response functionality."""
    print("\n🤖 Testing Generate Agentic Response...")
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key not configured")
        return False
    
    client = OpenAIClient(OPENAI_API_KEY)
    test_cases = AGENTIC_RESPONSE_TEST_CASES
    passed = 0
    total = len(test_cases)
    
    # Import the function schema for testing
    from clients.PROMPTS import MOVIE_AGENT_FUNCTION_SCHEMA
    

    for test_case in test_cases:
        try:
            result = client.generate_agentic_response(
                prompt=test_case['prompt'],
                functions=MOVIE_AGENT_FUNCTION_SCHEMA
            )

            # Organize success logic: all must be True for success
            success = (
                result.get('success') == test_case['expected_success'] and
                result.get('has_function_calls') == test_case['expected_has_function_calls']
            )

            # If function calls are expected, also check function name if provided
            if test_case.get('expected_has_function_calls') and test_case.get('expected_function_name'):
                # Try to get function name from tool_calls if not present at top level
                function_name = result.get('function_name')
                if not function_name and result.get('tool_calls'):
                    # Try to extract from first tool_call if possible
                    tool_calls = result.get('tool_calls')
                    if isinstance(tool_calls, list) and tool_calls:
                        # Try to get function name from OpenAI tool_call structure
                        function_call = getattr(tool_calls[0], 'function', None)
                        if function_call and hasattr(function_call, 'name'):
                            function_name = function_call.name
                        elif isinstance(tool_calls[0], dict):
                            # fallback for dict structure
                            function_name = tool_calls[0].get('function', {}).get('name')
                if function_name != test_case['expected_function_name']:
                    print(f"  ❌ {test_case['name']}: Expected function_name={test_case['expected_function_name']}, got {function_name}")
                    success = False

            if result.get('success') != test_case['expected_success']:
                print(f"  ❌ {test_case['name']}: Expected success={test_case['expected_success']}, got {result.get('success')}")
                success = False
            if result.get('has_function_calls') != test_case['expected_has_function_calls']:
                print(f"  ❌ {test_case['name']}: Expected has_function_calls={test_case['expected_has_function_calls']}, got {result.get('has_function_calls')}")
                success = False



            if success:
                print(f"  ✅ {test_case['name']}")
                passed += 1

        except Exception as e:
            print(f"  ❌ {test_case['name']}: {str(e)}")
    
    print(f"  📊 Agentic Response: {passed}/{total} passed")
    return passed == total

def main():
    """Run OpenAI client tests with command line options."""
    parser = argparse.ArgumentParser(description='Test OpenAI Client functionality')
    parser.add_argument('--movie-only', action='store_true', 
                       help='Run only movie detection tests')
    parser.add_argument('--sms-only', action='store_true', 
                       help='Run only SMS response tests')
    parser.add_argument('--filename-only', action='store_true', 
                       help='Run only filename cleaning tests')
    parser.add_argument('--agentic-only', action='store_true', 
                       help='Run only agentic response tests')
    
    args = parser.parse_args()
    
    print("🧪 OpenAI Client Test Suite")
    print("=" * 50)
    
    # Test connection first
    if not test_openai_connection():
        print("\n❌ Cannot proceed without OpenAI connection")
        return
    
    # Determine which tests to run
    run_movie = args.movie_only or (not args.sms_only and not args.filename_only and not args.agentic_only)
    run_sms = args.sms_only or (not args.movie_only and not args.filename_only and not args.agentic_only)
    run_filename = args.filename_only or (not args.movie_only and not args.sms_only and not args.agentic_only)
    run_agentic = args.agentic_only or (not args.movie_only and not args.sms_only and not args.filename_only)
    
    # Run selected tests
    movie_result = test_movie_detection() if run_movie else None
    sms_result = test_sms_response_generation() if run_sms else None
    filename_result = test_filename_cleaning() if run_filename else None
    agentic_result = test_generate_agentic_response() if run_agentic else None
    
    # Final summary
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)
    
    results = [r for r in [movie_result, sms_result, filename_result, agentic_result] if r is not None]
    total_tests = len(results)
    passed_tests = sum(results)
    
    if run_movie:
        print(f"Movie Detection: {'✅ PASS' if movie_result else '❌ FAIL'}")
    if run_sms:
        print(f"SMS Response:   {'✅ PASS' if sms_result else '❌ FAIL'}")
    if run_filename:
        print(f"Filename Clean: {'✅ PASS' if filename_result else '❌ FAIL'}")
    if run_agentic:
        print(f"Agentic Response: {'✅ PASS' if agentic_result else '❌ FAIL'}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} test suites passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed - check output above")

if __name__ == "__main__":
    main()
