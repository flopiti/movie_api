#!/usr/bin/env python3
"""
Plex API Client for retrieving movie information from Plex server.
Connects to Plex server at natetrystuff.com:32400
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import os

class PlexClient:
    def __init__(self, server_url: str = "http://192.168.0.10:32400", token: Optional[str] = None):
        """
        Initialize Plex client
        
        Args:
            server_url: Plex server URL (default: http://natetrystuff.com:32400)
            token: Plex authentication token (optional)
        """
        self.server_url = server_url.rstrip('/')
        self.token = token or os.getenv('PLEX_TOKEN') or '1CkG7DQwFVFadauKTxuB'
        self.session = requests.Session()
        self.session.timeout = 30  # 30 second timeout
        
        if self.token:
            self.session.headers.update({'X-Plex-Token': self.token})
    
    def get_libraries(self) -> List[Dict]:
        """
        Get all libraries from Plex server
        
        Returns:
            List of library information dictionaries
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Fetching libraries from {self.server_url}/library/sections")
            url = f"{self.server_url}/library/sections"
            response = self.session.get(url)
            response.raise_for_status()
            logger.info(f"Libraries response status: {response.status_code}")
            
            root = ET.fromstring(response.content)
            libraries = []
            
            for directory in root.findall('.//Directory'):
                library = {
                    'id': directory.get('key'),
                    'title': directory.get('title'),
                    'type': directory.get('type'),
                    'count': directory.get('count')
                }
                libraries.append(library)
                logger.info(f"Found library: {library['title']} (ID: {library['id']}, Type: {library['type']}, Count: {library['count']})")
            
            logger.info(f"Total libraries found: {len(libraries)}")
            return libraries
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get libraries: {e}")
            return []
    
    def get_movies_from_library(self, library_id: str, limit: int = 1000) -> List[Dict]:
        """
        Get all movies from a specific library
        
        Args:
            library_id: Library ID to fetch movies from
            limit: Maximum number of movies to retrieve
            
        Returns:
            List of movie information dictionaries
        """
        try:
            url = f"{self.server_url}/library/sections/{library_id}/all"
            params = {
                'type': 'movie'
            }
            
            if limit > 0:
                params['X-Plex-Container-Start'] = '0'
                params['X-Plex-Container-Size'] = str(limit)
            
            response = self.session.get(url, params=params)
            
            # If we get a 500 error, try without type parameter
            if response.status_code == 500:
                alt_url = f"{self.server_url}/library/sections/{library_id}/all"
                alt_params = {}
                if limit > 0:
                    alt_params['X-Plex-Container-Start'] = '0'
                    alt_params['X-Plex-Container-Size'] = str(limit)
                
                response = self.session.get(alt_url, params=alt_params)
            
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            movies = []
            
            for video in root.findall('.//Video'):
                movie = {
                    'ratingKey': video.get('ratingKey'),
                    'title': video.get('title'),
                    'year': video.get('year'),
                    'guid': video.get('guid'),
                    'type': video.get('type'),
                    'summary': video.get('summary'),
                    'rating': video.get('rating'),
                    'media': []
                }
                
                # Get media information
                for media in video.findall('.//Media'):
                    media_info = {
                        'part': []
                    }
                    
                    # Get part information
                    for part in media.findall('.//Part'):
                        part_info = {
                            'file': part.get('file'),
                            'size': part.get('size')
                        }
                        media_info['part'].append(part_info)
                    
                    movie['media'].append(media_info)
                
                movies.append(movie)
            
            return movies
            
        except requests.exceptions.RequestException:
            return []
    
    def get_all_movies(self) -> List[Dict]:
        """
        Get all movies from all movie libraries
        
        Returns:
            List of all movies from all libraries
        """
        libraries = self.get_libraries()
        all_movies = []
        
        for library in libraries:
            if library['type'] == 'movie':
                movies = self.get_movies_from_library(library['id'])
                all_movies.extend(movies)
        
        return all_movies
    
    def get_movie_count(self) -> Dict[str, int]:
        """
        Get movie count by library
        
        Returns:
            Dictionary with library names as keys and movie counts as values
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Getting movie count from Plex...")
        libraries = self.get_libraries()
        logger.info(f"Found {len(libraries)} libraries")
        
        counts = {}
        
        for library in libraries:
            if library['type'] == 'movie':
                logger.info(f"Processing movie library: {library['title']}")
                count_value = library.get('count')
                if count_value is not None:
                    counts[library['title']] = int(count_value)
                    logger.info(f"Using library count: {count_value}")
                else:
                    # Direct approach - just get the count from /all endpoint
                    logger.info(f"Library count is None, getting from /all endpoint...")
                    try:
                        # Try a more efficient approach - just get the count without full movie data
                        url = f"{self.server_url}/library/sections/{library['id']}/all"
                        params = {
                            'X-Plex-Container-Start': '0',
                            'X-Plex-Container-Size': '1'  # Just get 1 item to check totalSize
                        }
                        response = self.session.get(url, params=params, timeout=30)  # Increased timeout
                        if response.status_code == 200:
                            root = ET.fromstring(response.content)
                            total_size = root.get('totalSize')
                            if total_size is not None:
                                counts[library['title']] = int(total_size)
                                logger.info(f"Got count from /all endpoint: {total_size}")
                            else:
                                # If still no totalSize, try without pagination
                                response = self.session.get(url, timeout=60)  # Even longer timeout for full response
                                if response.status_code == 200:
                                    root = ET.fromstring(response.content)
                                    movies_in_response = len(root.findall('.//Video'))
                                    counts[library['title']] = movies_in_response
                                    logger.info(f"No totalSize in response, counted {movies_in_response} movies from response")
                                else:
                                    logger.error(f"/all request failed: {response.status_code}")
                                    counts[library['title']] = 0
                        else:
                            logger.error(f"/all request failed: {response.status_code}")
                            counts[library['title']] = 0
                    except Exception as e:
                        logger.error(f"Error getting count for {library['title']}: {e}")
                        counts[library['title']] = 0
        
        logger.info(f"Final counts: {counts}")
        return counts
    
    def search_movies(self, query: str, library_id: Optional[str] = None) -> List[Dict]:
        """
        Search for movies by title
        
        Args:
            query: Search query
            library_id: Optional library ID to search in specific library
            
        Returns:
            List of matching movies
        """
        try:
            if library_id:
                url = f"{self.server_url}/library/sections/{library_id}/search"
            else:
                url = f"{self.server_url}/search"
            
            params = {
                'query': query,
                'type': 'movie'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            movies = []
            
            for video in root.findall('.//Video'):
                movie = {
                    'ratingKey': video.get('ratingKey'),
                    'title': video.get('title'),
                    'year': video.get('year'),
                    'guid': video.get('guid'),
                    'type': video.get('type'),
                    'summary': video.get('summary'),
                    'rating': video.get('rating')
                }
                movies.append(movie)
            
            return movies
            
        except requests.exceptions.RequestException:
            return []

def main():
    """Example usage of the PlexClient"""
    plex = PlexClient()
    
    # Get library information
    print("=== Plex Libraries ===")
    libraries = plex.get_libraries()
    for lib in libraries:
        if lib['type'] == 'movie':
            print(f"Movie Library: {lib['title']} (ID: {lib['id']}) - Count: {lib.get('count', 'Unknown')}")
    
    # Get movie counts
    print("\n=== Movie Counts ===")
    counts = plex.get_movie_count()
    for library, count in counts.items():
        print(f"{library}: {count} movies")
    
    # Get all movies
    print("\n=== Fetching All Movies ===")
    all_movies = plex.get_all_movies()
    print(f"Total movies retrieved: {len(all_movies)}")
    
    # Display first few movies as example
    print("\n=== Sample Movies ===")
    for i, movie in enumerate(all_movies[:5]):
        print(f"{i+1}. {movie['title']} ({movie.get('year', 'N/A')})")
        if movie.get('summary'):
            print(f"   Summary: {movie['summary'][:100]}...")
        print()

if __name__ == "__main__":
    main()
