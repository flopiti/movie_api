#!/usr/bin/env python3
"""
Configuration management for the movie management system.
Handles Redis and local JSON configuration storage.
"""

import os
import json
import logging
import time
import subprocess
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """Manages the application configuration including movie file paths using Redis storage."""
    
    def __init__(self, config_file: str = None, use_redis: bool = True, redis_client=None):
        self.config_file = config_file or os.path.expanduser("~/movie-config/config.json")
        self.use_redis = use_redis and redis_client is not None
        self.redis_client = redis_client
        
        # Always initialize local data for fallback purposes
        self.data = self._load_local_config()
        
        # Initialize default SMS templates if none exist
        self._initialize_default_sms_templates()
        
        if not self.use_redis:
            logger.info(f"Using local JSON config at: {self.config_file}")
        else:
            logger.info(f"Using Redis config with local fallback at: {self.config_file}")
    
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
            "tmdb_api_key": os.getenv('TMDB_API_KEY', ''),
            "radarr_url": "http://192.168.0.10:7878",
            "radarr_api_key": "",
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
            logger.info("🔍 Executing Redis command: redis_client.get('movie_config')")
            data = self.redis_client.get('movie_config')
            logger.info(f"🔍 Redis GET result: {type(data)} - {'None' if data is None else f'{len(data)} characters'}")
            
            if data is None:
                logger.info("🔍 Redis data is None, initializing with default data")
                # Initialize Redis with default data
                default_data = {
                    "movie_file_paths": [],
                    "media_paths": [],
                    "download_paths": [],
                    "tmdb_api_key": os.getenv('TMDB_API_KEY', ''),
                    "radarr_url": "http://192.168.0.10:7878",
                    "radarr_api_key": "",
                    "movie_assignments": {}
                }
                logger.info(f"🔍 Setting default data to Redis: {list(default_data.keys())}")
                self.redis_client.set('movie_config', json.dumps(default_data))
                logger.info("🔍 Default data successfully set in Redis")
                return default_data
            
            logger.info("🔍 Parsing JSON data from Redis")
            parsed_data = json.loads(data)
            logger.info(f"🔍 Parsed data keys: {list(parsed_data.keys())}")
            if 'movie_file_paths' in parsed_data:
                logger.info(f"🔍 Found {len(parsed_data['movie_file_paths'])} movie file paths in Redis data")
            return parsed_data
        except Exception as e:
            logger.error(f"Failed to get Redis data: {str(e)}")
            raise Exception(f"Failed to get Redis configuration: {str(e)}")
    
    def _save_redis_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to Redis."""
        try:
            logger.info(f"🔥 Redis data keys: {list(data.keys())}")
            if 'movie_assignments' in data:
                logger.info(f"🔥 Movie assignments count: {len(data['movie_assignments'])}")
            
            self.redis_client.set('movie_config', json.dumps(data))
            logger.info("🔥 Redis data saved successfully!")
        except Exception as e:
            logger.error(f"🔥 Redis save failed: {str(e)}")
            logger.error(f"🔥 Exception type: {type(e).__name__}")
            raise Exception(f"Failed to save Redis configuration: {str(e)}")
    
    def get_movie_paths(self) -> List[str]:
        """Get list of movie file paths."""
        logger.info(f"🎬 get_movie_paths() called - use_redis: {self.use_redis}")
        
        if self.use_redis:
            try:
                logger.info("🎬 Using Redis to get movie paths")
                data = self._get_redis_data()
                movie_paths = data.get("movie_file_paths", [])
                logger.info(f"🎬 Retrieved {len(movie_paths)} movie paths from Redis")
                if movie_paths:
                    logger.info(f"🎬 First few paths: {movie_paths[:3]}")
                return movie_paths
            except Exception as e:
                logger.error(f"Redis error, falling back to local config: {str(e)}")
                fallback_paths = self.data.get("movie_file_paths", [])
                logger.info(f"🎬 Fallback: Retrieved {len(fallback_paths)} movie paths from local config")
                return fallback_paths
        else:
            logger.info("🎬 Using local config to get movie paths")
            local_paths = self.data.get("movie_file_paths", [])
            logger.info(f"🎬 Retrieved {len(local_paths)} movie paths from local config")
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
                    logger.info(f"Added path to Redis: {path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Redis error when adding path, falling back to local: {str(e)}")
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
                    logger.info(f"Removed path from Redis: {path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Redis error when removing path, falling back to local: {str(e)}")
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
                logger.info(f"📚 Retrieved {len(assignments)} assignments from Redis")
                logger.debug(f"📚 Assignment keys: {list(assignments.keys())}")
                return assignments
            except Exception as e:
                logger.error(f"Redis error, falling back to local config: {str(e)}")
                return self.data.get("movie_assignments", {})
        else:
            return self.data.get("movie_assignments", {})
    
    def assign_movie_to_file(self, file_path: str, movie_data: Dict[str, Any]) -> bool:
        """Assign a movie to a file."""
        logger.info(f"🎬 ASSIGN MOVIE: {movie_data.get('title', 'Unknown')} -> {file_path}")
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                assignments = data.setdefault("movie_assignments", {})
                assignments[file_path] = movie_data
                self._save_redis_data(data)
                logger.info(f"✅ Movie assigned to Redis: {movie_data.get('title', 'Unknown')}")
                return True
                
            except Exception as e:
                logger.error(f"Redis assignment failed, falling back to local: {str(e)}")
                # Fallback to local storage
                assignments = self.data.setdefault("movie_assignments", {})
                assignments[file_path] = movie_data
                self._save_local_config()
                logger.info(f"✅ Movie assigned to local storage: {movie_data.get('title', 'Unknown')}")
                return True
        else:
            assignments = self.data.setdefault("movie_assignments", {})
            assignments[file_path] = movie_data
            self._save_local_config()
            logger.info(f"✅ Movie assigned to local storage: {movie_data.get('title', 'Unknown')}")
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
                    logger.info(f"Removed movie assignment for file: {file_path}")
                    return True
                else:
                    logger.debug(f"Assignment not found in Redis for: {file_path}")
                    return False
            except Exception as e:
                logger.error(f"Redis error when removing assignment, falling back to local: {str(e)}")
                # Fallback to local storage
                assignments = self.data.get("movie_assignments", {})
                if file_path in assignments:
                    del assignments[file_path]
                    self._save_local_config()
                    logger.info(f"Removed movie assignment from local storage for file: {file_path}")
                    return True
                else:
                    logger.debug(f"Assignment not found in local storage for: {file_path}")
                    return False
        else:
            assignments = self.data.get("movie_assignments", {})
            if file_path in assignments:
                del assignments[file_path]
                self._save_local_config()
                logger.info(f"Removed movie assignment from local storage for file: {file_path}")
                return True
            else:
                logger.debug(f"Assignment not found in local storage for: {file_path}")
                return False

    def batch_update_assignments(self, updates: List[tuple]) -> bool:
        """Batch update movie assignments to reduce Redis calls.
        
        Args:
            updates: List of (old_path, new_path, movie_data) tuples
        """
        if not updates:
            return True
            
        logger.info(f"🔄 Batch updating {len(updates)} assignments")
        
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
                logger.info(f"✅ Batch update completed: {len(updates)} assignments")
                return True
                
            except Exception as e:
                logger.error(f"Redis batch update failed: {str(e)}")
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
            logger.info(f"✅ Local batch update completed: {len(updates)} assignments")
            return True

    def get_media_paths(self) -> List[Dict[str, Any]]:
        """Get list of media paths with space information."""
        if self.use_redis:
            try:
                data = self._get_redis_data()
                paths = data.get("media_paths", [])
            except Exception as e:
                logger.error(f"Redis error, falling back to local config: {str(e)}")
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
                logger.info(f"Added media path to Redis: {path}")
                return True
            except Exception as e:
                logger.error(f"Redis error when adding media path, falling back to local: {str(e)}")
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
                    logger.info(f"Removed media path from Redis: {path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Redis error when removing media path, falling back to local: {str(e)}")
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
                        logger.info(f"Refreshed space info for media path: {path}")
                        return updated_info
                return {}
            except Exception as e:
                logger.error(f"Redis error when refreshing media path space: {str(e)}")
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
                logger.info(f"Refreshed space info for {len(updated_paths)} media paths")
            except Exception as e:
                logger.error(f"Redis error when refreshing all media paths: {str(e)}")
        else:
            self.data['media_paths'] = updated_paths
            self._save_local_config()
        
        return updated_paths
    
    def get_download_paths(self) -> List[str]:
        """Get list of download paths."""
        logger.info(f"📥 get_download_paths() called - use_redis: {self.use_redis}")
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                if data:
                    logger.info("📥 Using Redis to get download paths")
                    download_paths = data.get("download_paths", [])
                    logger.info(f"📥 Retrieved {len(download_paths)} download paths from Redis")
                    if download_paths:
                        logger.info(f"📥 First few paths: {download_paths[:3]}")
                    return download_paths
                else:
                    fallback_paths = self.data.get("download_paths", [])
                    logger.info(f"📥 Fallback: Retrieved {len(fallback_paths)} download paths from local config")
                    return fallback_paths
            except Exception as e:
                logger.error(f"Redis error when getting download paths, falling back to local: {str(e)}")
                logger.info("📥 Using local config to get download paths")
                local_paths = self.data.get("download_paths", [])
                logger.info(f"📥 Retrieved {len(local_paths)} download paths from local config")
                return local_paths
        else:
            logger.info("📥 Using local config to get download paths")
            local_paths = self.data.get("download_paths", [])
            logger.info(f"📥 Retrieved {len(local_paths)} download paths from local config")
            return local_paths

    def add_download_path(self, path: str) -> bool:
        """Add a download path if it doesn't already exist."""
        logger.info(f"📥 Adding download path: {path}")
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                if data:
                    paths = data.setdefault("download_paths", [])
                    if path not in paths:
                        paths.append(path)
                        self._save_redis_data(data)
                        logger.info(f"Added download path to Redis: {path}")
                        return True
                    else:
                        logger.info(f"Download path already exists in Redis: {path}")
                        return False
                else:
                    logger.error("Redis error when adding download path, falling back to local")
                    paths = self.data.setdefault("download_paths", [])
                    if path not in paths:
                        paths.append(path)
                        self._save_local_config()
                        logger.info(f"Added download path to local config: {path}")
                        return True
                    else:
                        logger.info(f"Download path already exists in local config: {path}")
                        return False
            except Exception as e:
                logger.error(f"Redis error when adding download path, falling back to local: {str(e)}")
                paths = self.data.setdefault("download_paths", [])
                if path not in paths:
                    paths.append(path)
                    self._save_local_config()
                    logger.info(f"Added download path to local config: {path}")
                    return True
                else:
                    logger.info(f"Download path already exists in local config: {path}")
                    return False
        else:
            paths = self.data.setdefault("download_paths", [])
            if path not in paths:
                paths.append(path)
                self._save_local_config()
                logger.info(f"Added download path to local config: {path}")
                return True
            else:
                logger.info(f"Download path already exists in local config: {path}")
                return False

    def remove_download_path(self, path: str) -> bool:
        """Remove a download path."""
        logger.info(f"📥 Removing download path: {path}")
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                if data:
                    paths = data.get("download_paths", [])
                    if path in paths:
                        paths.remove(path)
                        self._save_redis_data(data)
                        logger.info(f"Removed download path from Redis: {path}")
                        return True
                    else:
                        logger.info(f"Download path not found in Redis: {path}")
                        return False
                else:
                    logger.error("Redis error when removing download path, falling back to local")
                    paths = self.data.get("download_paths", [])
                    if path in paths:
                        paths.remove(path)
                        self._save_local_config()
                        logger.info(f"Removed download path from local config: {path}")
                        return True
                    else:
                        logger.info(f"Download path not found in local config: {path}")
                        return False
            except Exception as e:
                logger.error(f"Redis error when removing download path, falling back to local: {str(e)}")
                paths = self.data.get("download_paths", [])
                if path in paths:
                    paths.remove(path)
                    self._save_local_config()
                    logger.info(f"Removed download path from local config: {path}")
                    return True
                else:
                    logger.info(f"Download path not found in local config: {path}")
                    return False
        else:
            paths = self.data.get("download_paths", [])
            if path in paths:
                paths.remove(path)
                self._save_local_config()
                logger.info(f"Removed download path from local config: {path}")
                return True
            else:
                logger.info(f"Download path not found in local config: {path}")
                return False

    def get_download_path_contents(self, path: str) -> Dict[str, Any]:
        """Get contents of a download path (folders and files)."""
        logger.info(f"📥 Getting contents of download path: {path}")
        
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
                        logger.warning(f"Could not get info for folder {item_path}: {str(e)}")
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
                        logger.warning(f"Could not get info for file {item_path}: {str(e)}")
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
            logger.error(f"Error getting download path contents for {path}: {str(e)}")
            return {
                'path': path,
                'exists': False,
                'folders': [],
                'files': [],
                'error': str(e)
            }

    def _is_media_file(self, file_path: Path) -> bool:
        """Check if a file is a media file based on its extension."""
        media_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
            '.mpg', '.mpeg', '.3gp', '.asf', '.rm', '.rmvb', '.vob', '.ts'
        }
        return file_path.suffix.lower() in media_extensions

    def get_radarr_client(self):
        """Get Radarr client instance."""
        try:
            from radarr_client import RadarrClient
            radarr_url = self.data.get('radarr_url', 'http://192.168.0.10:7878')
            radarr_api_key = self.data.get('radarr_api_key', '')
            
            if not radarr_api_key:
                logger.warning("Radarr API key not configured")
                return None
                
            return RadarrClient(radarr_url, radarr_api_key)
        except ImportError as e:
            logger.error(f"Failed to import RadarrClient: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Failed to create RadarrClient: {str(e)}")
            return None

    def get_download_files(self) -> List[Dict[str, Any]]:
        """Get all media files from download paths (flattened, no folders)."""
        logger.info("📥 Getting download files from all download paths")
        
        all_files = []
        download_paths = self.get_download_paths()
        
        if not download_paths:
            logger.info("📥 No download paths configured")
            return all_files
        
        for path in download_paths:
            try:
                if not os.path.exists(path) or not os.path.isdir(path):
                    logger.warning(f"📥 Download path does not exist or is not a directory: {path}")
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
                                logger.warning(f"Could not get info for file {file_path}: {str(e)}")
                                continue
                                
            except Exception as e:
                logger.error(f"Error processing download path {path}: {str(e)}")
                continue
        
        # Sort by name for consistent ordering
        all_files.sort(key=lambda x: x['name'].lower())
        
        logger.info(f"📥 Found {len(all_files)} media files in download paths")
        return all_files

    def search_radarr_movies(self, query: str) -> List[Dict[str, Any]]:
        """Search for movies using Radarr API."""
        logger.info(f"🔍 Searching Radarr for: {query}")
        
        radarr_client = self.get_radarr_client()
        if not radarr_client:
            logger.error("Radarr client not available")
            return []
        
        try:
            # Test connection first
            if not radarr_client.test_connection():
                logger.error("Radarr connection failed")
                return []
            
            # Search for movies
            movies = radarr_client.search_movies(query)
            logger.info(f"🔍 Found {len(movies)} movies in Radarr")
            return movies
            
        except Exception as e:
            logger.error(f"Error searching Radarr: {str(e)}")
            return []

    def _generate_filename_info(self, movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Generate filename information for a movie."""
        # This would be implemented based on the FilenameFormatter logic
        return {
            'standard_filename': f"{movie_data.get('title', 'Unknown')}_{movie_data.get('year', '')}.{Path(file_path).suffix[1:]}",
            'should_rename': True
        }

    def _generate_folder_info(self, movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Generate folder information for a movie."""
        # This would be implemented based on the FilenameFormatter logic
        return {
            'standard_foldername': f"{movie_data.get('title', 'Unknown')} ({movie_data.get('year', '')})",
            'should_rename': True
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
            logger.info(f"Getting space info for {path}")
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
            
            logger.info(f"df output for {path}: {data_line[1]}K total, {data_line[2]}K used, {data_line[3]}K free")
            logger.info(f"Calculated space for {path}: total={total/(1024**3):.2f}GB, used={used/(1024**3):.2f}GB, free={free/(1024**3):.2f}GB")
            
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
            logger.error(f"Error getting space info for path {path}: {str(e)}")
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
                logger.error(f"Redis error, falling back to local config: {str(e)}")
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
                logger.info(f"Added SMS reply template to Redis: {template_data['name']}")
                return True
            except Exception as e:
                logger.error(f"Redis error when adding template, falling back to local: {str(e)}")
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
                        logger.info(f"Updated SMS reply template in Redis: {updated_template['name']}")
                        return True
                return False
            except Exception as e:
                logger.error(f"Redis error when updating template, falling back to local: {str(e)}")
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
                        logger.info(f"Deleted SMS reply template from Redis: {template_id}")
                        return True
                return False
            except Exception as e:
                logger.error(f"Redis error when deleting template, falling back to local: {str(e)}")
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
            "openai_enabled": False,
            "openai_system_prompt": "You are a helpful assistant responding to SMS messages. Keep responses concise and friendly."
        }
        
        if self.use_redis:
            try:
                data = self._get_redis_data()
                settings = data.get("sms_reply_settings", default_settings)
                return settings
            except Exception as e:
                logger.error(f"Redis error, falling back to local config: {str(e)}")
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
                logger.info("Updated SMS reply settings in Redis")
                return True
            except Exception as e:
                logger.error(f"Redis error when updating settings, falling back to local: {str(e)}")
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
