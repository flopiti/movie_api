#!/usr/bin/env python3
"""
Simple Plex connection test
"""

from plex_client import PlexClient
import json

def main():
    print("Simple Plex Connection Test")
    print("=" * 40)
    
    # Initialize Plex client
    plex = PlexClient()
    
    try:
        # Test basic connection - get libraries
        print("Testing basic connection...")
        libraries = plex.get_libraries()
        
        if not libraries:
            print("❌ No libraries found")
            return
        
        print(f"✅ Found {len(libraries)} libraries")
        
        # Show all libraries
        print("\nAll libraries:")
        for i, lib in enumerate(libraries):
            print(f"  {i+1}. {lib['title']} (ID: {lib['id']}, Type: {lib['type']})")
        
        # Show movie libraries specifically
        movie_libraries = [lib for lib in libraries if lib['type'] == 'movie']
        print(f"\nMovie libraries: {len(movie_libraries)}")
        for lib in movie_libraries:
            print(f"  - {lib['title']} (ID: {lib['id']})")
        
        # Test getting movie count
        print("\nTesting movie count...")
        counts = plex.get_movie_count()
        total = sum(counts.values())
        print(f"Total movies: {total}")
        
        for library, count in counts.items():
            print(f"  {library}: {count}")
        
        # Save basic info
        basic_info = {
            'total_libraries': len(libraries),
            'movie_libraries': len(movie_libraries),
            'total_movies': total,
            'libraries': [{'id': lib['id'], 'title': lib['title'], 'type': lib['type']} for lib in libraries],
            'movie_counts': counts
        }
        
        with open('plex_basic_info.json', 'w') as f:
            json.dump(basic_info, f, indent=2)
        
        print(f"\n✅ Basic info saved to plex_basic_info.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
