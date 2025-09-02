#!/usr/bin/env python3
"""
Plex Movie Checker
Connects to Plex instance and retrieves movie information
"""

import os
from plexapi.server import PlexServer
from plexapi.exceptions import PlexApiException
import json
from datetime import datetime

class PlexMovieChecker:
    def __init__(self, base_url, token=None):
        """
        Initialize Plex connection
        
        Args:
            base_url (str): Plex server URL (e.g., 'http://natetrystuff.com:32400')
            token (str, optional): Plex authentication token
        """
        self.base_url = base_url
        self.token = token
        self.plex = None
        
    def connect(self):
        """Connect to Plex server"""
        try:
            if self.token:
                self.plex = PlexServer(self.base_url, self.token)
            else:
                # Try to connect without token (may work for local networks)
                self.plex = PlexServer(self.base_url)
            print(f"✅ Successfully connected to Plex server: {self.base_url}")
            return True
        except PlexApiException as e:
            print(f"❌ Failed to connect to Plex server: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error connecting to Plex: {e}")
            return False
    
    def get_movies(self):
        """Get all movies from Plex"""
        if not self.plex:
            print("❌ Not connected to Plex server")
            return []
        
        try:
            # Get all movie libraries
            movie_libraries = self.plex.library.sections()
            movies = []
            
            for library in movie_libraries:
                if library.type == 'movie':
                    print(f"📁 Found movie library: {library.title}")
                    library_movies = library.all()
                    movies.extend(library_movies)
                    print(f"   Found {len(library_movies)} movies in {library.title}")
            
            return movies
        except Exception as e:
            print(f"❌ Error getting movies: {e}")
            return []
    
    def get_movie_details(self, movies):
        """Extract detailed information from movies"""
        movie_details = []
        
        for movie in movies:
            try:
                detail = {
                    'title': movie.title,
                    'year': movie.year,
                    'rating': movie.rating,
                    'duration': movie.duration,
                    'summary': movie.summary,
                    'genres': [genre.tag for genre in movie.genres] if movie.genres else [],
                    'file_path': movie.locations[0] if movie.locations else None,
                    'plex_id': movie.ratingKey,
                    'added_at': movie.addedAt.isoformat() if movie.addedAt else None,
                    'updated_at': movie.updatedAt.isoformat() if movie.updatedAt else None,
                    'view_count': movie.viewCount,
                    'last_viewed': movie.lastViewedAt.isoformat() if movie.lastViewedAt else None
                }
                movie_details.append(detail)
            except Exception as e:
                print(f"⚠️ Error processing movie {movie.title}: {e}")
                continue
        
        return movie_details
    
    def save_to_file(self, movies, filename=None):
        """Save movie details to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plex_movies_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(movies, f, indent=2, ensure_ascii=False)
            print(f"💾 Movie details saved to: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Error saving to file: {e}")
            return None
    
    def print_summary(self, movies):
        """Print a summary of the movies found"""
        if not movies:
            print("📋 No movies found")
            return
        
        print(f"\n📊 MOVIE SUMMARY")
        print(f"=" * 50)
        print(f"Total movies found: {len(movies)}")
        
        # Group by year
        years = {}
        for movie in movies:
            year = movie.get('year', 'Unknown')
            if year not in years:
                years[year] = 0
            years[year] += 1
        
        print(f"\n📅 Movies by year:")
        for year in sorted(years.keys(), reverse=True):
            print(f"   {year}: {years[year]} movies")
        
        # Show some sample movies
        print(f"\n🎬 Sample movies (first 10):")
        for i, movie in enumerate(movies[:10]):
            print(f"   {i+1}. {movie['title']} ({movie.get('year', 'N/A')})")
        
        if len(movies) > 10:
            print(f"   ... and {len(movies) - 10} more")

def main():
    """Main function"""
    print("🎬 Plex Movie Checker")
    print("=" * 50)
    
    # Configuration
    base_url = "http://natetrystuff.com:32400"
    
    # You may need to provide a token for remote access
    # You can get this from your Plex web interface
    token = os.getenv('PLEX_TOKEN')  # Set this environment variable if needed
    
    # Create checker instance
    checker = PlexMovieChecker(base_url, token)
    
    # Connect to Plex
    if not checker.connect():
        print("\n💡 If connection failed, you might need to:")
        print("   1. Provide a Plex token (set PLEX_TOKEN environment variable)")
        print("   2. Check if the Plex server is accessible")
        print("   3. Verify the URL is correct")
        return
    
    # Get movies
    print("\n🔍 Retrieving movies from Plex...")
    movies = checker.get_movies()
    
    if not movies:
        print("❌ No movies found or error occurred")
        return
    
    # Get detailed information
    print("\n📝 Extracting movie details...")
    movie_details = checker.get_movie_details(movies)
    
    # Print summary
    checker.print_summary(movie_details)
    
    # Save to file
    filename = checker.save_to_file(movie_details)
    
    print(f"\n✅ Analysis complete!")
    print(f"📁 Movie details saved to: {filename}")
    print(f"📊 Total movies in Plex: {len(movie_details)}")

if __name__ == "__main__":
    main()
