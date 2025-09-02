#!/usr/bin/env python3
"""
Plex API Diagnostic Tool
"""

import requests
import xml.etree.ElementTree as ET
from plex_client import PlexClient

def test_basic_connection():
    """Test basic Plex server connection"""
    print("Testing basic Plex server connection...")
    
    try:
        response = requests.get("http://natetrystuff.com:32400/")
        print(f"Server response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Basic connection successful")
            return True
        else:
            print(f"❌ Server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_libraries_endpoint():
    """Test the libraries endpoint"""
    print("\nTesting libraries endpoint...")
    
    try:
        response = requests.get("http://natetrystuff.com:32400/library/sections")
        print(f"Libraries endpoint response: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Libraries endpoint accessible")
            root = ET.fromstring(response.content)
            directories = root.findall('.//Directory')
            print(f"Found {len(directories)} libraries")
            
            for directory in directories:
                lib_id = directory.get('key')
                lib_title = directory.get('title')
                lib_type = directory.get('type')
                lib_count = directory.get('count')
                print(f"  - {lib_title} (ID: {lib_id}, Type: {lib_type}, Count: {lib_count})")
            
            return True
        else:
            print(f"❌ Libraries endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Libraries endpoint failed: {e}")
        return False

def test_specific_library(library_id):
    """Test access to a specific library"""
    print(f"\nTesting library {library_id} access...")
    
    try:
        # Test library info endpoint
        info_url = f"http://natetrystuff.com:32400/library/sections/{library_id}"
        response = requests.get(info_url)
        print(f"Library info response: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Library info accessible")
            
            # Test library contents endpoint without parameters
            contents_url = f"http://natetrystuff.com:32400/library/sections/{library_id}/all"
            response = requests.get(contents_url)
            print(f"Library contents response (no params): {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Library contents accessible without parameters")
                root = ET.fromstring(response.content)
                videos = root.findall('.//Video')
                print(f"Found {len(videos)} videos")
                
                # Show first few videos
                for i, video in enumerate(videos[:3]):
                    title = video.get('title', 'Unknown')
                    year = video.get('year', 'N/A')
                    print(f"  {i+1}. {title} ({year})")
                
                return True
            else:
                print(f"❌ Library contents returned {response.status_code}")
                return False
        else:
            print(f"❌ Library info returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Library test failed: {e}")
        return False

def test_with_plex_client():
    """Test using the PlexClient class"""
    print("\nTesting with PlexClient class...")
    
    plex = PlexClient()
    
    # Test library access
    if plex.test_library_access("1"):
        print("✅ PlexClient can access library 1")
    else:
        print("❌ PlexClient cannot access library 1")
    
    # Test getting movies
    try:
        movies = plex.get_movies_from_library("1", limit=5)
        print(f"✅ Retrieved {len(movies)} movies")
    except Exception as e:
        print(f"❌ Failed to get movies: {e}")

def main():
    print("Plex API Diagnostic Tool")
    print("=" * 50)
    
    # Test basic connection
    if not test_basic_connection():
        print("Cannot proceed - basic connection failed")
        return
    
    # Test libraries endpoint
    if not test_libraries_endpoint():
        print("Cannot proceed - libraries endpoint failed")
        return
    
    # Test specific library
    test_specific_library("1")
    
    # Test with PlexClient
    test_with_plex_client()
    
    print("\n" + "=" * 50)
    print("Diagnostic complete")

if __name__ == "__main__":
    main()
