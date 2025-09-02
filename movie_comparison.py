#!/usr/bin/env python3
"""
Movie Comparison Tool
Compares local movie files with Plex movies to identify differences
"""

import os
import json
import re
from pathlib import Path
from plex_movie_checker import PlexMovieChecker

class MovieComparison:
    def __init__(self, plex_checker):
        self.plex_checker = plex_checker
        self.plex_movies = []
        self.local_movies = []
        
    def scan_local_movies(self, directories):
        """
        Scan local directories for movie files
        
        Args:
            directories (list): List of directory paths to scan
        """
        print("🔍 Scanning local directories for movies...")
        
        # Common movie file extensions
        movie_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        for directory in directories:
            if not os.path.exists(directory):
                print(f"⚠️ Directory not found: {directory}")
                continue
                
            print(f"📁 Scanning: {directory}")
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    if file_ext in movie_extensions:
                        # Extract movie title from filename
                        title = self.extract_movie_title(file)
                        year = self.extract_movie_year(file)
                        
                        movie_info = {
                            'title': title,
                            'year': year,
                            'filename': file,
                            'file_path': file_path,
                            'size': os.path.getsize(file_path)
                        }
                        self.local_movies.append(movie_info)
        
        print(f"📊 Found {len(self.local_movies)} local movie files")
    
    def extract_movie_title(self, filename):
        """Extract movie title from filename"""
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Remove year pattern (YYYY) or (YYYY)
        name = re.sub(r'\s*\(\d{4}\)', '', name)
        name = re.sub(r'\s*\d{4}', '', name)
        
        # Remove quality indicators
        name = re.sub(r'\s*(1080p|720p|480p|HD|SD|BluRay|BRRip|HDRip|WEB-DL|WEBRip)', '', name, flags=re.IGNORECASE)
        
        # Remove release group names
        name = re.sub(r'\s*-\s*[A-Z0-9]+$', '', name)
        
        # Clean up extra spaces and replace dots/underscores with spaces
        name = re.sub(r'[._]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def extract_movie_year(self, filename):
        """Extract movie year from filename"""
        # Look for year patterns like (2023) or 2023
        year_match = re.search(r'\((\d{4})\)|(\d{4})', filename)
        if year_match:
            return int(year_match.group(1) or year_match.group(2))
        return None
    
    def get_plex_movies(self):
        """Get movies from Plex"""
        print("🎬 Getting movies from Plex...")
        
        if not self.plex_checker.connect():
            return False
        
        movies = self.plex_checker.get_movies()
        if not movies:
            return False
        
        self.plex_movies = self.plex_checker.get_movie_details(movies)
        print(f"📊 Found {len(self.plex_movies)} movies in Plex")
        return True
    
    def compare_movies(self):
        """Compare local movies with Plex movies"""
        if not self.plex_movies or not self.local_movies:
            print("❌ No movies to compare")
            return
        
        print("\n🔍 Comparing movies...")
        
        # Create sets for comparison
        plex_titles = {movie['title'].lower() for movie in self.plex_movies}
        local_titles = {movie['title'].lower() for movie in self.local_movies}
        
        # Find differences
        in_local_not_plex = local_titles - plex_titles
        in_plex_not_local = plex_titles - local_titles
        
        print(f"\n📊 COMPARISON RESULTS")
        print("=" * 50)
        print(f"Local movies: {len(self.local_movies)}")
        print(f"Plex movies: {len(self.plex_movies)}")
        print(f"Difference: {len(self.local_movies) - len(self.plex_movies)}")
        
        if in_local_not_plex:
            print(f"\n🎬 Movies in local files but NOT in Plex ({len(in_local_not_plex)}):")
            for title in sorted(in_local_not_plex):
                local_movie = next(m for m in self.local_movies if m['title'].lower() == title)
                print(f"   • {local_movie['title']} ({local_movie.get('year', 'N/A')}) - {local_movie['filename']}")
        
        if in_plex_not_local:
            print(f"\n🎬 Movies in Plex but NOT in local files ({len(in_plex_not_local)}):")
            for title in sorted(in_plex_not_local):
                plex_movie = next(m for m in self.plex_movies if m['title'].lower() == title)
                print(f"   • {plex_movie['title']} ({plex_movie.get('year', 'N/A')})")
        
        if not in_local_not_plex and not in_plex_not_local:
            print("\n✅ All movies match between local files and Plex!")
        
        return {
            'local_count': len(self.local_movies),
            'plex_count': len(self.plex_movies),
            'difference': len(self.local_movies) - len(self.plex_movies),
            'missing_in_plex': list(in_local_not_plex),
            'missing_in_local': list(in_plex_not_local)
        }
    
    def save_comparison_report(self, comparison_results, filename=None):
        """Save comparison results to file"""
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"movie_comparison_{timestamp}.json"
        
        report = {
            'comparison_date': datetime.now().isoformat(),
            'results': comparison_results,
            'local_movies': self.local_movies,
            'plex_movies': self.plex_movies
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"💾 Comparison report saved to: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Error saving report: {e}")
            return None

def main():
    """Main function"""
    print("🎬 Movie Comparison Tool")
    print("=" * 50)
    
    # Configuration
    plex_url = "http://natetrystuff.com:32400"
    plex_token = os.getenv('PLEX_TOKEN')  # Set this if needed
    
    # Local directories to scan (modify these paths)
    local_directories = [
        "/path/to/your/movies",  # Replace with your actual movie directories
        "/another/movie/path"
    ]
    
    # Create Plex checker
    plex_checker = PlexMovieChecker(plex_url, plex_token)
    
    # Create comparison tool
    comparison = MovieComparison(plex_checker)
    
    # Get Plex movies
    if not comparison.get_plex_movies():
        print("❌ Failed to get Plex movies")
        return
    
    # Scan local movies
    comparison.scan_local_movies(local_directories)
    
    if not comparison.local_movies:
        print("❌ No local movies found")
        return
    
    # Compare movies
    results = comparison.compare_movies()
    
    # Save report
    comparison.save_comparison_report(results)
    
    print(f"\n✅ Comparison complete!")

if __name__ == "__main__":
    main()
