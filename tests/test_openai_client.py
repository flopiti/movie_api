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
    EXPECTED_RESPONSE_PATTERNS,
    VALIDATION_RULES
)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def flexible_movie_match(detected_movie, expected_movie):
    """Compare movie titles flexibly, accepting both with and without year formats."""
    if detected_movie == expected_movie:
        return True
    
    # If expected has year but detected doesn't, check if base titles match
    if expected_movie and '(' in expected_movie:
        expected_base = expected_movie.split(' (')[0]
        if detected_movie == expected_base:
            return True
    
    # If detected has year but expected doesn't, check if base titles match
    if detected_movie and '(' in detected_movie:
        detected_base = detected_movie.split(' (')[0]
        if detected_base == expected_movie:
            return True
    
    # Handle "The" prefix differences
    def normalize_title(title):
        """Remove 'The' prefix for comparison."""
        if title and title.startswith('The '):
            return title[4:]  # Remove "The "
        return title
    
    # Compare normalized titles (without "The")
    normalized_detected = normalize_title(detected_movie)
    normalized_expected = normalize_title(expected_movie)
    
    if normalized_detected == normalized_expected:
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
    
    for test_case in test_cases:
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
    
    print(f"  📊 Movie Detection: {passed}/{total} passed")
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
                    if found_keywords:
                        print(f"  ✅ {test_case['name']}")
                        passed += 1
                    else:
                        print(f"  ❌ {test_case['name']}: Missing keywords {expected_keywords}")
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

def main():
    """Run OpenAI client tests with command line options."""
    parser = argparse.ArgumentParser(description='Test OpenAI Client functionality')
    parser.add_argument('--movie-only', action='store_true', 
                       help='Run only movie detection tests')
    parser.add_argument('--sms-only', action='store_true', 
                       help='Run only SMS response tests')
    parser.add_argument('--filename-only', action='store_true', 
                       help='Run only filename cleaning tests')
    
    args = parser.parse_args()
    
    print("🧪 OpenAI Client Test Suite")
    print("=" * 50)
    
    # Test connection first
    if not test_openai_connection():
        print("\n❌ Cannot proceed without OpenAI connection")
        return
    
    # Determine which tests to run
    run_movie = args.movie_only or (not args.sms_only and not args.filename_only)
    run_sms = args.sms_only or (not args.movie_only and not args.filename_only)
    run_filename = args.filename_only or (not args.movie_only and not args.sms_only)
    
    # Run selected tests
    movie_result = test_movie_detection() if run_movie else None
    sms_result = test_sms_response_generation() if run_sms else None
    filename_result = test_filename_cleaning() if run_filename else None
    
    # Final summary
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)
    
    results = [r for r in [movie_result, sms_result, filename_result] if r is not None]
    total_tests = len(results)
    passed_tests = sum(results)
    
    if run_movie:
        print(f"Movie Detection: {'✅ PASS' if movie_result else '❌ FAIL'}")
    if run_sms:
        print(f"SMS Response:   {'✅ PASS' if sms_result else '❌ FAIL'}")
    if run_filename:
        print(f"Filename Clean: {'✅ PASS' if filename_result else '❌ FAIL'}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} test suites passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed - check output above")

if __name__ == "__main__":
    main()
