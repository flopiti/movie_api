#!/usr/bin/env python3
"""
Test script to verify Plex connection and get movie counts
"""

from plex_client import PlexClient

def main():
    print("Testing Plex connection to natetrystuff.com:32400")
    print("=" * 50)
    
    # Initialize Plex client
    plex = PlexClient()
    
    try:
        # Get libraries
        print("Fetching libraries...")
        libraries = plex.get_libraries()
        
        if not libraries:
            print("❌ No libraries found or connection failed")
            return
        
        print(f"✅ Found {len(libraries)} libraries")
        
        # Show movie libraries
        movie_libraries = [lib for lib in libraries if lib['type'] == 'movie']
        print(f"\nMovie libraries found: {len(movie_libraries)}")
        
        for lib in movie_libraries:
            print(f"  - {lib['title']} (ID: {lib['id']}) - Count: {lib.get('count', 'Unknown')}")
        
        # Get movie counts
        print("\n" + "=" * 50)
        print("MOVIE COUNTS BY LIBRARY:")
        counts = plex.get_movie_count()
        total_count = sum(counts.values())
        
        for library, count in counts.items():
            print(f"  {library}: {count} movies")
        
        print(f"\nTotal movies in Plex: {total_count}")
        
        # Get detailed movie list (first 10 for testing)
        print("\n" + "=" * 50)
        print("SAMPLE MOVIES (first 10):")
        
        all_movies = plex.get_all_movies()
        print(f"Retrieved {len(all_movies)} movies total")
        
        for i, movie in enumerate(all_movies[:10]):
            print(f"  {i+1}. {movie['title']} ({movie.get('year', 'N/A')})")
            if movie.get('media') and movie['media'][0].get('part'):
                file_path = movie['media'][0]['part'][0].get('file', 'Unknown')
                print(f"     File: {file_path}")
        
        print(f"\n✅ Plex connection working - {total_count} movies found")
        print("Use the API endpoints to access this data from your frontend")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure your Plex server is accessible at natetrystuff.com:32400")

if __name__ == "__main__":
    main()
