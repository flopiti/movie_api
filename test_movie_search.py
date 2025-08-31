#!/usr/bin/env python3
"""
Test script for the enhanced movie search functionality.
This demonstrates how the API now uses OpenAI to clean filenames before searching TMDB.
"""

import requests
import json

# API endpoint
BASE_URL = "http://localhost:5000"

def test_movie_search(filename):
    """Test the movie search endpoint with a filename."""
    print(f"\n{'='*60}")
    print(f"Testing filename: {filename}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(f"{BASE_URL}/search-movie", params={"q": filename})
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"Original query: {data['original_query']}")
            print(f"OpenAI processing: {data['openai_processing']}")
            print(f"TMDB search query: {data['tmdb_search_query']}")
            
            tmdb_results = data['tmdb_results']
            if 'results' in tmdb_results and tmdb_results['results']:
                print(f"\nTMDB found {len(tmdb_results['results'])} results:")
                for i, movie in enumerate(tmdb_results['results'][:3]):  # Show top 3
                    print(f"  {i+1}. {movie['title']} ({movie.get('release_date', 'Unknown')[:4]})")
                    print(f"     Overview: {movie['overview'][:100]}...")
            else:
                print("No TMDB results found")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API. Make sure the server is running on localhost:5000")
    except Exception as e:
        print(f"Error: {str(e)}")

def test_health():
    """Test the health endpoint to check API configuration."""
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print("API Health Check:")
            print(f"  Status: {data['status']}")
            print(f"  TMDB configured: {data['tmdb_configured']}")
            print(f"  OpenAI configured: {data['openai_configured']}")
            print(f"  Movie paths: {data['movie_paths_count']}")
            return data['openai_configured'] and data['tmdb_configured']
        else:
            print(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Health check error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Movie Search API Test")
    print("This test demonstrates the new OpenAI + TMDB integration")
    
    # Check if APIs are configured
    if not test_health():
        print("\nWarning: API not fully configured. Make sure to set your OpenAI API key in the env file.")
        print("The test will continue but may not work properly.")
    
    # Test cases with messy filenames
    test_filenames = [
        "The.Matrix.1999.1080p.BluRay.x264-YIFY.mp4",
        "Inception_2010_720p_WEBRip_[RARBG].mkv",
        "Pulp.Fiction.(1994).4K.UHD.HDR.mp4",
        "The_Dark_Knight_2008_IMAX_1080p_BluRay_x265.mkv",
        "Interstellar.2014.2160p.4K.UHD.BluRay.x265-RARBG.mp4"
    ]
    
    for filename in test_filenames:
        test_movie_search(filename)
    
    print(f"\n{'='*60}")
    print("Test complete! Check the logs for detailed processing information.")
    print("Log file: movie_api.log")
