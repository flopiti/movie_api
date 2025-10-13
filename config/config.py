#!/usr/bin/env python3
"""
Configuration management for Movie Management REST API.
Handles movie file paths, media paths, download paths, and movie assignments
using Redis storage with local JSON fallback.
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import redis

# Configuration constants
CONFIG_FILE = os.path.expanduser("~/movie-config/config.json")
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')  # Default to localhost for better compatibility
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Initialize Redis Client
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from clients.redis_client import RedisClient

redis_client = RedisClient()

class Config:
    """Manages the application configuration including movie file paths using Redis storage."""
    
    def __init__(self, config_file: str = CONFIG_FILE, use_redis: bool = True):
        self.config_file = config_file
        self.use_redis = use_redis and redis_client is not None
        
        # Always initialize local data for fallback purposes
        self.data = self._load_local_config()
        
        # Initialize default SMS templates if none exist
        self._initialize_default_sms_templates()
        
    def _load_local_config(self) -> Dict[str, Any]:
        """Load configuration from local JSON file (fallback)."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Default configuration
        return {
            "movie_file_paths": [],
            "media_paths": [],
            "download_paths": [],
            "tmdb_api_key": TMDB_API_KEY,
            "radarr_url": "http://192.168.0.10:7878",
            "radarr_api_key": "5a71ac347fb845da90e2284762335a1a",
            "movie_assignments": {}
        }
    
    def _save_local_config(self) -> None:
        """Save configuration to local JSON file (fallback)."""
        try:
            # Ensure the parent directory exists
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            raise Exception(f"Failed to save local configuration: {str(e)}")
    
    def _get_redis_data(self) -> Dict[str, Any]:
        """Get configuration data from Redis."""
        try:
            data = redis_client.get('movie_config')
            
            if data is None:
                # Initialize Redis with default data
                default_data = {
                    "movie_file_paths": [],
                    "media_paths": [],
                    "download_paths": [],
                    "tmdb_api_key": TMDB_API_KEY,
                    "radarr_url": "http://192.168.0.10:7878",
                    "radarr_api_key": "",
                    "movie_assignments": {},
                    "sms_reply_settings": {
                        "auto_reply_enabled": True,
                        "fallback_message": "Thanks for your message! I received: '{message}' from {sender} at {timestamp}. Configure your number in the system to get personalized responses.",
                        "reply_delay_seconds": 0,
                        "max_replies_per_day": 10,
                        "blocked_numbers": [],
                        "use_chatgpt": True,
                        "chatgpt_prompt": "You are a helpful assistant. Please respond to this SMS message in a friendly and concise way. Keep your response under 160 characters and appropriate for SMS communication.\n\nMessage: {message}\nFrom: {sender}"
                    }
                }
                redis_client.set('movie_config', json.dumps(default_data))
                return default_data
            
            parsed_data = json.loads(data)
            return parsed_data
        except Exception as e:
            raise Exception(f"Failed to get Redis configuration: {str(e)}")
    
    def _save_redis_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to Redis."""
        try:
            redis_client.set('movie_config', json.dumps(data))
        except Exception as e:
            raise Exception(f"Failed to save Redis configuration: {str(e)}")
    
    def get_movie_paths(self) -> List[str]:
        """Get list of movie file paths."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                movie_paths = data.get("movie_file_paths", [])
                return movie_paths  # Always return the list, even if empty
            except Exception as e:
                fallback_paths = self.data.get("movie_file_paths", [])
                return fallback_paths
        else:
            local_paths = self.data.get("movie_file_paths", [])
            return local_paths
    
    def add_movie_path(self, path: str) -> bool:
        """Add a movie file path if it doesn't already exist."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.setdefault("movie_file_paths", [])
                if path not in paths:
                    paths.append(path)
                    self._save_redis_data(data)
                    return True
                return False
            except Exception as e:
                # Fallback to local storage
                paths = self.data.setdefault("movie_file_paths", [])
                if path not in paths:
                    paths.append(path)
                    self._save_local_config()
                    return True
                return False
        else:
            paths = self.data.setdefault("movie_file_paths", [])
            if path not in paths:
                paths.append(path)
                self._save_local_config()
                return True
            return False
    
    def remove_movie_path(self, path: str) -> bool:
        """Remove a movie file path."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.get("movie_file_paths", [])
                if path in paths:
                    paths.remove(path)
                    self._save_redis_data(data)
                    return True
                return False
            except Exception as e:
                # Fallback to local storage
                paths = self.data.get("movie_file_paths", [])
                if path in paths:
                    paths.remove(path)
                    self._save_local_config()
                    return True
                return False
        else:
            paths = self.data.get("movie_file_paths", [])
            if path in paths:
                paths.remove(path)
                self._save_local_config()
                return True
            return False
    
    def get_movie_assignments(self) -> Dict[str, Dict[str, Any]]:
        """Get all movie assignments for files."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                assignments = data.get("movie_assignments", {})
                return assignments
            except Exception as e:
                return self.data.get("movie_assignments", {})
        else:
            return self.data.get("movie_assignments", {})
    
    def assign_movie_to_file(self, file_path: str, movie_data: Dict[str, Any]) -> bool:
        """Assign a movie to a file."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                assignments = data.setdefault("movie_assignments", {})
                assignments[file_path] = movie_data
                self._save_redis_data(data)
                return True
            except Exception as e:
                # Fallback to local storage
                assignments = self.data.setdefault("movie_assignments", {})
                assignments[file_path] = movie_data
                self._save_local_config()
                return True
        else:
            assignments = self.data.setdefault("movie_assignments", {})
            assignments[file_path] = movie_data
            self._save_local_config()
            return True
    
    def remove_movie_assignment(self, file_path: str) -> bool:
        """Remove a movie assignment from a file."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                assignments = data.get("movie_assignments", {})
                
                if file_path in assignments:
                    del assignments[file_path]
                    self._save_redis_data(data)
                    # Also update local data to keep it in sync
                    self.data["movie_assignments"] = data.get("movie_assignments", {})
                    return True
                else:
                    return False
            except Exception as e:
                # Fallback to local storage
                assignments = self.data.get("movie_assignments", {})
                if file_path in assignments:
                    del assignments[file_path]
                    self._save_local_config()
                    return True
                else:
                    return False
        else:
            assignments = self.data.get("movie_assignments", {})
            if file_path in assignments:
                del assignments[file_path]
                self._save_local_config()
                return True
            else:
                return False

    def batch_update_assignments(self, updates: List[tuple]) -> bool:
        """Batch update movie assignments to reduce Redis calls.
        
        Args:
            updates: List of (old_path, new_path, movie_data) tuples
        """
        if not updates:
            return True

        if self.use_redis:
            try:
                # Get all current data once
                data = self._get_redis_data()
                assignments = data.setdefault("movie_assignments", {})
                
                # Process all updates in memory
                for old_path, new_path, movie_data in updates:
                    # Remove old assignment
                    if old_path and old_path in assignments:
                        del assignments[old_path]
                    
                    # Add new assignment
                    if new_path and movie_data:
                        assignments[new_path] = movie_data
                
                # Save all changes at once
                self._save_redis_data(data)
                return True
            except Exception as e:
                return False
        else:
            # Local storage batch update
            assignments = self.data.setdefault("movie_assignments", {})
            for old_path, new_path, movie_data in updates:
                if old_path and old_path in assignments:
                    del assignments[old_path]
                if new_path and movie_data:
                    assignments[new_path] = movie_data
            
            self._save_local_config()
            return True

    def get_media_paths(self) -> List[Dict[str, Any]]:
        """Get list of media paths with space information."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.get("media_paths", [])
            except Exception as e:
                paths = self.data.get("media_paths", [])
        else:
            paths = self.data.get("media_paths", [])
        
        # Always refresh space info for all paths
        updated_paths = []
        for path_info in paths:
            path = path_info.get('path', '')
            if path:
                updated_info = self._get_path_space_info(path)
                if updated_info:
                    updated_paths.append(updated_info)
                else:
                    updated_paths.append(path_info)
            else:
                updated_paths.append(path_info)
        
        return updated_paths
    
    def add_media_path(self, path: str) -> bool:
        """Add a media path if it doesn't already exist."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.setdefault("media_paths", [])
                
                # Check if path already exists
                if any(p.get('path') == path for p in paths):
                    return False
                
                # Add new path with space information
                new_path_info = self._get_path_space_info(path)
                paths.append(new_path_info)
                self._save_redis_data(data)
                return True
            except Exception as e:
                # Fallback to local storage
                paths = self.data.setdefault("media_paths", [])
                if not any(p.get('path') == path for p in paths):
                    new_path_info = self._get_path_space_info(path)
                    paths.append(new_path_info)
                    self._save_local_config()
                    return True
                return False
        else:
            paths = self.data.setdefault("media_paths", [])
            if not any(p.get('path') == path for p in paths):
                new_path_info = self._get_path_space_info(path)
                paths.append(new_path_info)
                self._save_local_config()
                return True
            return False
    
    def remove_media_path(self, path: str) -> bool:
        """Remove a media path."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.get("media_paths", [])
                original_length = len(paths)
                paths[:] = [p for p in paths if p.get('path') != path]
                if len(paths) < original_length:
                    self._save_redis_data(data)
                    return True
                return False
            except Exception as e:
                # Fallback to local storage
                paths = self.data.get("media_paths", [])
                original_length = len(paths)
                paths[:] = [p for p in paths if p.get('path') != path]
                if len(paths) < original_length:
                    self._save_local_config()
                    return True
                return False
        else:
            paths = self.data.get("media_paths", [])
            original_length = len(paths)
            paths[:] = [p for p in paths if p.get('path') != path]
            if len(paths) < original_length:
                self._save_local_config()
                return True
            return False
    
    def refresh_media_path_space(self, path: str) -> Dict[str, Any]:
        """Refresh space information for a specific media path."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.get("media_paths", [])
                for path_info in paths:
                    if path_info.get('path') == path:
                        updated_info = self._get_path_space_info(path)
                        path_info.update(updated_info)
                        self._save_redis_data(data)
                        return updated_info
                return {}
            except Exception as e:
                return {}
        else:
            paths = self.data.get("media_paths", [])
            for path_info in paths:
                if path_info.get('path') == path:
                    updated_info = self._get_path_space_info(path)
                    path_info.update(updated_info)
                    self._save_local_config()
                    return updated_info
            return {}
    
    def refresh_all_media_paths_space(self) -> List[Dict[str, Any]]:
        """Refresh space information for all media paths."""
        paths = self.get_media_paths()
        updated_paths = []
        
        for path_info in paths:
            path = path_info.get('path')
            if path:
                updated_info = self._get_path_space_info(path)
                updated_info['path'] = path  # Ensure path is included
                updated_paths.append(updated_info)
        
        # Update the stored data
        if self.use_redis:
            try:
                data = self._get_redis_data()
                data['media_paths'] = updated_paths
                self._save_redis_data(data)
            except Exception as e:
                pass
        else:
            self.data['media_paths'] = updated_paths
            self._save_local_config()
        
        return updated_paths
    
    def get_download_paths(self) -> List[str]:
        """Get list of download paths."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                if data:
                    download_paths = data.get("download_paths", [])
                    return download_paths  # Always return the list, even if empty
                else:
                    fallback_paths = self.data.get("download_paths", [])
                    return fallback_paths
            except Exception as e:
                local_paths = self.data.get("download_paths", [])
                return local_paths
        else:
            local_paths = self.data.get("download_paths", [])
            return local_paths

    def add_download_path(self, path: str) -> bool:
        """Add a download path if it doesn't already exist."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                if data:
                    paths = data.setdefault("download_paths", [])
                    if path not in paths:
                        paths.append(path)
                        self._save_redis_data(data)
                        return True
                    else:
                        return False
                else:
                    paths = self.data.setdefault("download_paths", [])
                    if path not in paths:
                        paths.append(path)
                        self._save_local_config()
                        return True
                    else:
                        return False
            except Exception as e:
                paths = self.data.setdefault("download_paths", [])
                if path not in paths:
                    paths.append(path)
                    self._save_local_config()
                    return True
                else:
                    return False
        else:
            paths = self.data.setdefault("download_paths", [])
            if path not in paths:
                paths.append(path)
                self._save_local_config()
                return True
            else:
                return False

    def remove_download_path(self, path: str) -> bool:
        """Remove a download path."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                if data:
                    paths = data.get("download_paths", [])
                    if path in paths:
                        paths.remove(path)
                        self._save_redis_data(data)
                        return True
                    else:
                        return False
                else:
                    paths = self.data.get("download_paths", [])
                    if path in paths:
                        paths.remove(path)
                        self._save_local_config()
                        return True
                    else:
                        return False
            except Exception as e:
                paths = self.data.get("download_paths", [])
                if path in paths:
                    paths.remove(path)
                    self._save_local_config()
                    return True
                else:
                    return False
        else:
            paths = self.data.get("download_paths", [])
            if path in paths:
                paths.remove(path)
                self._save_local_config()
                return True
            else:
                return False

    def get_download_path_contents(self, path: str) -> Dict[str, Any]:
        """Get contents of a download path (folders and files)."""
        try:
            if not os.path.exists(path):
                return {
                    'path': path,
                    'exists': False,
                    'folders': [],
                    'files': [],
                    'error': 'Path does not exist'
                }
            
            if not os.path.isdir(path):
                return {
                    'path': path,
                    'exists': False,
                    'folders': [],
                    'files': [],
                    'error': 'Path is not a directory'
                }
            
            folders = []
            files = []
            
            # Get all items in the directory
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                
                if os.path.isdir(item_path):
                    # Get folder info
                    try:
                        stat_info = os.stat(item_path)
                        folders.append({
                            'name': item,
                            'path': item_path,
                            'modified': stat_info.st_mtime,
                            'size': 0  # Folders don't have a direct size
                        })
                    except Exception as e:
                        folders.append({
                            'name': item,
                            'path': item_path,
                            'modified': 0,
                            'size': 0,
                            'error': str(e)
                        })
                elif os.path.isfile(item_path):
                    # Get file info
                    try:
                        stat_info = os.stat(item_path)
                        files.append({
                            'name': item,
                            'path': item_path,
                            'modified': stat_info.st_mtime,
                            'size': stat_info.st_size,
                            'is_media': self._is_media_file(Path(item_path))
                        })
                    except Exception as e:
                        files.append({
                            'name': item,
                            'path': item_path,
                            'modified': 0,
                            'size': 0,
                            'is_media': self._is_media_file(Path(item_path)),
                            'error': str(e)
                        })
            
            # Sort folders and files by name
            folders.sort(key=lambda x: x['name'].lower())
            files.sort(key=lambda x: x['name'].lower())
            
            return {
                'path': path,
                'exists': True,
                'folders': folders,
                'files': files,
                'total_folders': len(folders),
                'total_files': len(files),
                'media_files': len([f for f in files if f.get('is_media', False)])
            }
            
        except Exception as e:
            return {
                'path': path,
                'exists': False,
                'folders': [],
                'files': [],
                'error': str(e)
            }

    def get_radarr_client(self):
        """Get Radarr client instance."""
        try:
            from clients.radarr_client import RadarrClient
            radarr_url = self.data.get('radarr_url', 'http://192.168.0.10:7878')
            radarr_api_key = self.data.get('radarr_api_key', '5a71ac347fb845da90e2284762335a1a')
            
            if not radarr_api_key:
                return None
                
            return RadarrClient(radarr_url, radarr_api_key)
        except ImportError as e:
            return None
        except Exception as e:
            return None

    def get_download_files(self) -> List[Dict[str, Any]]:
        """Get all media files from download paths (flattened, no folders)."""
        all_files = []
        download_paths = self.get_download_paths()
        
        if not download_paths:
            return all_files
        
        for path in download_paths:
            try:
                if not os.path.exists(path) or not os.path.isdir(path):
                    continue
                
                # Get all files recursively from this download path
                for root, dirs, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        # Check if it's a media file
                        if self._is_media_file(Path(file_path)):
                            try:
                                stat_info = os.stat(file_path)
                                relative_path = os.path.relpath(file_path, path)
                                
                                file_info = {
                                    'name': file,
                                    'path': file_path,
                                    'relative_path': relative_path,
                                    'directory': os.path.dirname(file_path),
                                    'size': stat_info.st_size,
                                    'modified': stat_info.st_mtime,
                                    'source_path': path,
                                    'is_download_file': True
                                }
                                
                                # Check if this file has a movie assignment
                                movie_assignments = self.get_movie_assignments()
                                if file_path in movie_assignments:
                                    file_info['movie'] = movie_assignments[file_path]
                                    
                                    # Add filename and folder info
                                    movie_data = movie_assignments[file_path]
                                    file_info['filenameInfo'] = self._generate_filename_info(movie_data, file_path)
                                    file_info['folderInfo'] = self._generate_folder_info(movie_data, file_path)
                                
                                all_files.append(file_info)
                                
                            except Exception as e:
                                continue
                                
            except Exception as e:
                continue
        
        # Sort by name for consistent ordering
        all_files.sort(key=lambda x: x['name'].lower())
        return all_files

    def search_radarr_movies(self, query: str) -> List[Dict[str, Any]]:
        """Search for movies using Radarr API."""
        radarr_client = self.get_radarr_client()
        if not radarr_client:
            return []
        
        try:
            # Test connection first
            if not radarr_client.test_connection():
                return []
            
            # Search for movies
            movies = radarr_client.search_movies(query)
            return movies
            
        except Exception as e:
            return []

    def compare_radarr_vs_plex(self) -> Dict[str, Any]:
        """Compare movies between Radarr and Plex to find movies in Radarr but not in Plex."""
        try:
            # Get Radarr client
            radarr_client = self.get_radarr_client()
            if not radarr_client:
                return {
                    'error': 'Radarr client not available - check API key configuration',
                    'radarr_movies': [],
                    'plex_movies': [],
                    'movies_in_radarr_not_in_plex': [],
                    'movies_in_plex_not_in_radarr': [],
                    'total_radarr': 0,
                    'total_plex': 0,
                    'comparison_summary': {}
                }
            
            # Test Radarr connection
            if not radarr_client.test_connection():
                return {
                    'error': 'Radarr connection failed',
                    'radarr_movies': [],
                    'plex_movies': [],
                    'movies_in_radarr_not_in_plex': [],
                    'movies_in_plex_not_in_radarr': [],
                    'total_radarr': 0,
                    'total_plex': 0,
                    'comparison_summary': {}
                }
            
            # Get movies from Radarr
            radarr_movies = radarr_client.get_movies()

            # Get movies from Plex
            from clients.plex_client import PlexClient
            plex_client = PlexClient()
            plex_movies = plex_client.get_all_movies()

            # Helper function to extract TMDB ID from Plex GUID
            def extract_tmdb_id_from_plex_guid(guid):
                """Extract TMDB ID from Plex GUID format: tmdb://tmdb/movie/12345"""
                if guid and guid.startswith('tmdb://tmdb/movie/'):
                    try:
                        return int(guid.split('/')[-1])
                    except (ValueError, IndexError):
                        return None
                return None
            
            # Create TMDB ID sets for comparison (more reliable than title matching)
            radarr_tmdb_ids = set()
            plex_tmdb_ids = set()
            
            # Process Radarr movies
            radarr_movie_data = []
            for movie in radarr_movies:
                title = movie.get('title', '')
                year = movie.get('year', '')
                tmdb_id = movie.get('tmdbId')
                if title and tmdb_id:
                    radarr_tmdb_ids.add(tmdb_id)
                    radarr_movie_data.append({
                        'id': movie.get('id'),
                        'title': title,
                        'year': year,
                        'tmdbId': tmdb_id,
                        'hasFile': movie.get('hasFile', False),
                        'monitored': movie.get('monitored', False),
                        'status': movie.get('status', ''),
                        'qualityProfileId': movie.get('qualityProfileId'),
                        'rootFolderPath': movie.get('rootFolderPath', ''),
                        'folderName': movie.get('folderName', '')
                    })
            
            # Process Plex movies
            plex_movie_data = []
            for movie in plex_movies:
                title = movie.get('title', '')
                year = movie.get('year', '')
                guid = movie.get('guid', '')
                tmdb_id = extract_tmdb_id_from_plex_guid(guid)
                if title and tmdb_id:
                    plex_tmdb_ids.add(tmdb_id)
                    plex_movie_data.append({
                        'id': movie.get('id'),
                        'title': title,
                        'year': year,
                        'tmdbId': tmdb_id,
                        'guid': guid,
                        'library': movie.get('library', ''),
                        'addedAt': movie.get('addedAt', ''),
                        'updatedAt': movie.get('updatedAt', '')
                    })
            
            # Find movies in Radarr but not in Plex (using TMDB ID matching)
            movies_in_radarr_not_in_plex = []
            for radarr_movie in radarr_movie_data:
                if radarr_movie['tmdbId'] not in plex_tmdb_ids:
                    movies_in_radarr_not_in_plex.append(radarr_movie)
            
            # Find movies in Plex but not in Radarr (using TMDB ID matching)
            movies_in_plex_not_in_radarr = []
            for plex_movie in plex_movie_data:
                if plex_movie['tmdbId'] not in radarr_tmdb_ids:
                    movies_in_plex_not_in_radarr.append(plex_movie)
            
            # Create comparison summary
            comparison_summary = {
                'total_radarr_movies': len(radarr_movie_data),
                'total_plex_movies': len(plex_movie_data),
                'movies_in_radarr_not_in_plex_count': len(movies_in_radarr_not_in_plex),
                'movies_in_plex_not_in_radarr_count': len(movies_in_plex_not_in_radarr),
                'common_movies_count': len(radarr_tmdb_ids.intersection(plex_tmdb_ids)),
                'radarr_monitored_count': len([m for m in radarr_movie_data if m.get('monitored', False)]),
                'radarr_with_files_count': len([m for m in radarr_movie_data if m.get('hasFile', False)])
            }

            return {
                'radarr_movies': radarr_movie_data,
                'plex_movies': plex_movie_data,
                'movies_in_radarr_not_in_plex': movies_in_radarr_not_in_plex,
                'movies_in_plex_not_in_radarr': movies_in_plex_not_in_radarr,
                'total_radarr': len(radarr_movie_data),
                'total_plex': len(plex_movie_data),
                'comparison_summary': comparison_summary,
                'success': True
            }
            
        except Exception as e:
            return {
                'error': f'Failed to compare Radarr vs Plex: {str(e)}',
                'radarr_movies': [],
                'plex_movies': [],
                'movies_in_radarr_not_in_plex': [],
                'movies_in_plex_not_in_radarr': [],
                'total_radarr': 0,
                'total_plex': 0,
                'comparison_summary': {},
                'success': False
            }
    
    def _get_path_space_info(self, path: str) -> Dict[str, Any]:
        """Get disk space information for a path using df command."""
        try:
            if not os.path.exists(path):
                return {
                    'path': path,
                    'exists': False,
                    'total_space': 0,
                    'used_space': 0,
                    'free_space': 0,
                    'total_space_gb': 0,
                    'used_space_gb': 0,
                    'free_space_gb': 0,
                    'usage_percentage': 0,
                    'error': 'Path does not exist'
                }
            
            # Use df command to get accurate disk usage for mount points
            import subprocess
            result = subprocess.run(['df', '-k', path], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            
            # Parse the df output (skip header line)
            if len(lines) < 2:
                raise Exception("Invalid df output")
                
            data_line = lines[1].split()
            if len(data_line) < 4:
                raise Exception("Incomplete df output")
            
            # df output: Filesystem, 1K-blocks, Used, Available, Use%, Mounted on
            # Values are in 1K blocks, so multiply by 1024 to get bytes
            total = int(data_line[1]) * 1024
            used = int(data_line[2]) * 1024
            free = int(data_line[3]) * 1024

            # Convert to GB
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            
            # Calculate usage percentage
            usage_percentage = (used / total) * 100 if total > 0 else 0
            
            return {
                'path': path,
                'exists': True,
                'total_space': total,
                'used_space': used,
                'free_space': free,
                'total_space_gb': round(total_gb, 2),
                'used_space_gb': round(used_gb, 2),
                'free_space_gb': round(free_gb, 2),
                'usage_percentage': round(usage_percentage, 2),
                'last_updated': int(time.time())
            }
        except Exception as e:
            return {
                'path': path,
                'exists': False,
                'total_space': 0,
                'used_space': 0,
                'free_space': 0,
                'total_space_gb': 0,
                'used_space_gb': 0,
                'free_space_gb': 0,
                'usage_percentage': 0,
                'error': f"Failed to get disk space: {str(e)}"
            }

    # SMS Reply Management Methods
    def get_sms_reply_templates(self) -> List[Dict[str, Any]]:
        """Get all SMS reply templates."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                templates = data.get("sms_reply_templates", [])
                return templates
            except Exception as e:
                return self.data.get("sms_reply_templates", [])
        else:
            return self.data.get("sms_reply_templates", [])

    def add_sms_reply_template(self, template_data: Dict[str, Any]) -> bool:
        """Add a new SMS reply template."""
        import uuid
        template_data['id'] = str(uuid.uuid4())
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                templates = data.setdefault("sms_reply_templates", [])
                templates.append(template_data)
                self._save_redis_data(data)
                return True
            except Exception as e:
                templates = self.data.setdefault("sms_reply_templates", [])
                templates.append(template_data)
                self._save_local_config()
                return True
        else:
            templates = self.data.setdefault("sms_reply_templates", [])
            templates.append(template_data)
            self._save_local_config()
            return True

    def update_sms_reply_template(self, template_id: str, updated_template: Dict[str, Any]) -> bool:
        """Update an existing SMS reply template."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                templates = data.get("sms_reply_templates", [])
                
                for i, template in enumerate(templates):
                    if template.get('id') == template_id:
                        templates[i] = updated_template
                        self._save_redis_data(data)
                        return True
                return False
            except Exception as e:
                templates = self.data.get("sms_reply_templates", [])
                for i, template in enumerate(templates):
                    if template.get('id') == template_id:
                        templates[i] = updated_template
                        self._save_local_config()
                        return True
                return False
        else:
            templates = self.data.get("sms_reply_templates", [])
            for i, template in enumerate(templates):
                if template.get('id') == template_id:
                    templates[i] = updated_template
                    self._save_local_config()
                    return True
            return False

    def delete_sms_reply_template(self, template_id: str) -> bool:
        """Delete an SMS reply template."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                templates = data.get("sms_reply_templates", [])
                
                for i, template in enumerate(templates):
                    if template.get('id') == template_id:
                        del templates[i]
                        self._save_redis_data(data)
                        return True
                return False
            except Exception as e:
                templates = self.data.get("sms_reply_templates", [])
                for i, template in enumerate(templates):
                    if template.get('id') == template_id:
                        del templates[i]
                        self._save_local_config()
                        return True
                return False
        else:
            templates = self.data.get("sms_reply_templates", [])
            for i, template in enumerate(templates):
                if template.get('id') == template_id:
                    del templates[i]
                    self._save_local_config()
                    return True
            return False

    def get_sms_reply_settings(self) -> Dict[str, Any]:
        """Get SMS reply settings."""
        default_settings = {
            "auto_reply_enabled": True,
            "fallback_message": "Thanks for your message! I received: '{message}' from {sender} at {timestamp}. Configure your number in the system to get personalized responses.",
            "reply_delay_seconds": 0,
            "max_replies_per_day": 10,
            "blocked_numbers": [],
            "use_chatgpt": False,
            "chatgpt_prompt": "You are a helpful assistant. Please respond to this SMS message in a friendly and concise way. Keep your response under 160 characters and appropriate for SMS communication.\n\nMessage: {message}\nFrom: {sender}"
        }
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                settings = data.get("sms_reply_settings", default_settings)
                return settings
            except Exception as e:
                return self.data.get("sms_reply_settings", default_settings)
        else:
            return self.data.get("sms_reply_settings", default_settings)

    def update_sms_reply_settings(self, settings: Dict[str, Any]) -> bool:
        """Update SMS reply settings."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                data["sms_reply_settings"] = settings
                self._save_redis_data(data)
                return True
            except Exception as e:
                self.data["sms_reply_settings"] = settings
                self._save_local_config()
                return True
        else:
            self.data["sms_reply_settings"] = settings
            self._save_local_config()
            return True

    def _initialize_default_sms_templates(self) -> None:
        """Initialize default SMS reply templates if none exist."""
        # Don't auto-initialize templates - let user configure via interface
        pass

    # Helper methods for media file detection and filename formatting
    def _is_media_file(self, file_path: Path) -> bool:
        """Check if a file is a media file based on its extension."""
        MEDIA_EXTENSIONS = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
            '.mpg', '.mpeg', '.3gp', '.asf', '.rm', '.rmvb', '.vob', '.ts'
        }
        return file_path.suffix.lower() in MEDIA_EXTENSIONS

    def _generate_filename_info(self, movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Generate filename information for a movie file."""
        standard_filename = self._generate_standard_filename(movie_data, file_path)
        current_filename = Path(file_path).name
        needs_rename = self._should_rename_file(file_path, standard_filename)
        
        return {
            'current_filename': current_filename,
            'standard_filename': standard_filename,
            'needs_rename': needs_rename
        }

    def _generate_folder_info(self, movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Generate folder information for a movie file."""
        current_folder_path = str(Path(file_path).parent)
        standard_foldername = self._generate_standard_foldername(movie_data)
        folder_needs_rename = self._should_rename_folder(current_folder_path, standard_foldername)
        current_foldername = Path(file_path).parent.name
        
        return {
            'current_foldername': current_foldername,
            'current_folder_path': current_folder_path,
            'standard_foldername': standard_foldername,
            'needs_rename': folder_needs_rename
        }

    def _generate_standard_filename(self, movie_data: Dict[str, Any], original_filename: str) -> str:
        """Generate a standard filename format: Title_YYYY.extension"""
        title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        # Extract year from release date
        year = ''
        if release_date:
            try:
                year = release_date.split('-')[0]  # Extract year from YYYY-MM-DD format
            except (IndexError, ValueError):
                pass
        
        # Clean title: remove special characters and replace spaces with underscores
        clean_title = title.replace(' ', '_')
        clean_title = ''.join(c for c in clean_title if c.isalnum() or c in '_-')
        
        # Extract original file extension
        original_path = Path(original_filename)
        extension = original_path.suffix.lower()
        
        # Build standard filename
        if year:
            standard_filename = f"{clean_title}_{year}{extension}"
        else:
            standard_filename = f"{clean_title}{extension}"
        
        return standard_filename

    def _generate_standard_foldername(self, movie_data: Dict[str, Any]) -> str:
        """Generate a standard folder name format: Title_YYYY"""
        title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        # Extract year from release date
        year = ''
        if release_date:
            try:
                year = release_date.split('-')[0]  # Extract year from YYYY-MM-DD format
            except (IndexError, ValueError):
                pass
        
        # Clean title: remove special characters and replace spaces with underscores
        clean_title = title.replace(' ', '_')
        clean_title = ''.join(c for c in clean_title if c.isalnum() or c in '_-')
        
        # Build standard folder name
        if year:
            standard_foldername = f"{clean_title}_{year}"
        else:
            standard_foldername = f"{clean_title}"
        
        return standard_foldername

    def _should_rename_file(self, current_filename: str, standard_filename: str) -> bool:
        """Check if the current filename differs from the standard format."""
        # Extract just the filename without path
        current_name = Path(current_filename).name
        return current_name != standard_filename

    def _should_rename_folder(self, current_folder_path: str, standard_foldername: str) -> bool:
        """Check if the current folder name differs from the standard format."""
        # Extract just the folder name without parent path
        current_name = Path(current_folder_path).name
        return current_name != standard_foldername


# Initialize configuration with Redis enabled by default when available
config = Config(use_redis=True)