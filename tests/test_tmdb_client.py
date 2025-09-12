#!/usr/bin/env python3
"""
TMDB Client Test Suite
Tests the TMDB client functionality using the expectations defined in test_tmdb_expectations.py
"""

import sys
import os
import time
import json
from typing import Dict, Any, List

# Add the src directory to the path so we can import the TMDB client
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from clients.tmdb_client import TMDBClient
from test_tmdb_expectations import (
    MOVIE_SEARCH_TEST_CASES,
    TEST_CONFIG
)

class TMDBTestRunner:
    """Test runner for TMDB client tests."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._load_api_key_from_env()
        self.client = TMDBClient(self.api_key) if self.api_key else None
        self.results = []
        self.verbose = TEST_CONFIG.get('verbose_output', True)
    
    def _load_api_key_from_env(self) -> str:
        """Load API key from the env file."""
        env_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'env')
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('TMDB_API_KEY'):
                        return line.split('=')[1].strip().strip("'\"")
        except FileNotFoundError:
            pass
        return None
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message if verbose output is enabled."""
        if self.verbose:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{timestamp} - {level} - {message}")
    
    def run_movie_search_tests(self) -> List[Dict[str, Any]]:
        """Run movie search test cases."""
        self.log("🎬 Starting Movie Search Tests")
        results = []
        
        for test_case in MOVIE_SEARCH_TEST_CASES:
            self.log(f"Testing: {test_case['name']}")
            
            start_time = time.time()
            try:
                response = self.client.search_movie(test_case['query'])
                end_time = time.time()
                
                result = {
                    'test_name': test_case['name'],
                    'query': test_case['query'],
                    'success': True,
                    'response_time': end_time - start_time,
                    'response': response,
                    'expected': test_case['expected_results']
                }
                
                # Validate the response
                validation_result = self.validate_movie_search_response(result)
                result['validation'] = validation_result
                
                if validation_result['passed']:
                    self.log(f"✅ {test_case['name']} - PASSED")
                else:
                    self.log(f"❌ {test_case['name']} - FAILED: {validation_result['errors']}", "ERROR")
                
            except Exception as e:
                result = {
                    'test_name': test_case['name'],
                    'query': test_case['query'],
                    'success': False,
                    'error': str(e),
                    'expected': test_case['expected_results']
                }
                self.log(f"❌ {test_case['name']} - ERROR: {str(e)}", "ERROR")
            
            results.append(result)
        
        return results
    
    
    def _flexible_match(self, actual_value: Any, expected_value: Any) -> bool:
        """Perform flexible matching for test validation."""
        if expected_value == "any":
            return True
        
        if isinstance(expected_value, str) and expected_value.endswith("*"):
            # Wildcard matching for dates like "1999-03-*"
            prefix = expected_value[:-1]
            return str(actual_value).startswith(prefix)
        
        return actual_value == expected_value
    
    def validate_movie_search_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a movie search response."""
        response = result['response']
        expected = result['expected']
        errors = []
        
        # Check required fields
        required_fields = VALIDATION_RULES['movie_search']['required_fields']
        for field in required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")
        
        # Check success condition
        if response.get('success') != expected.get('success', True):
            errors.append(f"Success mismatch: got {response.get('success')}, expected {expected.get('success', True)}")
        
        # Check total results
        if 'total_results' in expected:
            expected_total = expected['total_results']
            actual_total = response.get('total_results', 0)
            
            if isinstance(expected_total, str) and expected_total.startswith('>'):
                min_expected = int(expected_total[1:])
                if actual_total <= min_expected:
                    errors.append(f"Total results too low: got {actual_total}, expected > {min_expected}")
            elif isinstance(expected_total, str) and expected_total.startswith('>='):
                min_expected = int(expected_total[2:].strip())
                if actual_total < min_expected:
                    errors.append(f"Total results too low: got {actual_total}, expected >= {min_expected}")
            elif isinstance(expected_total, str) and expected_total == ">= 0":
                # This is always true, so no validation needed
                pass
            elif actual_total != expected_total:
                errors.append(f"Total results mismatch: got {actual_total}, expected {expected_total}")
        
        # Check year matches
        if 'year_matches' in expected:
            expected_year_matches = expected['year_matches']
            actual_year_matches = response.get('year_matches', 0)
            
            if isinstance(expected_year_matches, str) and expected_year_matches.startswith('>'):
                min_expected = int(expected_year_matches[1:])
                if actual_year_matches <= min_expected:
                    errors.append(f"Year matches too low: got {actual_year_matches}, expected > {min_expected}")
            elif isinstance(expected_year_matches, str) and expected_year_matches.startswith('>='):
                min_expected = int(expected_year_matches[2:].strip())
                if actual_year_matches < min_expected:
                    errors.append(f"Year matches too low: got {actual_year_matches}, expected >= {min_expected}")
            elif isinstance(expected_year_matches, str) and expected_year_matches == ">= 0":
                # This is always true, so no validation needed
                pass
            elif actual_year_matches != expected_year_matches:
                errors.append(f"Year matches mismatch: got {actual_year_matches}, expected {expected_year_matches}")
        
        # Check first result if expected
        if 'first_result' in expected and response.get('results'):
            first_result = response['results'][0]
            expected_first = expected['first_result']
            
            for field, expected_value in expected_first.items():
                if field not in first_result:
                    errors.append(f"Missing field in first result: {field}")
                elif not self._flexible_match(first_result[field], expected_value):
                    errors.append(f"First result {field} mismatch: got {first_result[field]}, expected {expected_value}")
        
        return {
            'passed': len(errors) == 0,
            'errors': errors
        }
    
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run movie search tests only."""
        self.log("🚀 Starting TMDB Client Test Suite")
        
        if not self.client:
            self.log("❌ No TMDB API key provided. Set TMDB_API_KEY environment variable.", "ERROR")
            return {'error': 'No API key provided'}
        
        # Run only movie search tests
        results = self.run_movie_search_tests()
        
        # Calculate summary statistics
        total_tests = len(results)
        passed_tests = sum(1 for result in results if result.get('validation', {}).get('passed', False))
        
        summary = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }
        
        self.log(f"📊 Test Summary: {passed_tests}/{total_tests} tests passed ({summary['success_rate']:.1f}%)")
        
        return {
            'summary': summary,
            'results': {'movie_search': results},
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def save_results(self, results: Dict[str, Any]):
        """Save test results to file."""
        if TEST_CONFIG.get('save_results', False):
            results_file = TEST_CONFIG.get('results_file', 'tmdb_test_results.json')
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            self.log(f"💾 Results saved to {results_file}")

def main():
    """Main test runner."""
    print("🎬 TMDB Client Test Suite")
    print("=" * 50)
    
    # Run tests (API key will be loaded from env file)
    test_runner = TMDBTestRunner()
    if not test_runner.api_key:
        print("❌ TMDB_API_KEY not found in config/env file!")
        print("Please check that the API key is set in config/env")
        return
    
    print(f"✅ Using TMDB API key: {test_runner.api_key[:8]}...")
    results = test_runner.run_all_tests()
    
    # Save results if configured
    test_runner.save_results(results)
    
    # Print final summary
    summary = results.get('summary', {})
    print("\n" + "=" * 50)
    print("FINAL SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {summary.get('total_tests', 0)}")
    print(f"Passed: {summary.get('passed_tests', 0)}")
    print(f"Failed: {summary.get('failed_tests', 0)}")
    print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
    
    if summary.get('failed_tests', 0) > 0:
        print("\n❌ Some tests failed. Check the logs above for details.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")

if __name__ == "__main__":
    main()
