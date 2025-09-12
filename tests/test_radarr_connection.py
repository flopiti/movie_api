#!/usr/bin/env python3
"""
Test script for Radarr integration
"""

import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.radarr_client import RadarrClient

def test_radarr_connection():
    """Test the Radarr connection and basic functionality"""
    print("Testing Radarr integration...")
    print("Radarr URL: http://192.168.0.10:7878")
    print("API Key: [Not configured - set in app.py]")
    print()
    
    # Initialize Radarr client with default values
    radarr = RadarrClient(
        base_url="http://192.168.0.10:7878",
        api_key="5a71ac347fb845da90e2284762335a1a",  # Set your API key here for testing
        timeout=30
    )
    
    # Test connection
    print("1. Testing connection...")
    if radarr.test_connection():
        print("✓ Connection successful!")
    else:
        print("✗ Connection failed!")
        return False
    
    # Get system status
    print("\n2. Getting system status...")
    status = radarr.get_system_status()
    if status:
        print("✓ System status retrieved:")
        print(f"  - Version: {status.get('version', 'Unknown')}")
        print(f"  - App Name: {status.get('appName', 'Unknown')}")
    else:
        print("✗ Failed to get system status")
    
    # Get movie count
    print("\n3. Getting movie count...")
    count = radarr.get_movie_count()
    print(f"✓ Movie count: {count}")
    
    # Get movies (limit to first 5 for testing)
    print("\n4. Getting movies (first 5)...")
    movies = radarr.get_movies()
    if movies:
        print(f"✓ Retrieved {len(movies)} movies")
        for i, movie in enumerate(movies[:5]):
            title = movie.get('title', 'Unknown')
            year = movie.get('year', 'Unknown')
            print(f"  {i+1}. {title} ({year})")
    else:
        print("✗ Failed to retrieve movies")
    
    print("\n✓ Radarr integration test completed!")
    return True

if __name__ == '__main__':
    test_radarr_connection()
