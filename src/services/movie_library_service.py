#!/usr/bin/env python3
"""
Movie Library Service
Handles TMDB searches and movie library status checks.
"""

import logging
from ..clients.tmdb_client import TMDBClient

logger = logging.getLogger(__name__)

class MovieLibraryService:
    """Service for managing movie library operations"""
    
    def __init__(self, tmdb_client: TMDBClient):
        self.tmdb_client = tmdb_client
    
    def check_movie_library_status(self, movie_name):
        """
        Agentic function: Search TMDB and check release status for a movie
        Returns comprehensive movie information and availability status
        """
        try:
            logger.info(f"🔍 MovieLibrary: Checking library status for: {movie_name}")
            
            # Search TMDB for the movie
            tmdb_result = self.tmdb_client.search_movie(movie_name)
            if not tmdb_result.get('results') or len(tmdb_result.get('results', [])) == 0:
                logger.info(f"🔍 MovieLibrary: Movie not found in TMDB: {movie_name}")
                return {
                    'success': False,
                    'movie_name': movie_name,
                    'tmdb_result': tmdb_result,
                    'movie_data': None,
                    'release_status': None,
                    'error': 'Movie not found in TMDB'
                }
            
            movie_data = tmdb_result['results'][0]  # Get first result
            tmdb_id = movie_data.get('id')
            
            # Extract year from release_date (format: YYYY-MM-DD)
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            
            logger.info(f"🔍 MovieLibrary: TMDB found movie: {movie_data.get('title')} ({year})")
            
            # Check release status
            release_status = self.tmdb_client.is_movie_released(movie_data)
            logger.info(f"📅 MovieLibrary: Release status: {release_status}")
            
            return {
                'success': True,
                'movie_name': movie_name,
                'tmdb_result': tmdb_result,
                'movie_data': movie_data,
                'tmdb_id': tmdb_id,
                'year': year,
                'release_status': release_status
            }
            
        except Exception as e:
            logger.error(f"❌ MovieLibrary: Error checking movie library status: {str(e)}")
            return {
                'success': False,
                'movie_name': movie_name,
                'error': str(e)
            }
    
    def get_movie(self, movie_result):
        """
        Service method to handle TMDB search for a detected movie.
        Returns TMDB result, movie data, Radarr status, and release status if found.
        """
        if not movie_result or not movie_result.get('success') or not movie_result.get('movie_name') or movie_result.get('movie_name') == "No movie identified":
            logger.info(f"🎬 MovieLibrary: No movie identified in conversation")
            return None, None, None, None
        
        logger.info(f"🎬 MovieLibrary: Movie detected: {movie_result['movie_name']}")
        
        # Search TMDB for the movie
        tmdb_result = self.tmdb_client.search_movie(movie_result['movie_name'])
        if not tmdb_result.get('results') or len(tmdb_result.get('results', [])) == 0:
            logger.info(f"🎬 MovieLibrary: Movie not found in TMDB: {movie_result['movie_name']}")
            return tmdb_result, None, None, None
        
        movie_data = tmdb_result['results'][0]  # Get first result
        tmdb_id = movie_data.get('id')
        
        # Extract year from release_date (format: YYYY-MM-DD)
        release_date = movie_data.get('release_date', '')
        year = release_date.split('-')[0] if release_date else 'Unknown year'
        
        logger.info(f"🎬 MovieLibrary: TMDB found movie: {movie_data.get('title')} ({year})")
        
        # Check release status
        release_status = self.tmdb_client.is_movie_released(movie_data)
        logger.info(f"📅 MovieLibrary: Release status: {release_status}")
        
        return tmdb_result, movie_data, None, release_status  # Radarr status will be checked separately
