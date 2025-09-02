#!/usr/bin/env python3
"""
Quick Plex Movie Count Checker
Simple script to get movie count from Plex
"""

import os
from plex_movie_checker import PlexMovieChecker

def main():
    """Quick check of Plex movie count"""
    print("🎬 Quick Plex Movie Count Check")
    print("=" * 40)
    
    # Configuration
    base_url = "http://natetrystuff.com:32400"
    token = os.getenv('PLEX_TOKEN')  # Set this if needed
    
    # Create checker
    checker = PlexMovieChecker(base_url, token)
    
    # Connect and get movies
    if not checker.connect():
        print("❌ Failed to connect to Plex")
        return
    
    movies = checker.get_movies()
    if not movies:
        print("❌ No movies found in Plex")
        return
    
    movie_details = checker.get_movie_details(movies)
    
    print(f"\n📊 PLEX MOVIE COUNT: {len(movie_details)}")
    print(f"📁 Total movie files recognized by Plex")
    
    # Show breakdown by library if multiple libraries
    libraries = {}
    for movie in movies:
        if hasattr(movie, 'librarySectionTitle'):
            lib_name = movie.librarySectionTitle
            if lib_name not in libraries:
                libraries[lib_name] = 0
            libraries[lib_name] += 1
    
    if len(libraries) > 1:
        print(f"\n📂 Breakdown by library:")
        for lib_name, count in libraries.items():
            print(f"   {lib_name}: {count} movies")

if __name__ == "__main__":
    main()
