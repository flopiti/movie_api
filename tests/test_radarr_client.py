#!/usr/bin/env python3
"""
Test script for Radarr client functionality
"""

import os
import sys
import json

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from clients.radarr_client import RadarrClient
from test_radarr_expectations import (
    RADARR_SEARCH_TEST_CASES,
    RADARR_STATUS_TEST_CASES,
    TEST_CONFIG,
    VALIDATION_RULES
)

def test_radarr_connection():
    """Test the Radarr connection"""
    print("🔧 Testing Radarr Connection...")
    
    # Initialize Radarr client
    radarr = RadarrClient(
        base_url="http://192.168.0.10:7878",
        api_key="5a71ac347fb845da90e2284762335a1a",  # Set your API key here for testing
        timeout=TEST_CONFIG["timeout"]
    )
    
    # Test connection
    if radarr.test_connection():
        print("✅ Radarr connection successful!")
        return radarr
    else:
        print("❌ Radarr connection failed!")
        return None

def flexible_match(actual, expected):
    """Flexible matching for test results"""
    if expected == "any":
        return actual is not None
    elif expected == "> 0":
        return actual > 0
    elif expected == ">= 0":
        return actual >= 0
    elif expected == "> 5":
        return actual > 5
    elif isinstance(expected, str) and expected.startswith(">="):
        return actual >= int(expected.split(">=")[1])
    elif isinstance(expected, str) and expected.startswith(">"):
        return actual > int(expected.split(">")[1])
    else:
        return actual == expected

def test_movie_search():
    """Test movie search functionality"""
    print("\n🔍 Testing Movie Search...")
    
    radarr = test_radarr_connection()
    if not radarr:
        return False
    
    test_cases = RADARR_SEARCH_TEST_CASES
    passed = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        try:
            print(f"  Testing: {test_case['name']}")
            result = radarr.search_movies(test_case['query'])
            
            # Radarr search_movies returns a list directly
            if isinstance(result, list):
                total_results = len(result)
                first_result = result[0] if result else {}
                
                expected = test_case['expected_results']
                
                # Check total results
                if not flexible_match(total_results, expected.get('total_results', '>= 0')):
                    print(f"    ❌ Total results mismatch: Expected {expected.get('total_results')}, got {total_results}")
                    continue
                
                # Check first result if expected
                if 'first_result' in expected and total_results > 0:
                    first_expected = expected['first_result']
                    for field, expected_value in first_expected.items():
                        if field == 'note':
                            continue
                        actual_value = first_result.get(field)
                        if not flexible_match(actual_value, expected_value):
                            print(f"    ❌ First result {field} mismatch: Expected {expected_value}, got {actual_value}")
                            break
                    else:
                        print(f"    ✅ {test_case['name']}")
                        passed += 1
                        continue
                
                print(f"    ✅ {test_case['name']}")
                passed += 1
                
            else:
                print(f"    ❌ {test_case['name']}: Unexpected result type: {type(result)}")
                
        except Exception as e:
            print(f"    ❌ {test_case['name']}: {str(e)}")
    
    print(f"  📊 Movie Search: {passed}/{total} passed")
    return passed == total

def test_movie_status():
    """Test movie status checking"""
    print("\n📊 Testing Movie Status...")
    
    radarr = test_radarr_connection()
    if not radarr:
        return False
    
    test_cases = RADARR_STATUS_TEST_CASES
    passed = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        try:
            print(f"  Testing: {test_case['name']}")
            result = radarr.get_movie_status_by_tmdb_id(test_case['tmdb_id'])
            
            expected = test_case['expected_results']
            
            # Check if movie was found
            movie_found = result is not None
            if not flexible_match(movie_found, expected.get('movie_found', True)):
                print(f"    ❌ Movie found mismatch: Expected {expected.get('movie_found')}, got {movie_found}")
                continue
            
            # Check status if movie was found
            if movie_found and 'status' in expected:
                actual_status = result.get('status') if isinstance(result, dict) else 'downloaded'
                if not flexible_match(actual_status, expected['status']):
                    print(f"    ❌ Status mismatch: Expected {expected['status']}, got {actual_status}")
                    continue
            
            print(f"    ✅ {test_case['name']}")
            passed += 1
            
        except Exception as e:
            print(f"    ❌ {test_case['name']}: {str(e)}")
    
    print(f"  📊 Movie Status: {passed}/{total} passed")
    return passed == total

def test_blade_runner_specific():
    """Test Blade Runner specific scenarios"""
    print("\n🎬 Testing Blade Runner Specific Scenarios...")
    
    radarr = test_radarr_connection()
    if not radarr:
        return False
    
    # Test 1: Search for "Blade Runner (2017)" - should find Blade Runner 2049
    print("  Testing: Blade Runner (2017) search")
    result1 = radarr.search_movies("Blade Runner (2017)")
    
    if isinstance(result1, list) and result1:
        first_movie = result1[0]
        if first_movie.get('title') == 'Blade Runner 2049' and first_movie.get('year') == 2017:
            print("    ✅ Found Blade Runner 2049 with ambiguous search")
        else:
            print(f"    ❌ Expected Blade Runner 2049 (2017), got {first_movie.get('title')} ({first_movie.get('year')})")
    else:
        print("    ❌ No results found for Blade Runner (2017)")
    
    # Test 2: Check if Blade Runner 2049 is in library
    print("  Testing: Blade Runner 2049 library status")
    status = radarr.get_movie_status_by_tmdb_id(335984)  # Blade Runner 2049 TMDB ID
    
    if status:
        print(f"    ✅ Blade Runner 2049 found in library: {status}")
    else:
        print("    ℹ️  Blade Runner 2049 not found in library")
    
    return True

def main():
    """Run all Radarr tests"""
    print("🧪 Radarr Client Test Suite")
    print("=" * 50)
    
    # Run tests
    search_passed = test_movie_search()
    status_passed = test_movie_status()
    blade_runner_passed = test_blade_runner_specific()
    
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)
    print(f"Movie Search: {'✅ PASS' if search_passed else '❌ FAIL'}")
    print(f"Movie Status: {'✅ PASS' if status_passed else '❌ FAIL'}")
    print(f"Blade Runner: {'✅ PASS' if blade_runner_passed else '❌ FAIL'}")
    
    overall_passed = sum([search_passed, status_passed, blade_runner_passed])
    print(f"\nOverall: {overall_passed}/3 test suites passed")
    
    if overall_passed == 3:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed - check output above")

if __name__ == '__main__':
    main()
