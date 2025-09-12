#!/usr/bin/env python3
"""
Radarr API Client for managing movies and downloads
"""

import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

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
        
        try:
            response = self.session.request(
                method, 
                url, 
                timeout=self.timeout,
                **kwargs
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 201:
                return response.json()
            elif response.status_code == 204:
                return {}
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            return None
    
    def test_connection(self) -> bool:
        """
        Test connection to Radarr API
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            result = self._make_request('GET', '/api/v3/system/status')
            return result is not None
        except Exception as e:
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
        result = self._make_request('GET', '/api/v3/queue')
        return result.get('records', []) if result else []
    
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
