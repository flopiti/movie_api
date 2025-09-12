#!/usr/bin/env python3
"""
Radarr API Client for managing movies and downloads
"""

import requests
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

# Set up logging
logger = logging.getLogger(__name__)

class RadarrClient:
    """Client for interacting with Radarr API"""
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        """
        Initialize Radarr client
        
        Args:
            base_url: Base URL of Radarr instance (e.g., "http://192.168.0.10:7878")
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        })
        
        logger.info(f"🔧 Radarr Client initialized: URL={self.base_url}, API Key={'*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '****'}")
        
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to Radarr API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/api/v3/movie")
            **kwargs: Additional arguments for requests
            
        Returns:
            Response data as dictionary or None if error
        """
        url = urljoin(self.base_url, endpoint)
        
        # Log request details
        logger.debug(f"🌐 Radarr API Request: {method} {url}")
        if 'json' in kwargs:
            logger.debug(f"📤 Request payload: {kwargs['json']}")
        if 'params' in kwargs:
            logger.debug(f"📤 Request params: {kwargs['params']}")
        
        try:
            response = self.session.request(
                method, 
                url, 
                timeout=self.timeout,
                **kwargs
            )
            
            logger.debug(f"📥 Radarr API Response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"✅ Radarr API Success: {len(str(data))} chars response")
                return data
            elif response.status_code == 201:
                data = response.json()
                logger.info(f"✅ Radarr API Created: {len(str(data))} chars response")
                return data
            elif response.status_code == 204:
                logger.info("✅ Radarr API Success: No content")
                return {}
            else:
                logger.error(f"❌ Radarr API Error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Radarr API Request Exception: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test connection to Radarr API
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("🔍 Testing Radarr connection...")
            result = self._make_request('GET', '/api/v3/system/status')
            
            if result:
                logger.info(f"✅ Radarr connection successful - Version: {result.get('version', 'Unknown')}")
                logger.info(f"✅ Radarr App Name: {result.get('appName', 'Unknown')}")
                return True
            else:
                logger.error("❌ Radarr connection failed - no response")
                return False
        except Exception as e:
            logger.error(f"❌ Radarr connection test failed: {str(e)}")
            return False
    
    def get_system_status(self) -> Optional[Dict[str, Any]]:
        """
        Get Radarr system status
        
        Returns:
            System status information or None if error
        """
        return self._make_request('GET', '/api/v3/system/status')
    
    def get_movie_count(self) -> int:
        """
        Get total number of movies in Radarr
        
        Returns:
            Number of movies or 0 if error
        """
        movies = self.get_movies()
        return len(movies) if movies else 0
    
    def get_movies(self) -> List[Dict[str, Any]]:
        """
        Get all movies from Radarr
        
        Returns:
            List of movie dictionaries or empty list if error
        """
        result = self._make_request('GET', '/api/v3/movie')
        return result if result else []
    
    def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """
        Get specific movie by ID
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            Movie dictionary or None if not found
        """
        return self._make_request('GET', f'/api/v3/movie/{movie_id}')
    
    def search_movies(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for movies using Radarr's search functionality
        
        Args:
            query: Search query
            
        Returns:
            List of matching movies or empty list if error
        """
        params = {'term': query}
        result = self._make_request('GET', '/api/v3/movie/lookup', params=params)
        return result if result else []
    
    def add_movie(self, movie_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Add a new movie to Radarr
        
        Args:
            movie_data: Movie information dictionary
            
        Returns:
            Added movie data or None if error
        """
        return self._make_request('POST', '/api/v3/movie', json=movie_data)
    
    def update_movie(self, movie_id: int, movie_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update existing movie in Radarr
        
        Args:
            movie_id: Radarr movie ID
            movie_data: Updated movie information
            
        Returns:
            Updated movie data or None if error
        """
        return self._make_request('PUT', f'/api/v3/movie/{movie_id}', json=movie_data)
    
    def delete_movie(self, movie_id: int) -> bool:
        """
        Delete movie from Radarr
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            True if successful, False otherwise
        """
        result = self._make_request('DELETE', f'/api/v3/movie/{movie_id}')
        return result is not None
    
    def get_downloads(self) -> List[Dict[str, Any]]:
        """
        Get current downloads from Radarr
        
        Returns:
            List of download dictionaries or empty list if error
        """
        logger.debug("📥 Getting current downloads from Radarr...")
        result = self._make_request('GET', '/api/v3/queue')
        
        if result:
            downloads = result.get('records', [])
            logger.debug(f"📥 Found {len(downloads)} downloads in queue")
            for download in downloads:
                movie_title = download.get('movie', {}).get('title', 'Unknown')
                status = download.get('status', 'Unknown')
                logger.debug(f"📥 Download: {movie_title} - Status: {status}")
            return downloads
        else:
            logger.error("❌ Failed to get downloads from Radarr")
            return []
    
    def get_download_history(self) -> List[Dict[str, Any]]:
        """
        Get download history from Radarr
        
        Returns:
            List of download history records or empty list if error
        """
        result = self._make_request('GET', '/api/v3/history')
        return result.get('records', []) if result else []
    
    def get_root_folders(self) -> List[Dict[str, Any]]:
        """
        Get root folders configured in Radarr
        
        Returns:
            List of root folder dictionaries or empty list if error
        """
        result = self._make_request('GET', '/api/v3/rootfolder')
        return result if result else []
    
    def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """
        Get quality profiles from Radarr
        
        Returns:
            List of quality profile dictionaries or empty list if error
        """
        result = self._make_request('GET', '/api/v3/qualityprofile')
        return result if result else []
    
    def get_languages(self) -> List[Dict[str, Any]]:
        """
        Get available languages from Radarr
        
        Returns:
            List of language dictionaries or empty list if error
        """
        result = self._make_request('GET', '/api/v3/language')
        return result if result else []
    
    def get_tags(self) -> List[Dict[str, Any]]:
        """
        Get tags from Radarr
        
        Returns:
            List of tag dictionaries or empty list if error
        """
        result = self._make_request('GET', '/api/v3/tag')
        return result if result else []
    
    def create_tag(self, label: str) -> Optional[Dict[str, Any]]:
        """
        Create a new tag in Radarr
        
        Args:
            label: Tag label
            
        Returns:
            Created tag data or None if error
        """
        data = {'label': label}
        return self._make_request('POST', '/api/v3/tag', json=data)
    
    def delete_tag(self, tag_id: int) -> bool:
        """
        Delete tag from Radarr
        
        Args:
            tag_id: Tag ID
            
        Returns:
            True if successful, False otherwise
        """
        result = self._make_request('DELETE', f'/api/v3/tag/{tag_id}')
        return result is not None
    
    def get_calendar(self, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        Get calendar of upcoming releases
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of calendar entries or empty list if error
        """
        params = {}
        if start_date:
            params['start'] = start_date
        if end_date:
            params['end'] = end_date
            
        result = self._make_request('GET', '/api/v3/calendar', params=params)
        return result if result else []
    
    def get_wanted_missing(self) -> List[Dict[str, Any]]:
        """
        Get wanted missing movies
        
        Returns:
            List of wanted missing movies or empty list if error
        """
        result = self._make_request('GET', '/api/v3/wanted/missing')
        return result.get('records', []) if result else []
    
    def get_wanted_cutoff_unmet(self) -> List[Dict[str, Any]]:
        """
        Get movies with cutoff unmet
        
        Returns:
            List of movies with cutoff unmet or empty list if error
        """
        result = self._make_request('GET', '/api/v3/wanted/cutoff')
        return result.get('records', []) if result else []
    
    def refresh_movie(self, movie_id: int) -> bool:
        """
        Refresh movie information from Radarr
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            True if successful, False otherwise
        """
        result = self._make_request('POST', f'/api/v3/command', json={
            'name': 'RefreshMovie',
            'movieId': movie_id
        })
        return result is not None
    
    def rescan_movie(self, movie_id: int) -> bool:
        """
        Rescan movie folder
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            True if successful, False otherwise
        """
        result = self._make_request('POST', f'/api/v3/command', json={
            'name': 'RescanMovie',
            'movieId': movie_id
        })
        return result is not None
    
    def search_missing_movies(self) -> bool:
        """
        Search for missing movies
        
        Returns:
            True if successful, False otherwise
        """
        result = self._make_request('POST', '/api/v3/command', json={
            'name': 'MissingMoviesSearch'
        })
        return result is not None
    
    def get_commands(self) -> List[Dict[str, Any]]:
        """
        Get active commands
        
        Returns:
            List of active commands or empty list if error
        """
        result = self._make_request('GET', '/api/v3/command')
        return result if result else []
    
    def get_command_status(self, command_id: int) -> Optional[Dict[str, Any]]:
        """
        Get status of specific command
        
        Args:
            command_id: Command ID
            
        Returns:
            Command status or None if error
        """
        return self._make_request('GET', f'/api/v3/command/{command_id}')
    
    def add_movie_from_tmdb(self, tmdb_id: int, root_folder_path: str = None, quality_profile_id: int = None, monitored: bool = True, search_for_movie: bool = True) -> Optional[Dict[str, Any]]:
        """
        Add a movie to Radarr using TMDB ID
        
        Args:
            tmdb_id: TMDB movie ID
            root_folder_path: Root folder path for the movie
            quality_profile_id: Quality profile ID
            monitored: Whether to monitor the movie
            search_for_movie: Whether to search for the movie immediately
            
        Returns:
            Added movie data or None if error
        """
        logger.info(f"🎬 Adding movie to Radarr: TMDB ID={tmdb_id}, monitored={monitored}, search_for_movie={search_for_movie}")
        
        # Validate TMDB ID first
        if not self.validate_tmdb_id(tmdb_id):
            logger.error(f"❌ Invalid TMDB ID: {tmdb_id}")
            return None
        
        # First, try to get movie details from TMDB lookup
        logger.info(f"🔍 Looking up movie details for TMDB ID: {tmdb_id}")
        movie_lookup = self._make_request('GET', f'/api/v3/movie/lookup/tmdb/{tmdb_id}')
        
        if not movie_lookup:
            logger.warning(f"⚠️ Direct TMDB lookup failed for ID {tmdb_id}, trying alternative lookup...")
            
            # Try alternative lookup using the general lookup endpoint
            # This is a fallback method that might work better
            alternative_lookup = self._lookup_movie_by_tmdb_id_alternative(tmdb_id)
            if alternative_lookup:
                movie_lookup = alternative_lookup
                logger.info(f"✅ Alternative lookup successful: {movie_lookup.get('title', 'Unknown')} ({movie_lookup.get('year', 'Unknown')})")
            else:
                logger.error(f"❌ All TMDB lookup methods failed for TMDB ID: {tmdb_id}")
                logger.info(f"🔄 This suggests the TMDB ID may be invalid or Radarr's TMDB database is not synced")
                logger.info(f"💡 Consider using title-based search instead of TMDB ID lookup")
                return None
        else:
            logger.info(f"✅ Movie lookup successful: {movie_lookup.get('title', 'Unknown')} ({movie_lookup.get('year', 'Unknown')})")
        
        # Get default root folder if not provided
        if not root_folder_path:
            logger.info("📁 Getting default root folder...")
            root_folders = self.get_root_folders()
            if not root_folders:
                logger.error("❌ No root folders found in Radarr")
                return None
            root_folder_path = root_folders[0]['path']
            logger.info(f"📁 Using root folder: {root_folder_path}")
        
        # Get default quality profile if not provided
        if not quality_profile_id:
            logger.info("⚙️ Getting default quality profile...")
            quality_profiles = self.get_quality_profiles()
            if not quality_profiles:
                logger.error("❌ No quality profiles found in Radarr")
                return None
            quality_profile_id = quality_profiles[0]['id']
            logger.info(f"⚙️ Using quality profile ID: {quality_profile_id}")
        
        # Prepare movie data for adding
        movie_data = {
            'title': movie_lookup['title'],
            'titleSlug': movie_lookup['titleSlug'],
            'year': movie_lookup['year'],
            'tmdbId': tmdb_id,
            'rootFolderPath': root_folder_path,
            'qualityProfileId': quality_profile_id,
            'monitored': monitored,
            'addOptions': {
                'searchForMovie': search_for_movie,
                'monitor': 'movieOnly' if monitored else 'none'
            }
        }
        
        logger.info(f"📤 Sending movie data to Radarr: {movie_data}")
        result = self._make_request('POST', '/api/v3/movie', json=movie_data)
        
        if result:
            logger.info(f"✅ Movie added successfully to Radarr: {result.get('title', 'Unknown')} (ID: {result.get('id', 'Unknown')})")
        else:
            logger.error(f"❌ Failed to add movie to Radarr: TMDB ID {tmdb_id}")
        
        return result
    
    def search_for_movie(self, movie_id: int) -> bool:
        """
        Search for a specific movie in Radarr
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            True if search command was sent successfully, False otherwise
        """
        logger.info(f"🔍 Triggering search for movie ID: {movie_id}")
        result = self._make_request('POST', '/api/v3/command', json={
            'name': 'MoviesSearch',
            'movieIds': [movie_id]
        })
        
        if result:
            logger.info(f"✅ Search command sent successfully for movie ID: {movie_id}")
        else:
            logger.error(f"❌ Failed to send search command for movie ID: {movie_id}")
        
        return result is not None
    
    def get_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """
        Get movie by TMDB ID
        
        Args:
            tmdb_id: TMDB movie ID
            
        Returns:
            Movie dictionary or None if not found
        """
        logger.debug(f"🔍 Looking for movie with TMDB ID: {tmdb_id}")
        movies = self.get_movies()
        
        for movie in movies:
            if movie.get('tmdbId') == tmdb_id:
                logger.debug(f"✅ Found movie: {movie.get('title', 'Unknown')} (Radarr ID: {movie.get('id', 'Unknown')})")
                return movie
        
        logger.debug(f"❌ Movie with TMDB ID {tmdb_id} not found in Radarr")
        return None
    
    def is_movie_downloading(self, movie_id: int) -> bool:
        """
        Check if a movie is currently downloading
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            True if movie is downloading, False otherwise
        """
        downloads = self.get_downloads()
        for download in downloads:
            if download.get('movieId') == movie_id:
                status = download.get('status', '').lower()
                return status in ['downloading', 'queued', 'paused']
        return False
    
    def get_download_status_for_movie(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """
        Get download status for a specific movie
        
        Args:
            movie_id: Radarr movie ID
            
        Returns:
            Download status dictionary or None if not downloading
        """
        downloads = self.get_downloads()
        for download in downloads:
            if download.get('movieId') == movie_id:
                return {
                    'status': download.get('status'),
                    'progress': download.get('sizeleft', 0),
                    'size': download.get('size', 0),
                    'timeleft': download.get('timeleft'),
                    'trackedDownloadState': download.get('trackedDownloadState'),
                    'trackedDownloadStatus': download.get('trackedDownloadStatus'),
                    'errorMessage': download.get('errorMessage')
                }
        return None
    
    def get_radarr_config_info(self) -> Dict[str, Any]:
        """
        Get comprehensive Radarr configuration information for debugging
        
        Returns:
            Dictionary with configuration details
        """
        logger.info("🔧 Gathering Radarr configuration information...")
        
        config_info = {
            'base_url': self.base_url,
            'api_key_masked': '*' * (len(self.api_key) - 4) + self.api_key[-4:] if len(self.api_key) > 4 else '****',
            'timeout': self.timeout
        }
        
        try:
            # Test connection
            config_info['connection_test'] = self.test_connection()
            
            # Get system status
            system_status = self.get_system_status()
            if system_status:
                config_info['system_status'] = {
                    'version': system_status.get('version'),
                    'app_name': system_status.get('appName'),
                    'build_time': system_status.get('buildTime')
                }
            
            # Get root folders
            root_folders = self.get_root_folders()
            config_info['root_folders'] = [{'path': rf.get('path'), 'free_space': rf.get('freeSpace')} for rf in root_folders]
            
            # Get quality profiles
            quality_profiles = self.get_quality_profiles()
            config_info['quality_profiles'] = [{'id': qp.get('id'), 'name': qp.get('name')} for qp in quality_profiles]
            
            # Get current downloads count
            downloads = self.get_downloads()
            config_info['current_downloads'] = len(downloads)
            
            # Get total movies count
            movies = self.get_movies()
            config_info['total_movies'] = len(movies)
            
            logger.info(f"🔧 Radarr Config Info: {config_info}")
            
        except Exception as e:
            logger.error(f"❌ Failed to gather Radarr config info: {str(e)}")
            config_info['error'] = str(e)
        
        return config_info
    
    def _lookup_movie_by_tmdb_id_alternative(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """
        Alternative method to lookup movie by TMDB ID using different approaches
        
        Args:
            tmdb_id: TMDB movie ID
            
        Returns:
            Movie data or None if not found
        """
        logger.info(f"🔍 Trying alternative lookup for TMDB ID: {tmdb_id}")
        
        # Method 1: Try using the general lookup endpoint with TMDB ID as search term
        try:
            # Sometimes Radarr's lookup works better with the TMDB ID as a search term
            params = {'term': str(tmdb_id)}
            result = self._make_request('GET', '/api/v3/movie/lookup', params=params)
            
            if result:
                # Look for exact TMDB ID match in results
                for movie in result:
                    if movie.get('tmdbId') == tmdb_id:
                        logger.info(f"✅ Alternative lookup found movie: {movie.get('title', 'Unknown')}")
                        return movie
                        
        except Exception as e:
            logger.debug(f"Alternative lookup method 1 failed: {str(e)}")
        
        # Method 2: Try using the import list endpoint (if available)
        try:
            # Some Radarr versions have different endpoints
            result = self._make_request('GET', f'/api/v3/movie/lookup/imdb/{tmdb_id}')
            if result:
                logger.info(f"✅ Alternative lookup (IMDB method) found movie: {result.get('title', 'Unknown')}")
                return result
        except Exception as e:
            logger.debug(f"Alternative lookup method 2 failed: {str(e)}")
        
        # Method 3: Try with different endpoint variations
        try:
            # Try without the 'lookup' part
            result = self._make_request('GET', f'/api/v3/movie/tmdb/{tmdb_id}')
            if result:
                logger.info(f"✅ Alternative lookup (direct TMDB) found movie: {result.get('title', 'Unknown')}")
                return result
        except Exception as e:
            logger.debug(f"Alternative lookup method 3 failed: {str(e)}")
        
        logger.warning(f"⚠️ All alternative lookup methods failed for TMDB ID: {tmdb_id}")
        return None
    
    def validate_tmdb_id(self, tmdb_id: int) -> bool:
        """
        Validate if a TMDB ID is likely valid
        
        Args:
            tmdb_id: TMDB movie ID
            
        Returns:
            True if ID appears valid, False otherwise
        """
        # Basic validation - TMDB IDs are typically positive integers
        if not isinstance(tmdb_id, int) or tmdb_id <= 0:
            logger.warning(f"⚠️ Invalid TMDB ID format: {tmdb_id}")
            return False
        
        # TMDB IDs are typically in a reasonable range
        if tmdb_id > 999999999:  # Very large numbers are suspicious
            logger.warning(f"⚠️ TMDB ID seems unusually large: {tmdb_id}")
            return False
        
        logger.debug(f"✅ TMDB ID format appears valid: {tmdb_id}")
        return True
    
    def test_tmdb_lookup(self, tmdb_id: int) -> Dict[str, Any]:
        """
        Test TMDB lookup with detailed debugging information
        
        Args:
            tmdb_id: TMDB movie ID to test
            
        Returns:
            Dictionary with test results and debugging info
        """
        logger.info(f"🧪 Testing TMDB lookup for ID: {tmdb_id}")
        
        test_results = {
            'tmdb_id': tmdb_id,
            'validation': self.validate_tmdb_id(tmdb_id),
            'direct_lookup': None,
            'alternative_lookup': None,
            'error_messages': []
        }
        
        # Test direct lookup
        try:
            logger.info(f"🧪 Testing direct lookup: /api/v3/movie/lookup/tmdb/{tmdb_id}")
            result = self._make_request('GET', f'/api/v3/movie/lookup/tmdb/{tmdb_id}')
            test_results['direct_lookup'] = result is not None
            if result:
                test_results['direct_lookup_data'] = {
                    'title': result.get('title'),
                    'year': result.get('year'),
                    'tmdbId': result.get('tmdbId')
                }
            else:
                test_results['error_messages'].append("Direct lookup returned None")
        except Exception as e:
            test_results['error_messages'].append(f"Direct lookup exception: {str(e)}")
        
        # Test alternative lookup
        try:
            logger.info(f"🧪 Testing alternative lookup methods")
            alt_result = self._lookup_movie_by_tmdb_id_alternative(tmdb_id)
            test_results['alternative_lookup'] = alt_result is not None
            if alt_result:
                test_results['alternative_lookup_data'] = {
                    'title': alt_result.get('title'),
                    'year': alt_result.get('year'),
                    'tmdbId': alt_result.get('tmdbId')
                }
        except Exception as e:
            test_results['error_messages'].append(f"Alternative lookup exception: {str(e)}")
        
        logger.info(f"🧪 TMDB lookup test results: {test_results}")
        return test_results
    
    def add_movie_by_title_and_year(self, title: str, year: int, root_folder_path: str = None, quality_profile_id: int = None, monitored: bool = True, search_for_movie: bool = True) -> Optional[Dict[str, Any]]:
        """
        Add a movie to Radarr using title and year (fallback when TMDB ID fails)
        
        Args:
            title: Movie title
            year: Movie year
            root_folder_path: Root folder path for the movie
            quality_profile_id: Quality profile ID
            monitored: Whether to monitor the movie
            search_for_movie: Whether to search for the movie immediately
            
        Returns:
            Added movie data or None if error
        """
        logger.info(f"🎬 Adding movie to Radarr by title: '{title}' ({year}), monitored={monitored}, search_for_movie={search_for_movie}")
        
        # Search for the movie by title
        logger.info(f"🔍 Searching for movie by title: '{title}'")
        search_results = self.search_movies(title)
        
        if not search_results:
            logger.error(f"❌ No search results found for title: '{title}'")
            return None
        
        # Find the best match by title and year
        best_match = None
        for movie in search_results:
            movie_title = movie.get('title', '').lower()
            movie_year = movie.get('year', 0)
            
            # Check for exact title match
            if movie_title == title.lower():
                if movie_year == year:
                    best_match = movie
                    logger.info(f"✅ Found exact match: {movie.get('title')} ({movie.get('year')})")
                    break
                elif not best_match:  # Store first title match as fallback
                    best_match = movie
                    logger.info(f"✅ Found title match (year differs): {movie.get('title')} ({movie.get('year')})")
        
        if not best_match:
            # If no exact match, try partial title match
            logger.info(f"🔍 No exact title match found, trying partial matches...")
            for movie in search_results:
                movie_title = movie.get('title', '').lower()
                if title.lower() in movie_title or movie_title in title.lower():
                    best_match = movie
                    logger.info(f"✅ Found partial match: {movie.get('title')} ({movie.get('year')})")
                    break
        
        if not best_match:
            logger.error(f"❌ No suitable match found for title: '{title}' ({year})")
            search_results_preview = [f"{m.get('title', 'Unknown')} ({m.get('year', 'Unknown')})" for m in search_results[:5]]
            logger.info(f"🔍 Available search results: {search_results_preview}")
            return None
        
        logger.info(f"✅ Using movie: {best_match.get('title')} ({best_match.get('year')}) - TMDB ID: {best_match.get('tmdbId')}")
        
        # Get default root folder if not provided
        if not root_folder_path:
            logger.info("📁 Getting default root folder...")
            root_folders = self.get_root_folders()
            if not root_folders:
                logger.error("❌ No root folders found in Radarr")
                return None
            root_folder_path = root_folders[0]['path']
            logger.info(f"📁 Using root folder: {root_folder_path}")
        
        # Get default quality profile if not provided
        if not quality_profile_id:
            logger.info("⚙️ Getting default quality profile...")
            quality_profiles = self.get_quality_profiles()
            if not quality_profiles:
                logger.error("❌ No quality profiles found in Radarr")
                return None
            quality_profile_id = quality_profiles[0]['id']
            logger.info(f"⚙️ Using quality profile ID: {quality_profile_id}")
        
        # Prepare movie data for adding
        movie_data = {
            'title': best_match['title'],
            'titleSlug': best_match['titleSlug'],
            'year': best_match['year'],
            'tmdbId': best_match['tmdbId'],
            'rootFolderPath': root_folder_path,
            'qualityProfileId': quality_profile_id,
            'monitored': monitored,
            'addOptions': {
                'searchForMovie': search_for_movie,
                'monitor': 'movieOnly' if monitored else 'none'
            }
        }
        
        logger.info(f"📤 Sending movie data to Radarr: {movie_data}")
        result = self._make_request('POST', '/api/v3/movie', json=movie_data)
        
        if result:
            logger.info(f"✅ Movie added successfully to Radarr: {result.get('title', 'Unknown')} (ID: {result.get('id', 'Unknown')})")
        else:
            logger.error(f"❌ Failed to add movie to Radarr: {title} ({year})")
        
        return result