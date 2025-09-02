#!/usr/bin/env python3
"""
Plex API Client for retrieving movie information from Plex server.
Connects to Plex server at natetrystuff.com:32400
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlexClient:
    def __init__(self, server_url: str = "http://natetrystuff.com:32400", token: Optional[str] = '1CkG7DQwFVFadauKTxuB'):
        """
        Initialize Plex client
        
        Args:
            server_url: Plex server URL (default: http://natetrystuff.com:32400)
            token: Plex authentication token (optional)
        """
        self.server_url = server_url.rstrip('/')
        self.token = token or os.getenv('PLEX_TOKEN')
        self.session = requests.Session()
        
        if self.token:
            self.session.headers.update({'X-Plex-Token': self.token})
            logger.info("Plex token configured")
        else:
            logger.warning("No Plex token provided. Some endpoints may require authentication.")
            logger.info("To get your Plex token:")
            logger.info("1. Go to https://app.plex.tv/desktop/#!/settings/account")
            logger.info("2. Copy your Plex token")
            logger.info("3. Set PLEX_TOKEN environment variable or pass token to constructor")
    
    def get_libraries(self) -> List[Dict]:
        """
        Get all libraries from Plex server
        
        Returns:
            List of library information dictionaries
        """
        try:
            url = f"{self.server_url}/library/sections"
            response = self.session.get(url)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            libraries = []
            
            for directory in root.findall('.//Directory'):
                library = {
                    'id': directory.get('key'),
                    'title': directory.get('title'),
                    'type': directory.get('type'),
                    'agent': directory.get('agent'),
                    'scanner': directory.get('scanner'),
                    'language': directory.get('language'),
                    'uuid': directory.get('uuid'),
                    'updatedAt': directory.get('updatedAt'),
                    'createdAt': directory.get('createdAt'),
                    'scannedAt': directory.get('scannedAt'),
                    'count': directory.get('count'),
                    'content': directory.get('content'),
                    'directory': directory.get('directory'),
                    'enableAutoPhotoTags': directory.get('enableAutoPhotoTags'),
                    'enableBWS': directory.get('enableBWS'),
                    'enableBW': directory.get('enableBW'),
                    'enablePhotoTagFilters': directory.get('enablePhotoTagFilters'),
                    'enableCinemaTrailers': directory.get('enableCinemaTrailers'),
                    'enablePhotoTranscoding': directory.get('enablePhotoTranscoding'),
                    'enableSmartFilters': directory.get('enableSmartFilters'),
                    'enableSync': directory.get('enableSync'),
                    'includeInGlobal': directory.get('includeInGlobal'),
                    'minAutoUpdate': directory.get('minAutoUpdate'),
                    'refreshing': directory.get('refreshing'),
                    'thumb': directory.get('thumb'),
                    'art': directory.get('art')
                }
                libraries.append(library)
            
            return libraries
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get libraries: {e}")
            if "401" in str(e):
                logger.error("Authentication required. Please provide a valid Plex token.")
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
            # Try the standard endpoint first
            url = f"{self.server_url}/library/sections/{library_id}/all"
            params = {
                'type': 'movie'
            }
            
            # Add pagination parameters if needed
            if limit > 0:
                params['X-Plex-Container-Start'] = '0'
                params['X-Plex-Container-Size'] = str(limit)
            
            logger.info(f"Requesting URL: {url}")
            logger.info(f"Parameters: {params}")
            response = self.session.get(url, params=params)
            logger.info(f"Response status: {response.status_code}")
            
            # If we get a 500 error, try alternative endpoints
            if response.status_code == 500:
                logger.warning("Got 500 error, trying alternative endpoint...")
                
                # Try without type parameter
                alt_url = f"{self.server_url}/library/sections/{library_id}/all"
                alt_params = {}
                if limit > 0:
                    alt_params['X-Plex-Container-Start'] = '0'
                    alt_params['X-Plex-Container-Size'] = str(limit)
                
                logger.info(f"Trying alternative URL: {alt_url}")
                logger.info(f"Alternative parameters: {alt_params}")
                response = self.session.get(alt_url, params=alt_params)
                logger.info(f"Alternative response status: {response.status_code}")
                
                # If still 500, try without any parameters
                if response.status_code == 500:
                    logger.warning("Still getting 500 error, trying without any parameters...")
                    alt_url = f"{self.server_url}/library/sections/{library_id}/all"
                    response = self.session.get(alt_url)
                    logger.info(f"Minimal parameters response status: {response.status_code}")
            
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            movies = []
            
            for video in root.findall('.//Video'):
                movie = {
                    'ratingKey': video.get('ratingKey'),
                    'key': video.get('key'),
                    'guid': video.get('guid'),
                    'studio': video.get('studio'),
                    'type': video.get('type'),
                    'title': video.get('title'),
                    'librarySectionTitle': video.get('librarySectionTitle'),
                    'librarySectionID': video.get('librarySectionID'),
                    'librarySectionKey': video.get('librarySectionKey'),
                    'contentRating': video.get('contentRating'),
                    'summary': video.get('summary'),
                    'rating': video.get('rating'),
                    'audienceRating': video.get('audienceRating'),
                    'year': video.get('year'),
                    'tagline': video.get('tagline'),
                    'thumb': video.get('thumb'),
                    'art': video.get('art'),
                    'duration': video.get('duration'),
                    'originallyAvailableAt': video.get('originallyAvailableAt'),
                    'addedAt': video.get('addedAt'),
                    'updatedAt': video.get('updatedAt'),
                    'audienceRatingImage': video.get('audienceRatingImage'),
                    'chapterSource': video.get('chapterSource'),
                    'primaryExtraKey': video.get('primaryExtraKey'),
                    'ratingImage': video.get('ratingImage'),
                    'media': []
                }
                
                # Get media information
                for media in video.findall('.//Media'):
                    media_info = {
                        'id': media.get('id'),
                        'duration': media.get('duration'),
                        'bitrate': media.get('bitrate'),
                        'width': media.get('width'),
                        'height': media.get('height'),
                        'aspectRatio': media.get('aspectRatio'),
                        'audioChannels': media.get('audioChannels'),
                        'audioCodec': media.get('audioCodec'),
                        'videoCodec': media.get('videoCodec'),
                        'videoResolution': media.get('videoResolution'),
                        'container': media.get('container'),
                        'videoFrameRate': media.get('videoFrameRate'),
                        'audioProfile': media.get('audioProfile'),
                        'videoProfile': media.get('videoProfile'),
                        'part': []
                    }
                    
                    # Get part information
                    for part in media.findall('.//Part'):
                        part_info = {
                            'id': part.get('id'),
                            'key': part.get('key'),
                            'duration': part.get('duration'),
                            'file': part.get('file'),
                            'size': part.get('size'),
                            'audioProfile': part.get('audioProfile'),
                            'container': part.get('container'),
                            'videoProfile': part.get('videoProfile'),
                            'stream': []
                        }
                        
                        # Get stream information
                        for stream in part.findall('.//Stream'):
                            stream_info = {
                                'id': stream.get('id'),
                                'streamType': stream.get('streamType'),
                                'default': stream.get('default'),
                                'codec': stream.get('codec'),
                                'index': stream.get('index'),
                                'bitrate': stream.get('bitrate'),
                                'bitrateMode': stream.get('bitrateMode'),
                                'language': stream.get('language'),
                                'languageCode': stream.get('languageCode'),
                                'profile': stream.get('profile'),
                                'title': stream.get('title'),
                                'width': stream.get('width'),
                                'height': stream.get('height'),
                                'aspectRatio': stream.get('aspectRatio'),
                                'aspectRatioFloat': stream.get('aspectRatioFloat'),
                                'pixelFormat': stream.get('pixelFormat'),
                                'level': stream.get('level'),
                                'refFrames': stream.get('refFrames'),
                                'streamIdentifier': stream.get('streamIdentifier'),
                                'samplingRate': stream.get('samplingRate'),
                                'channels': stream.get('channels'),
                                'bitDepth': stream.get('bitDepth'),
                                'selected': stream.get('selected'),
                                'channels': stream.get('channels'),
                                'audioChannelLayout': stream.get('audioChannelLayout'),
                                'samplingRate': stream.get('samplingRate'),
                                'frameRate': stream.get('frameRate'),
                                'frameRateMode': stream.get('frameRateMode'),
                                'colorSpace': stream.get('colorSpace'),
                                'colorTrc': stream.get('colorTrc'),
                                'colorPrimaries': stream.get('colorPrimaries'),
                                'colorRange': stream.get('colorRange'),
                                'chromaSubsampling': stream.get('chromaSubsampling'),
                                'cabac': stream.get('cabac'),
                                'fieldOrder': stream.get('fieldOrder'),
                                'refFrames': stream.get('refFrames'),
                                'hasScalingMatrix': stream.get('hasScalingMatrix'),
                                'displayTitle': stream.get('displayTitle'),
                                'extendedDisplayTitle': stream.get('extendedDisplayTitle')
                            }
                            part_info['stream'].append(stream_info)
                        
                        media_info['part'].append(part_info)
                    
                    movie['media'].append(media_info)
                
                movies.append(movie)
            
            return movies
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get movies from library {library_id}: {e}")
            if "401" in str(e):
                logger.error("Authentication required. Please provide a valid Plex token.")
            elif "500" in str(e):
                logger.error("Plex server error. The library might not exist or be accessible.")
                logger.error("Try checking if the library ID is correct and the server is running.")
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
                logger.info(f"Fetching movies from library: {library['title']} (ID: {library['id']})")
                
                # Test library access first
                if not self.test_library_access(library['id']):
                    logger.warning(f"Cannot access library {library['id']}, skipping...")
                    continue
                
                movies = self.get_movies_from_library(library['id'])
                all_movies.extend(movies)
                logger.info(f"Found {len(movies)} movies in library '{library['title']}'")
        
        logger.info(f"Total movies found: {len(all_movies)}")
        return all_movies
    
    def get_movie_count(self) -> Dict[str, int]:
        """
        Get movie count by library
        
        Returns:
            Dictionary with library names as keys and movie counts as values
        """
        libraries = self.get_libraries()
        counts = {}
        
        for library in libraries:
            if library['type'] == 'movie':
                count_value = library.get('count')
                if count_value is not None:
                    counts[library['title']] = int(count_value)
                else:
                    counts[library['title']] = 0
        
        return counts
    
    def test_library_access(self, library_id: str) -> bool:
        """
        Test if we can access a specific library
        
        Args:
            library_id: Library ID to test
            
        Returns:
            True if accessible, False otherwise
        """
        try:
            url = f"{self.server_url}/library/sections/{library_id}"
            response = self.session.get(url)
            logger.info(f"Testing library {library_id} access: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error testing library {library_id} access: {e}")
            return False

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
                    'thumb': video.get('thumb'),
                    'art': video.get('art'),
                    'summary': video.get('summary'),
                    'rating': video.get('rating'),
                    'audienceRating': video.get('audienceRating'),
                    'contentRating': video.get('contentRating'),
                    'originallyAvailableAt': video.get('originallyAvailableAt'),
                    'addedAt': video.get('addedAt'),
                    'updatedAt': video.get('updatedAt'),
                    'duration': video.get('duration'),
                    'studio': video.get('studio'),
                    'tagline': video.get('tagline')
                }
                movies.append(movie)
            
            return movies
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search movies: {e}")
            if "401" in str(e):
                logger.error("Authentication required. Please provide a valid Plex token.")
            return []

def main():
    """Example usage of the PlexClient"""
    # Initialize client
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
