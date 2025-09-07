#!/usr/bin/env python3
"""
Movie Management REST API
A Flask-based REST API for managing movie file paths and discovering media files,
with TMDB API integration for movie metadata.
"""

import os
import json
import logging
import base64
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, db
from plex_client import PlexClient

# Load environment variables (fallback for local development)
load_dotenv('env')

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('movie_api.log'),
        logging.StreamHandler()
    ]
    
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_FILE = os.path.expanduser("~/movie-config/config.json")
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', '')
FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL', '')

# Initialize Firebase
firebase_app = None
logger.info(f"Firebase credentials path: {FIREBASE_CREDENTIALS_PATH}")
logger.info(f"Firebase database URL: {FIREBASE_DATABASE_URL}")

if FIREBASE_CREDENTIALS_PATH and FIREBASE_DATABASE_URL:
    try:
        if os.path.exists(FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_app = firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DATABASE_URL
            })
            logger.info("Firebase initialized successfully")
        else:
            
            logger.warning(f"Firebase credentials file not found at: {FIREBASE_CREDENTIALS_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
else:
    logger.warning("Firebase credentials or database URL not configured")

# Supported media file extensions
MEDIA_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.asf', '.rm', '.rmvb', '.vob', '.ts'
}

class Config:
    """Manages the application configuration including movie file paths using local JSON storage."""
    
    @staticmethod
    def _encode_path_for_firebase(path: str) -> str:
        """Encode file path to be safe for Firebase keys."""
        return base64.urlsafe_b64encode(path.encode('utf-8')).decode('ascii')
    
    @staticmethod
    def _decode_path_from_firebase(encoded_path: str) -> str:
        """Decode Firebase key back to file path."""
        return base64.urlsafe_b64decode(encoded_path.encode('ascii')).decode('utf-8')
    
    def __init__(self, config_file: str = CONFIG_FILE, use_firebase: bool = True):
        self.config_file = config_file
        self.use_firebase = use_firebase and firebase_app is not None
        self.firebase_ref = db.reference('movie_config') if self.use_firebase else None
        
        # Always initialize local data for fallback purposes
        self.data = self._load_local_config()
        
        if not self.use_firebase:
            logger.info(f"Using local JSON config at: {self.config_file}")
        else:
            logger.info(f"Using Firebase config with local fallback at: {self.config_file}")
    
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
            "tmdb_api_key": TMDB_API_KEY,
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
    
    def _get_firebase_data(self) -> Dict[str, Any]:
        """Get configuration data from Firebase."""
        try:
            data = self.firebase_ref.get()
            if data is None:
                # Initialize Firebase with default data
                default_data = {
                    "movie_file_paths": [],
                    "media_paths": [],
                    "tmdb_api_key": TMDB_API_KEY,
                    "movie_assignments": {}  # CRITICAL: This was missing!
                }
                self.firebase_ref.set(default_data)
                return default_data
            return data
        except Exception as e:
            logger.error(f"Failed to get Firebase data: {str(e)}")
            raise Exception(f"Failed to get Firebase configuration: {str(e)}")
    
    def _save_firebase_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to Firebase."""
        try:
            logger.info(f"🔥 Firebase ref path: {self.firebase_ref.path if self.firebase_ref else 'None'}")
            logger.info(f"🔥 Data to save keys: {list(data.keys())}")
            if 'movie_assignments' in data:
                logger.info(f"🔥 Movie assignments count: {len(data['movie_assignments'])}")
                # Removed verbose logging of assignment file paths to reduce log clutter
            
            self.firebase_ref.set(data)
            logger.info("🔥 Firebase ref.set() completed successfully!")
        except Exception as e:
            logger.error(f"🔥 Firebase ref.set() failed: {str(e)}")
            logger.error(f"🔥 Exception type: {type(e).__name__}")
            raise Exception(f"Failed to save Firebase configuration: {str(e)}")
    
    def get_movie_paths(self) -> List[str]:
        """Get list of movie file paths."""
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                return data.get("movie_file_paths", [])
            except Exception as e:
                logger.error(f"Firebase error, falling back to local config: {str(e)}")
                return self.data.get("movie_file_paths", [])
        else:
            return self.data.get("movie_file_paths", [])
    
    def add_movie_path(self, path: str) -> bool:
        """Add a movie file path if it doesn't already exist."""
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                paths = data.setdefault("movie_file_paths", [])
                if path not in paths:
                    paths.append(path)
                    self._save_firebase_data(data)
                    logger.info(f"Added path to Firebase: {path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Firebase error when adding path, falling back to local: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                paths = data.get("movie_file_paths", [])
                if path in paths:
                    paths.remove(path)
                    self._save_firebase_data(data)
                    logger.info(f"Removed path from Firebase: {path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Firebase error when removing path, falling back to local: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                encoded_assignments = data.get("movie_assignments", {})
                
                # Decode Firebase keys back to original file paths
                decoded_assignments = {}
                for encoded_path, movie_data in encoded_assignments.items():
                    try:
                        # Try to decode - if it fails, assume it's already a plain path (backward compatibility)
                        original_path = movie_data.get('original_path') or self._decode_path_from_firebase(encoded_path)
                        decoded_assignments[original_path] = movie_data
                        logger.debug(f"🔍 Decoded: {encoded_path} -> {original_path}")
                    except Exception as decode_e:
                        logger.warning(f"Failed to decode path {encoded_path}, using as-is: {str(decode_e)}")
                        decoded_assignments[encoded_path] = movie_data
                logger.info(f"📚 Decoded {len(decoded_assignments)} assignments from Firebase")
                logger.debug(f"📚 Assignment keys: {list(decoded_assignments.keys())}")
                return decoded_assignments
            except Exception as e:
                logger.error(f"Firebase error, falling back to local config: {str(e)}")
                return self.data.get("movie_assignments", {})
        else:
            return self.data.get("movie_assignments", {})
    
    def assign_movie_to_file(self, file_path: str, movie_data: Dict[str, Any]) -> bool:
        """Assign a movie to a file."""
        logger.info(f"🎬 ASSIGN MOVIE: {movie_data.get('title', 'Unknown')} -> {file_path}")
        
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                assignments = data.setdefault("movie_assignments", {})
                
                # Encode file path for Firebase (Firebase keys can't contain / . etc.)
                encoded_path = self._encode_path_for_firebase(file_path)
                
                assignments[encoded_path] = {**movie_data, 'original_path': file_path}
                
                self._save_firebase_data(data)
                logger.info(f"✅ Movie assigned to Firebase: {movie_data.get('title', 'Unknown')}")
                return True
                
            except Exception as e:
                logger.error(f"Firebase assignment failed, falling back to local: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                assignments = data.get("movie_assignments", {})
                
                # For Firebase, we need to encode the file path to match the stored key
                encoded_path = self._encode_path_for_firebase(file_path)
                
                if encoded_path in assignments:
                    del assignments[encoded_path]
                    self._save_firebase_data(data)
                    # Also update local data to keep it in sync
                    self.data["movie_assignments"] = data.get("movie_assignments", {})
                    logger.info(f"Removed movie assignment for file: {file_path}")
                    return True
                else:
                    logger.debug(f"Assignment not found in Firebase for: {file_path}")
                    return False
            except Exception as e:
                logger.error(f"Firebase error when removing assignment, falling back to local: {str(e)}")
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
        """Batch update movie assignments to reduce Firebase calls.
        
        Args:
            updates: List of (old_path, new_path, movie_data) tuples
        """
        if not updates:
            return True
            
        logger.info(f"🔄 Batch updating {len(updates)} assignments")
        
        if self.use_firebase:
            try:
                # Get all current data once
                data = self._get_firebase_data()
                assignments = data.setdefault("movie_assignments", {})
                
                # Process all updates in memory
                for old_path, new_path, movie_data in updates:
                    # Remove old assignment
                    if old_path:
                        encoded_old_path = self._encode_path_for_firebase(old_path)
                        if encoded_old_path in assignments:
                            del assignments[encoded_old_path]
                    
                    # Add new assignment
                    if new_path and movie_data:
                        encoded_new_path = self._encode_path_for_firebase(new_path)
                        assignments[encoded_new_path] = {**movie_data, 'original_path': new_path}
                
                # Save all changes at once
                self._save_firebase_data(data)
                logger.info(f"✅ Batch update completed: {len(updates)} assignments")
                return True
                
            except Exception as e:
                logger.error(f"Firebase batch update failed: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                return data.get("media_paths", [])
            except Exception as e:
                logger.error(f"Firebase error, falling back to local config: {str(e)}")
                return self.data.get("media_paths", [])
        else:
            return self.data.get("media_paths", [])
    
    def add_media_path(self, path: str) -> bool:
        """Add a media path if it doesn't already exist."""
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                paths = data.setdefault("media_paths", [])
                
                # Check if path already exists
                if any(p.get('path') == path for p in paths):
                    return False
                
                # Add new path with space information
                new_path_info = self._get_path_space_info(path)
                paths.append(new_path_info)
                self._save_firebase_data(data)
                logger.info(f"Added media path to Firebase: {path}")
                return True
            except Exception as e:
                logger.error(f"Firebase error when adding media path, falling back to local: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                paths = data.get("media_paths", [])
                original_length = len(paths)
                paths[:] = [p for p in paths if p.get('path') != path]
                if len(paths) < original_length:
                    self._save_firebase_data(data)
                    logger.info(f"Removed media path from Firebase: {path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Firebase error when removing media path, falling back to local: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                paths = data.get("media_paths", [])
                for path_info in paths:
                    if path_info.get('path') == path:
                        updated_info = self._get_path_space_info(path)
                        path_info.update(updated_info)
                        self._save_firebase_data(data)
                        logger.info(f"Refreshed space info for media path: {path}")
                        return updated_info
                return {}
            except Exception as e:
                logger.error(f"Firebase error when refreshing media path space: {str(e)}")
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
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                data['media_paths'] = updated_paths
                self._save_firebase_data(data)
                logger.info(f"Refreshed space info for {len(updated_paths)} media paths")
            except Exception as e:
                logger.error(f"Firebase error when refreshing all media paths: {str(e)}")
        else:
            self.data['media_paths'] = updated_paths
            self._save_local_config()
        
        return updated_paths
    
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
            
            # Use os.statvfs to get accurate disk usage for mount points
            stat = os.statvfs(path)
            logger.info(f"statvfs for {path}: f_blocks={stat.f_blocks}, f_frsize={stat.f_frsize}, f_bavail={stat.f_bavail}")
            
            # statvfs returns values in blocks, multiply by block size to get bytes
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            
            logger.info(f"Calculated: total={total}, used={used}, free={free}")
            
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

# Initialize configuration with Firebase enabled by default when available
config = Config(use_firebase=True)

class FileDiscovery:
    """Handles recursive file discovery in movie directories."""
    
    @staticmethod
    def is_media_file(file_path: Path) -> bool:
        """Check if a file is a media file based on its extension."""
        return file_path.suffix.lower() in MEDIA_EXTENSIONS
    
    @staticmethod
    def discover_files(root_path: str, movie_assignments: Dict[str, Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recursively discover all media files in a directory."""
        files = []
        root = Path(root_path)
        
        if not root.exists():
            return files
        
        if movie_assignments is None:
            movie_assignments = {}
        
        try:
            for file_path in root.rglob('*'):
                if file_path.is_file() and FileDiscovery.is_media_file(file_path):
                    file_path_str = str(file_path)
                    file_info = {
                        'path': file_path_str,
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime,
                        'directory': str(file_path.parent)
                    }
                    
                    # Add movie assignment if it exists
                    if file_path_str in movie_assignments:
                        movie_data = movie_assignments[file_path_str]
                        file_info['movie'] = movie_data
                        logger.info(f"🎬 Found assignment for {file_path_str}: {movie_data.get('title', 'Unknown')}")
                        
                        # Add filename information for existing assignments
                        standard_filename = FilenameFormatter.generate_standard_filename(movie_data, file_path_str)
                        current_filename = file_path.name
                        needs_rename = FilenameFormatter.should_rename_file(file_path_str, standard_filename)
                        
                        # Add folder information for existing assignments
                        current_folder_path = str(file_path.parent)
                        standard_foldername = FilenameFormatter.generate_standard_foldername(movie_data)
                        folder_needs_rename = FilenameFormatter.should_rename_folder(current_folder_path, standard_foldername)
                        current_foldername = file_path.parent.name
                        
                        file_info['filenameInfo'] = {
                            'current_filename': current_filename,
                            'standard_filename': standard_filename,
                            'needs_rename': needs_rename
                        }
                        
                        file_info['folderInfo'] = {
                            'current_foldername': current_foldername,
                            'current_folder_path': current_folder_path,
                            'standard_foldername': standard_foldername,
                            'needs_rename': folder_needs_rename
                        }
                        
                        logger.info(f"📁 Added folder info: {current_foldername} -> {standard_foldername}, needs rename: {folder_needs_rename}")
                        logger.info(f"🎬 Added filename info for existing assignment: {file_path_str}")
                        logger.info(f"📝 Current: {current_filename}, Standard: {standard_filename}, Needs rename: {needs_rename}")
                    else:
                        logger.debug(f"📂 No assignment found for: {file_path_str}")
                        # Debug: Check if this is a path normalization issue
                        if movie_assignments:
                            sample_key = list(movie_assignments.keys())[0]
                            logger.debug(f"📂 Sample assignment key: '{sample_key}' vs file path: '{file_path_str}'")
                            logger.debug(f"📂 Paths match? {file_path_str == sample_key}")
                            logger.debug(f"📂 Paths normalized match? {str(Path(file_path_str).resolve()) == str(Path(sample_key).resolve())}")
                    
                    files.append(file_info)
        except (PermissionError, OSError) as e:
            print(f"Error accessing {root_path}: {str(e)}")
        
        return files

class TMDBClient:
    """TMDB API client for movie metadata."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = TMDB_BASE_URL
    
    def search_movie(self, query: str) -> Dict[str, Any]:
        """Search for a movie by title with aggressive year-aware filtering."""
        if not self.api_key:
            logger.error("TMDB API key not configured")
            return {"error": "TMDB API key not configured"}
        
        # Extract year from query if present
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        target_year = year_match.group(0) if year_match else None
        
        # Clean query by removing the year for base search
        base_query = re.sub(r'\b(19|20)\d{2}\b', '', query).strip()
        
        logger.info(f"Searching for: '{base_query}' with target year: {target_year}")
        
        all_results = []
        
        # Strategy 1: Search with year parameter if we have a target year
        if target_year:
            url = f"{self.base_url}/search/movie"
            year_params = {
                'api_key': self.api_key,
                'query': base_query,
                'year': target_year,
                'language': 'en-US',
                'include_adult': False
            }
            
            try:
                logger.info(f"Strategy 1: Searching with year parameter: '{base_query}' year={target_year}")
                response = requests.get(url, params=year_params)
                response.raise_for_status()
                year_result = response.json()
                
                if year_result.get('results'):
                    # These results are guaranteed to be from the target year
                    for movie in year_result['results']:
                        movie['_search_strategy'] = 'year_parameter'
                        movie['_year_match'] = True
                    all_results.extend(year_result['results'])
                    logger.info(f"Year parameter search found {len(year_result['results'])} results")
            except requests.RequestException as e:
                logger.warning(f"Year parameter search failed: {str(e)}")
        
        # Strategy 2: Search with full query (including year in text)
        url = f"{self.base_url}/search/movie"
        full_params = {
            'api_key': self.api_key,
            'query': query,
            'language': 'en-US',
            'include_adult': False
        }
        
        try:
            logger.info(f"Strategy 2: Searching with full query: '{query}'")
            response = requests.get(url, params=full_params)
            response.raise_for_status()
            full_result = response.json()
            
            if full_result.get('results'):
                for movie in full_result['results']:
                    movie['_search_strategy'] = 'full_query'
                    # Check if this movie matches our target year
                    movie_year = None
                    if movie.get('release_date'):
                        try:
                            movie_year = movie['release_date'].split('-')[0]
                        except (IndexError, ValueError):
                            pass
                    movie['_year_match'] = (movie_year == target_year) if target_year else False
                
                # Only add movies we haven't already found
                existing_ids = {m['id'] for m in all_results}
                new_movies = [m for m in full_result['results'] if m['id'] not in existing_ids]
                all_results.extend(new_movies)
                logger.info(f"Full query search found {len(new_movies)} additional results")
        except requests.RequestException as e:
            logger.error(f"Full query search failed: {str(e)}")
            return {"error": f"TMDB API error: {str(e)}"}
        
        # Strategy 3: If we still don't have enough year matches, try base query only
        if target_year and len([m for m in all_results if m.get('_year_match')]) < 3:
            base_params = {
                'api_key': self.api_key,
                'query': base_query,
                'language': 'en-US',
                'include_adult': False
            }
            
            try:
                logger.info(f"Strategy 3: Fallback search with base query: '{base_query}'")
                response = requests.get(url, params=base_params)
                response.raise_for_status()
                base_result = response.json()
                
                if base_result.get('results'):
                    for movie in base_result['results']:
                        movie['_search_strategy'] = 'base_query'
                        # Check if this movie matches our target year
                        movie_year = None
                        if movie.get('release_date'):
                            try:
                                movie_year = movie['release_date'].split('-')[0]
                            except (IndexError, ValueError):
                                pass
                        movie['_year_match'] = (movie_year == target_year) if target_year else False
                    
                    # Only add movies we haven't already found
                    existing_ids = {m['id'] for m in all_results}
                    new_movies = [m for m in base_result['results'] if m['id'] not in existing_ids]
                    all_results.extend(new_movies)
                    logger.info(f"Base query search found {len(new_movies)} additional results")
            except requests.RequestException as e:
                logger.warning(f"Base query search failed: {str(e)}")
        
        # Sort results: year matches first, then by strategy priority
        if target_year:
            year_matches = [m for m in all_results if m.get('_year_match')]
            other_movies = [m for m in all_results if not m.get('_year_match')]
            
            # Sort year matches by strategy priority
            strategy_priority = {'year_parameter': 1, 'full_query': 2, 'base_query': 3}
            year_matches.sort(key=lambda x: strategy_priority.get(x.get('_search_strategy', 'base_query'), 4))
            
            # Sort other movies by strategy priority
            other_movies.sort(key=lambda x: strategy_priority.get(x.get('_search_strategy', 'base_query'), 4))
            
            final_results = year_matches + other_movies
            logger.info(f"Final results: {len(year_matches)} year matches, {len(other_movies)} other movies")
            if year_matches:
                logger.info(f"Top year match: '{year_matches[0].get('title')}' ({year_matches[0].get('release_date')})")
        else:
            final_results = all_results
        
        # Clean up internal fields
        for movie in final_results:
            movie.pop('_search_strategy', None)
            movie.pop('_year_match', None)
        
        return {
            'results': final_results,
            'total_results': len(final_results),
            'year_matches': len([m for m in all_results if m.get('_year_match')]) if target_year else 0
        }

class FilenameFormatter:
    """Utility class for formatting movie filenames and folder names to standard format."""
    
    @staticmethod
    def generate_standard_filename(movie_data: Dict[str, Any], original_filename: str) -> str:
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
    
    @staticmethod
    def generate_standard_foldername(movie_data: Dict[str, Any]) -> str:
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
    
    @staticmethod
    def should_rename_file(current_filename: str, standard_filename: str) -> bool:
        """Check if the current filename differs from the standard format."""
        # Extract just the filename without path
        current_name = Path(current_filename).name
        return current_name != standard_filename
    
    @staticmethod
    def should_rename_folder(current_folder_path: str, standard_foldername: str) -> bool:
        """Check if the current folder name differs from the standard format."""
        # Extract just the folder name without parent path
        current_name = Path(current_folder_path).name
        return current_name != standard_foldername

class OpenAIClient:
    """OpenAI API client for cleaning movie filenames."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            try:
                # Initialize OpenAI client with explicit parameters to avoid proxy issues
                import httpx
                self.client = OpenAI(
                    api_key=api_key,
                    timeout=30.0,
                    max_retries=2,
                    http_client=httpx.Client()
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {str(e)}")
                logger.info("OpenAI client will be disabled, filename cleaning will be skipped")
                self.client = None
        else:
            logger.info("OpenAI API key not configured, filename cleaning will be disabled")
            self.client = None
    
    def clean_filename(self, filename: str) -> Dict[str, Any]:
        """Clean a movie filename using OpenAI to extract the movie title."""
        if not self.client:
            logger.error("OpenAI API key not configured")
            return {"error": "OpenAI API key not configured", "original_filename": filename}
        
        logger.info(f"Cleaning filename with OpenAI: {filename}")
        
        # Step 1: Initial cleaning
        initial_prompt = f"""
You are a movie filename parser. I will provide you with a movie filename, and you must extract the clean movie title.

IMPORTANT: You must ALWAYS process the filename I give you. Never ask for clarification or more information.

Your goal is to extract ONLY the core movie title for TMDB search purposes. Remove these elements from the filename:
- File extensions (.mp4, .mkv, .avi, etc.)
- Quality indicators like 1080p, 720p, 4K, BluRay, WEBRIP, HDRip, etc.
- Release group tags in brackets like [YIFY], [RARBG], [TGx], [EVO], [FUM]
- Audio/video codec info like x264, x265, AAC, AC3, etc.
- Language indicators like "Eng", "Jps", "Rus", "Ukr", "Multi", "Dual"
- Subtitle information like "Subs", "Subtitles", "Subbed"
- Audio track information like "5.1", "2.0", "DTS", "AC3"
- Content type indicators like "Anime", "Movie", "Film" (unless it's part of the actual title)
- Edition indicators like "Directors Cut", "Extended Cut", "Unrated", "Rated", "Theatrical Cut", "Final Cut"
- Version indicators like "Special Edition", "Collectors Edition", "Anniversary Edition"
- Collection/Label names like "Criterion Collection", "Arrow Video", "Shout Factory", "Kino Lorber", "StudioCanal"
- Extra periods, underscores, and dashes used as separators
- Any other technical metadata

CRITICAL: DO NOT remove or modify:
- Years (e.g., "1999", "2010", "1968") - these are CRUCIAL for finding the correct movie
- Director names (e.g., "by Christopher Nolan", "dir. Spielberg")
- Actor names that are part of the title
- Original movie titles in other languages
- Subtitle information that helps identify the movie
- Movie sequel numbers (e.g., "Cars 2", "Toy Story 3", "The Matrix 2", "Iron Man 2", "Inside Out 2", "Frozen 2", "Finding Dory", "Monsters University")
- Roman numerals in titles (e.g., "Rocky IV", "Star Wars Episode IV")
- ANY numbers that appear to be part of the movie title (e.g., "2", "3", "4", "II", "III", "IV")

Examples:
- "Akira Anime Eng Jps Rus Ukr Multi Subs" → "Akira"
- "The Matrix 1999 1080p BluRay x264" → "The Matrix 1999"
- "Cars 2 (2011) 1080p BluRay x264" → "Cars 2 2011"
- "Toy Story 3 2010 720p WEBRip" → "Toy Story 3 2010"
- "Iron Man 2 2010 BluRay x264" → "Iron Man 2 2010"
- "Inside Out 2 2024 1080p BluRay x264" → "Inside Out 2 2024"
- "Frozen 2 2019 720p WEBRip" → "Frozen 2 2019"
- "Finding Dory 2016 BluRay x264" → "Finding Dory 2016"
- "Monsters University 2013 1080p" → "Monsters University 2013"
- "Certified Copy Criterion Collection 1080p BluRay x264" → "Certified Copy"
- "The Seventh Seal Criterion Collection 1957" → "The Seventh Seal 1957"
- "Inception by Christopher Nolan 2010" → "Inception by Christopher Nolan 2010"
- "Alien Resurrection Directors Cut 1997" → "Alien Resurrection 1997"
- "Blade Runner Final Cut 1982" → "Blade Runner 1982"
- "The Lord of the Rings Extended Edition" → "The Lord of the Rings"
- "Signs of Life 1968" → "Signs of Life 1968"

If you cannot determine a clean movie title, return the filename as-is without the file extension.

Filename to process: {filename}

Extract the clean movie title from this filename:"""

        try:
            # Step 1: Initial cleaning
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a movie filename parser that ALWAYS processes the given filename and extracts ONLY the core movie title for TMDB search. Remove language indicators, subtitle info, edition indicators (Directors Cut, Extended Cut, etc.), and technical metadata. Preserve director names, actor names, CRITICALLY preserve movie sequel numbers (like Cars 2, Toy Story 3, Iron Man 2), and CRUCIALLY preserve YEARS (like 1999, 2010, 1968) which are essential for finding the correct movie. Never ask for clarification."},
                    {"role": "user", "content": initial_prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            initial_cleaned_title = response.choices[0].message.content.strip()
            
            # Check if OpenAI returned a generic response asking for clarification
            if any(phrase in initial_cleaned_title.lower() for phrase in [
                "please provide", "could you provide", "i'm here to help", 
                "can you provide", "need the filename", "missing", "clarification"
            ]):
                # Extract filename without extension as fallback
                import os
                initial_cleaned_title = os.path.splitext(os.path.basename(filename))[0]
                logger.warning(f"OpenAI returned generic response, using filename fallback: '{initial_cleaned_title}'")
            
            logger.info(f"OpenAI initial cleaning: '{filename}' to '{initial_cleaned_title}'")
            
            # Step 2: Check if the result needs further cleaning and ask for alternative
            # Look for patterns that suggest the title still has unwanted elements
            unwanted_patterns = [
                '~', '(', ')', '[', ']', '|', '\\', '/', ':', ';', '=', '+', '*', '?', '<', '>', '"', "'",
                'BluRay', 'x264', 'x265', '1080p', '720p', '4K', 'HDR', 'WEBRIP', 'HDRip', 'BRRip',
                'YIFY', 'RARBG', 'TGx', 'EVO', 'FUM', 'Dual', 'Multi', 'Eng', 'Jps', 'Rus', 'Ukr',
                '5.1', '2.0', 'DTS', 'AC3', 'AAC', 'Subs', 'Subbed', 'Subtitles',
                'Criterion Collection', 'Arrow Video', 'Shout Factory', 'Kino Lorber', 'StudioCanal'
            ]
            
            needs_further_cleaning = any(pattern in initial_cleaned_title for pattern in unwanted_patterns)
            
            if needs_further_cleaning:
                logger.info(f"Initial cleaning still contains unwanted elements, asking for alternative: '{initial_cleaned_title}'")
                
                # Step 2: Ask for alternative cleaner version
                alternative_prompt = f"""
The previous cleaning of this filename still contains unwanted elements. Please provide a cleaner alternative version.

Original filename: {filename}
Previous cleaning result: {initial_cleaned_title}

Please provide a cleaner version that removes ALL of these elements:
- Any text after ~ (tilde)
- Any text in parentheses or brackets
- Any quality indicators (BluRay, x264, 1080p, etc.)
- Any release group names
- Any audio/video codec information
- Any language indicators
- Any subtitle information
- Any audio track information
- Any collection/label names (Criterion Collection, Arrow Video, Shout Factory, etc.)
- Any special characters like ~, |, \\, /, etc.

CRITICAL: Preserve movie sequel numbers, Roman numerals in titles, and YEARS (e.g., "Cars 2", "Toy Story 3", "Iron Man 2", "Inside Out 2", "Frozen 2", "Finding Dory", "Monsters University", "Rocky IV", "1999", "2010", "1968")

Focus ONLY on the core movie title. If you're unsure about a word, remove it.

Examples of what to remove:
- "Cars 2 ~Invincible" → "Cars 2"
- "Cars 2 (2011) 1080p BluRay x264" → "Cars 2 2011"
- "Toy Story 3 2010 720p WEBRip" → "Toy Story 3 2010"
- "Inside Out 2 2024 1080p BluRay x264" → "Inside Out 2 2024"
- "Frozen 2 2019 720p WEBRip" → "Frozen 2 2019"
- "Finding Dory 2016 BluRay x264" → "Finding Dory 2016"
- "Monsters University 2013 1080p" → "Monsters University 2013"
- "Certified Copy Criterion Collection 1080p BluRay x264" → "Certified Copy"
- "The Matrix (1999) [YIFY]" → "The Matrix 1999"
- "Inception 1080p BluRay x264" → "Inception"
- "Signs of Life 1968" → "Signs of Life 1968"

Provide ONLY the clean movie title:"""

                alternative_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a movie title cleaner. Remove ALL unwanted elements and provide ONLY the core movie title. Be aggressive in removing uncertain elements, but CRITICALLY preserve movie sequel numbers (like Cars 2, Toy Story 3, Iron Man 2), Roman numerals in titles, and YEARS (like 1999, 2010, 1968) which are crucial for finding the correct movie."},
                        {"role": "user", "content": alternative_prompt}
                    ],
                    max_tokens=50,
                    temperature=0.1
                )
                
                final_cleaned_title = alternative_response.choices[0].message.content.strip()
                logger.info(f"OpenAI alternative cleaning: '{initial_cleaned_title}' to '{final_cleaned_title}'")
                
                return {
                    "cleaned_title": final_cleaned_title,
                    "original_filename": filename,
                    "initial_cleaning": initial_cleaned_title,
                    "alternative_cleaning": final_cleaned_title,
                    "success": True
                }
            else:
                logger.info(f"OpenAI cleaned '{filename}' to '{initial_cleaned_title}' (no further cleaning needed)")
                return {
                    "cleaned_title": initial_cleaned_title,
                    "original_filename": filename,
                    "success": True
                }
            
        except Exception as e:
            logger.error(f"OpenAI API error for filename '{filename}': {str(e)}")
            return {
                "error": f"OpenAI API error: {str(e)}",
                "original_filename": filename,
                "success": False
            }

# Initialize clients
tmdb_client = TMDBClient(TMDB_API_KEY)
openai_client = OpenAIClient(OPENAI_API_KEY)

# Routes

@app.route('/movie-file-paths', methods=['GET'])
def get_movie_file_paths():
    """Get all configured movie file paths."""
    return jsonify({
        'movie_file_paths': config.get_movie_paths(),
        'count': len(config.get_movie_paths())
    })

@app.route('/movie-file-paths', methods=['PUT'])
def add_movie_file_path():
    """Add a new movie file path."""
    data = request.get_json()
    
    if not data or 'path' not in data:
        return jsonify({'error': 'Path is required'}), 400
    
    path = data['path'].strip()
    if not path:
        return jsonify({'error': 'Path cannot be empty'}), 400
    
    # Validate that path exists
    if not os.path.exists(path):
        return jsonify({'error': 'Path does not exist'}), 400
    
    if not os.path.isdir(path):
        return jsonify({'error': 'Path must be a directory'}), 400
    
    if config.add_movie_path(path):
        return jsonify({
            'message': 'Path added successfully',
            'path': path,
            'movie_file_paths': config.get_movie_paths()
        }), 201
    else:
        return jsonify({
            'message': 'Path already exists',
            'path': path,
            'movie_file_paths': config.get_movie_paths()
        }), 200

@app.route('/movie-file-paths', methods=['DELETE'])
def remove_movie_file_path():
    """Remove a movie file path."""
    data = request.get_json()
    
    if not data or 'path' not in data:
        return jsonify({'error': 'Path is required'}), 400
    
    path = data['path'].strip()
    if not path:
        return jsonify({'error': 'Path cannot be empty'}), 400
    
    if config.remove_movie_path(path):
        return jsonify({
            'message': 'Path removed successfully',
            'path': path,
            'movie_file_paths': config.get_movie_paths()
        }), 200
    else:
        return jsonify({
            'error': 'Path not found',
            'path': path,
            'movie_file_paths': config.get_movie_paths()
        }), 404

@app.route('/media-paths', methods=['GET'])
def get_media_paths():
    """Get all configured media paths with space information."""
    return jsonify({
        'media_paths': config.get_media_paths(),
        'count': len(config.get_media_paths())
    })

@app.route('/media-paths', methods=['PUT'])
def add_media_path():
    """Add a new media path."""
    data = request.get_json()
    
    if not data or 'path' not in data:
        return jsonify({'error': 'Path is required'}), 400
    
    path = data['path'].strip()
    if not path:
        return jsonify({'error': 'Path cannot be empty'}), 400
    
    # Validate that path exists
    if not os.path.exists(path):
        return jsonify({'error': 'Path does not exist'}), 400
    
    if not os.path.isdir(path):
        return jsonify({'error': 'Path must be a directory'}), 400
    
    if config.add_media_path(path):
        return jsonify({
            'message': 'Media path added successfully',
            'path': path,
            'media_paths': config.get_media_paths()
        }), 201
    else:
        return jsonify({
            'message': 'Media path already exists',
            'path': path,
            'media_paths': config.get_media_paths()
        }), 200

@app.route('/media-paths', methods=['DELETE'])
def remove_media_path():
    """Remove a media path."""
    data = request.get_json()
    
    if not data or 'path' not in data:
        return jsonify({'error': 'Path is required'}), 400
    
    path = data['path'].strip()
    if not path:
        return jsonify({'error': 'Path cannot be empty'}), 400
    
    if config.remove_media_path(path):
        return jsonify({
            'message': 'Media path removed successfully',
            'path': path,
            'media_paths': config.get_media_paths()
        }), 200
    else:
        return jsonify({
            'error': 'Media path not found',
            'path': path,
            'media_paths': config.get_media_paths()
        }), 404

@app.route('/media-paths/refresh', methods=['POST'])
def refresh_media_paths_space():
    """Refresh space information for all media paths or a specific path."""
    try:
        data = request.get_json()
        
        # If a specific path is provided, refresh only that path
        if data and 'path' in data:
            path = data['path']
            updated_info = config.refresh_media_path_space(path)
            if updated_info:
                return jsonify({
                    'message': 'Space information refreshed successfully',
                    'path_info': updated_info
                }), 200
            else:
                return jsonify({
                    'error': 'Media path not found',
                    'path': path
                }), 404
        else:
            # Refresh all paths
            updated_paths = config.refresh_all_media_paths_space()
            return jsonify({
                'message': 'Space information refreshed successfully',
                'media_paths': updated_paths,
                'count': len(updated_paths)
            }), 200
    except Exception as e:
        logger.error(f"Error refreshing media paths space: {str(e)}")
        return jsonify({'error': f'Failed to refresh space information: {str(e)}'}), 500

@app.route('/all-files', methods=['GET'])
def get_all_files():
    """Get all media files from all configured movie paths."""
    all_files = []
    paths = config.get_movie_paths()
    
    if not paths:
        return jsonify({
            'files': [],
            'count': 0,
            'message': 'No movie file paths configured'
        })
    
    # Get movie assignments
    movie_assignments = config.get_movie_assignments()
    logger.info(f"🎬 Loading files with {len(movie_assignments)} movie assignments")
    logger.info(f"🎬 Assignment keys (first 10): {list(movie_assignments.keys())[:10]}")
    
    # Debug: Show some example assignments
    if movie_assignments:
        sample_key = list(movie_assignments.keys())[0]
        sample_assignment = movie_assignments[sample_key]
        logger.info(f"🎬 Sample assignment - Key: '{sample_key}', Movie: {sample_assignment.get('title', 'Unknown')}")
    
    for path in paths:
        files = FileDiscovery.discover_files(path, movie_assignments)
        for file_info in files:
            file_info['source_path'] = path
        all_files.extend(files)
    
    # Sort by name for consistent ordering
    all_files.sort(key=lambda x: x['name'].lower())
    
    return jsonify({
        'files': all_files,
        'count': len(all_files),
        'source_paths': paths
    })

@app.route('/search-movie', methods=['GET'])
def search_movie():
    """Search for movie metadata using OpenAI to clean filename first, then TMDB API."""
    query = request.args.get('q', '').strip()
    
    if not query:
        logger.warning("Search movie request missing query parameter")
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    logger.info(f"Movie search request received for: {query}")
    
    # Step 1: Clean the filename using OpenAI
    openai_result = openai_client.clean_filename(query)
    
    # Prepare the search query - use cleaned title if available, otherwise fallback to original
    if openai_result.get('success') and openai_result.get('cleaned_title'):
        search_query = openai_result['cleaned_title']
        logger.info(f"Using OpenAI cleaned title for TMDB search: {search_query}")
    else:
        search_query = query
        logger.warning(f"OpenAI cleaning failed, using original query for TMDB search: {search_query}")
    
    # Step 2: Search TMDB with the cleaned query
    logger.info(f"Searching TMDB for: {search_query}")
    tmdb_result = tmdb_client.search_movie(search_query)
    
    # Combine results
    response = {
        'openai_processing': openai_result,
        'tmdb_search_query': search_query,
        'tmdb_results': tmdb_result,
        'original_query': query
    }
    
    # Log the results
    if 'results' in tmdb_result and tmdb_result['results']:
        logger.info(f"TMDB search successful. Found {len(tmdb_result['results'])} results for '{search_query}'")
        if tmdb_result['results']:
            top_result = tmdb_result['results'][0]
            logger.info(f"Top result: '{top_result.get('title', 'Unknown')}' ({top_result.get('release_date', 'Unknown year')})")
    else:
        logger.warning(f"TMDB search returned no results for '{search_query}'")
    
    return jsonify(response)

@app.route('/assign-movie', methods=['POST'])
def assign_movie():
    """Assign a movie to a file."""
    data = request.get_json()
    
    if not data or 'file_path' not in data or 'movie' not in data:
        return jsonify({'error': 'file_path and movie are required'}), 400
    
    file_path = data['file_path'].strip()
    movie_data = data['movie']
    
    if not file_path:
        return jsonify({'error': 'file_path cannot be empty'}), 400
    
    # Note: Skipping file existence validation for now to focus on database persistence
    # TODO: Add proper file validation that works across different environments
    
    # Validate movie data has required fields
    if not isinstance(movie_data, dict) or 'title' not in movie_data:
        return jsonify({'error': 'Movie data must include title'}), 400
    
    try:
        if config.assign_movie_to_file(file_path, movie_data):
            # Generate standard filename information
            file_path_obj = Path(file_path)
            standard_filename = FilenameFormatter.generate_standard_filename(movie_data, file_path)
            current_filename = file_path_obj.name
            needs_rename = FilenameFormatter.should_rename_file(file_path, standard_filename)
            
            # Generate standard folder information
            current_folder_path = str(file_path_obj.parent)
            standard_foldername = FilenameFormatter.generate_standard_foldername(movie_data)
            folder_needs_rename = FilenameFormatter.should_rename_folder(current_folder_path, standard_foldername)
            current_foldername = file_path_obj.parent.name
            
            logger.info(f"Successfully assigned movie '{movie_data.get('title')}' to file: {file_path}")
            logger.info(f"📁 Assignment folder info: {current_foldername} -> {standard_foldername}, needs rename: {folder_needs_rename}")
            
            response_data = {
                'message': 'Movie assigned successfully',
                'file_path': file_path,
                'movie': movie_data,
                'filenameInfo': {
                    'current_filename': current_filename,
                    'standard_filename': standard_filename,
                    'needs_rename': needs_rename
                },
                'folderInfo': {
                    'current_foldername': current_foldername,
                    'current_folder_path': current_folder_path,
                    'standard_foldername': standard_foldername,
                    'needs_rename': folder_needs_rename
                }
            }
            
            return jsonify(response_data), 200
        else:
            return jsonify({'error': 'Failed to assign movie'}), 500
    except Exception as e:
        logger.error(f"Error assigning movie: {str(e)}")
        return jsonify({'error': f'Failed to assign movie: {str(e)}'}), 500

@app.route('/remove-movie-assignment', methods=['DELETE'])
def remove_movie_assignment():
    """Remove a movie assignment from a file."""
    data = request.get_json()
    
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path is required'}), 400
    
    file_path = data['file_path'].strip()
    
    if not file_path:
        return jsonify({'error': 'file_path cannot be empty'}), 400
    
    try:
        if config.remove_movie_assignment(file_path):
            logger.info(f"Successfully removed movie assignment for file: {file_path}")
            return jsonify({
                'message': 'Movie assignment removed successfully',
                'file_path': file_path
            }), 200
        else:
            return jsonify({
                'message': 'No movie assignment found for this file',
                'file_path': file_path
            }), 404
    except Exception as e:
        logger.error(f"Error removing movie assignment: {str(e)}")
        return jsonify({'error': f'Failed to remove movie assignment: {str(e)}'}), 500

@app.route('/cleanup-orphaned-assignments', methods=['POST'])
def cleanup_orphaned_assignments():
    """Remove all movie assignments for files that no longer exist."""
    try:
        logger.info("🚀 CLEANUP ENDPOINT CALLED - Starting cleanup of orphaned movie assignments...")
        
        # Get all current movie assignments
        movie_assignments = config.get_movie_assignments()
        logger.info(f"Found {len(movie_assignments)} total movie assignments")
        
        orphaned_assignments = []
        removed_count = 0
        valid_assignments = []
        
        # Check each assignment
        for file_path, movie_data in movie_assignments.items():
            logger.info(f"🔍 Checking assignment: {file_path} -> {movie_data.get('title', 'Unknown')}")
            
            if os.path.exists(file_path):
                logger.info(f"✅ File exists: {file_path}")
                valid_assignments.append({
                    'file_path': file_path,
                    'movie_title': movie_data.get('title', 'Unknown'),
                    'movie_id': movie_data.get('id', 'Unknown')
                })
            else:
                logger.info(f"🚨 Found orphaned assignment: {file_path} -> {movie_data.get('title', 'Unknown')}")
                orphaned_assignments.append({
                    'file_path': file_path,
                    'movie_title': movie_data.get('title', 'Unknown'),
                    'movie_id': movie_data.get('id', 'Unknown')
                })
                
                # Remove the assignment
                try:
                    logger.info(f"🗑️ Attempting to remove orphaned assignment: {file_path} -> {movie_data.get('title', 'Unknown')}")
                    result = config.remove_movie_assignment(file_path)
                    logger.info(f"🗑️ remove_movie_assignment returned: {result}")
                    if result:
                        removed_count += 1
                        logger.info(f"✅ Successfully removed orphaned assignment: {file_path} -> {movie_data.get('title', 'Unknown')}")
                    else:
                        logger.warning(f"⚠️ Assignment not found in database (already removed?): {file_path}")
                except Exception as e:
                    logger.error(f"❌ Error removing orphaned assignment {file_path}: {str(e)}")
        
        logger.info(f"Cleanup completed: {removed_count} orphaned assignments removed out of {len(orphaned_assignments)} found")
        logger.info(f"Valid assignments remaining: {len(valid_assignments)}")
        
        return jsonify({
            'message': 'Cleanup completed successfully',
            'total_assignments_checked': len(movie_assignments),
            'orphaned_assignments_found': len(orphaned_assignments),
            'assignments_removed': removed_count,
            'valid_assignments_remaining': len(valid_assignments),
            'orphaned_assignments': orphaned_assignments,
            'valid_assignments': valid_assignments
        }), 200
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        return jsonify({'error': f'Failed to cleanup orphaned assignments: {str(e)}'}), 500

@app.route('/assigned-movies', methods=['GET'])
def get_assigned_movies():
    """Get all movies that are currently assigned to files."""
    try:
        assignments = config.get_movie_assignments()
        
        logger.info(f"🔍 Debug: Found {len(assignments)} total assignments")
        logger.info(f"🔍 Debug: Assignment keys (first 5): {list(assignments.keys())[:5]}")
        
        # Extract just the movie data from assignments
        assigned_movies = []
        for file_path, movie_data in assignments.items():
            if isinstance(movie_data, dict) and movie_data.get('id'):
                assigned_movies.append({
                    'movie': movie_data,
                    'file_path': file_path
                })
        
        logger.info(f"🔍 Debug: Returning {len(assigned_movies)} valid assigned movies")
        
        return jsonify({
            'assigned_movies': assigned_movies,
            'count': len(assigned_movies)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting assigned movies: {str(e)}")
        return jsonify({'error': f'Failed to get assigned movies: {str(e)}'}), 500

@app.route('/debug-assignments', methods=['GET'])
def debug_assignments():
    """Debug endpoint to check current assignments."""
    try:
        assignments = config.get_movie_assignments()
        logger.info(f"🔍 Debug endpoint: Found {len(assignments)} assignments")
        logger.info(f"🔍 Debug endpoint: Assignment keys: {list(assignments.keys())}")
        
        # Show first few assignments in detail
        debug_info = []
        for i, (file_path, movie_data) in enumerate(assignments.items()):
            if i < 5:  # Only show first 5
                debug_info.append({
                    'file_path': file_path,
                    'movie_title': movie_data.get('title', 'Unknown'),
                    'movie_id': movie_data.get('id'),
                    'movie_data_keys': list(movie_data.keys())
                })
        
        return jsonify({
            'total_assignments': len(assignments),
            'sample_assignments': debug_info,
            'all_keys': list(assignments.keys())
        })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        return jsonify({'error': f'Debug endpoint failed: {str(e)}'})

@app.route('/test-cleanup', methods=['POST'])
def test_cleanup():
    """Test endpoint to manually trigger cleanup and see what happens."""
    try:
        logger.info("🧪 TEST CLEANUP ENDPOINT CALLED")
        
        # Get current assignments
        assignments = config.get_movie_assignments()
        logger.info(f"🧪 Current assignments: {len(assignments)}")
        
        # Find first orphaned assignment
        for file_path, movie_data in assignments.items():
            if not os.path.exists(file_path):
                logger.info(f"🧪 Found orphaned assignment to test: {file_path}")
                
                # Try to remove it
                result = config.remove_movie_assignment(file_path)
                logger.info(f"🧪 Remove result: {result}")
                
                # Check if it was actually removed
                new_assignments = config.get_movie_assignments()
                logger.info(f"🧪 Assignments after removal: {len(new_assignments)}")
                
                return jsonify({
                    'test_file': file_path,
                    'remove_result': result,
                    'assignments_before': len(assignments),
                    'assignments_after': len(new_assignments),
                    'success': result and len(new_assignments) < len(assignments)
                })
        
        return jsonify({'message': 'No orphaned assignments found to test'})
        
    except Exception as e:
        logger.error(f"Error in test cleanup: {str(e)}")
        return jsonify({'error': f'Test cleanup failed: {str(e)}'})



@app.route('/rename-file', methods=['POST'])
def rename_file():
    """Rename a movie file to standard format."""
    data = request.get_json()
    
    if not data or 'file_path' not in data or 'new_filename' not in data:
        return jsonify({'error': 'file_path and new_filename are required'}), 400
    
    current_path = data['file_path'].strip()
    new_filename = data['new_filename'].strip()
    
    if not current_path or not new_filename:
        return jsonify({'error': 'file_path and new_filename cannot be empty'}), 400
    
    try:
        current_file = Path(current_path)
        
        # Validate current file exists
        if not current_file.exists():
            return jsonify({'error': 'File does not exist'}), 404
        
        # Create new path with same directory but new filename
        new_path = current_file.parent / new_filename
        
        # Check if new filename already exists
        if new_path.exists():
            return jsonify({'error': 'A file with the new name already exists'}), 409
        
        # Perform the rename
        current_file.rename(new_path)
        
        # Update movie assignments if they exist - use batch update for better performance
        movie_assignments = config.get_movie_assignments()
        if current_path in movie_assignments:
            movie_data = movie_assignments[current_path]
            # Use batch update instead of individual calls
            config.batch_update_assignments([(current_path, str(new_path), movie_data)])
        
        logger.info(f"Successfully renamed file: {current_path} -> {new_path}")
        
        return jsonify({
            'message': 'File renamed successfully',
            'old_path': current_path,
            'new_path': str(new_path),
            'new_filename': new_filename
        }), 200
        
    except Exception as e:
        logger.error(f"Error renaming file: {str(e)}")
        return jsonify({'error': f'Failed to rename file: {str(e)}'}), 500

@app.route('/rename-folder', methods=['POST'])
def rename_folder():
    """Rename a movie folder to standard format."""
    data = request.get_json()
    
    if not data or 'folder_path' not in data or 'new_foldername' not in data:
        return jsonify({'error': 'folder_path and new_foldername are required'}), 400
    
    current_folder_path = data['folder_path'].strip()
    new_foldername = data['new_foldername'].strip()
    
    if not current_folder_path or not new_foldername:
        return jsonify({'error': 'folder_path and new_foldername cannot be empty'}), 400
    
    try:
        current_folder = Path(current_folder_path)
        
        # Validate current folder exists
        if not current_folder.exists():
            return jsonify({'error': 'Folder does not exist'}), 404
        
        if not current_folder.is_dir():
            return jsonify({'error': 'Path is not a directory'}), 400
        
        # Create new path with same parent but new folder name
        new_folder_path = current_folder.parent / new_foldername
        
        # Check if new folder name already exists
        if new_folder_path.exists():
            return jsonify({'error': 'A folder with the new name already exists'}), 409
        
        # Get all files in the folder that have movie assignments
        movie_assignments = config.get_movie_assignments()
        files_to_update = []
        
        for file_path, movie_data in movie_assignments.items():
            if file_path.startswith(current_folder_path):
                # Calculate the new file path after folder rename
                relative_path = Path(file_path).relative_to(current_folder)
                new_file_path = new_folder_path / relative_path
                files_to_update.append((file_path, str(new_file_path), movie_data))
        
        # Perform the folder rename
        current_folder.rename(new_folder_path)
        
        # Batch update all movie assignments that were in the renamed folder
        if files_to_update:
            config.batch_update_assignments(files_to_update)
        
        logger.info(f"Successfully renamed folder: {current_folder_path} -> {new_folder_path}")
        logger.info(f"Updated {len(files_to_update)} movie assignments")
        
        return jsonify({
            'message': 'Folder renamed successfully',
            'old_path': current_folder_path,
            'new_path': str(new_folder_path),
            'new_foldername': new_foldername,
            'updated_assignments': len(files_to_update)
        }), 200
        
    except Exception as e:
        logger.error(f"Error renaming folder: {str(e)}")
        return jsonify({'error': f'Failed to rename folder: {str(e)}'}), 500

@app.route('/delete-file', methods=['DELETE'])
def delete_file():
    """Delete a movie file from the filesystem."""
    data = request.get_json()
    
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path is required'}), 400
    
    file_path = data['file_path'].strip()
    
    if not file_path:
        return jsonify({'error': 'file_path cannot be empty'}), 400
    
    try:
        file_to_delete = Path(file_path)
        
        # Validate file exists
        if not file_to_delete.exists():
            return jsonify({'error': 'File does not exist'}), 404
        
        # Validate it's actually a file (not a directory)
        if not file_to_delete.is_file():
            return jsonify({'error': 'Path is not a file'}), 400
        
        # Check if it's a media file (safety check)
        if not FileDiscovery.is_media_file(file_to_delete):
            return jsonify({'error': 'File is not a supported media file'}), 400
        
        # Store file info before deletion for response
        file_name = file_to_delete.name
        file_size = file_to_delete.stat().st_size
        
        # Remove movie assignment if it exists
        movie_assignments = config.get_movie_assignments()
        had_assignment = file_path in movie_assignments
        if had_assignment:
            config.remove_movie_assignment(file_path)
            logger.info(f"Removed movie assignment for deleted file: {file_path}")
        
        # Delete the file
        file_to_delete.unlink()
        
        logger.info(f"Successfully deleted file: {file_path} (size: {file_size} bytes)")
        
        return jsonify({
            'message': 'File deleted successfully',
            'file_path': file_path,
            'file_name': file_name,
            'file_size': file_size,
            'had_movie_assignment': had_assignment
        }), 200
        
    except PermissionError:
        logger.error(f"Permission denied when trying to delete file: {file_path}")
        return jsonify({'error': 'Permission denied. Cannot delete file.'}), 403
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500



@app.route('/orphaned-files', methods=['GET'])
def find_orphaned_files():
    """Find files that are directly in movie paths and need to be moved to folders."""
    try:
        movie_paths = config.get_movie_paths()
        orphaned_files = []
        
        for movie_path in movie_paths:
            if os.path.exists(movie_path):
                # Get all files directly in this path (not in subdirectories)
                for item in os.listdir(movie_path):
                    item_path = os.path.join(movie_path, item)
                    if os.path.isfile(item_path) and FileDiscovery.is_media_file(Path(item_path)):
                        # Check if this file has a movie assignment
                        movie_assignments = config.get_movie_assignments()
                        movie_data = movie_assignments.get(item_path)
                        
                        orphaned_files.append({
                            'path': item_path,
                            'name': item,
                            'directory': movie_path,
                            'size': os.path.getsize(item_path),
                            'modified': int(os.path.getmtime(item_path)),
                            'movie_assigned': bool(movie_data),
                            'movie_title': movie_data.get('title', 'Unknown') if movie_data else None,
                            'movie_id': movie_data.get('id') if movie_data else None
                        })
        
        logger.info(f"Found {len(orphaned_files)} orphaned files")
        
        return jsonify({
            'orphaned_files': orphaned_files,
            'total_orphaned_files': len(orphaned_files)
        }), 200
        
    except Exception as e:
        logger.error(f"Error finding orphaned files: {str(e)}")
        return jsonify({'error': f'Failed to find orphaned files: {str(e)}'}), 500

@app.route('/move-to-folder', methods=['POST'])
def move_to_folder():
    """Move a file into its own folder based on its movie assignment."""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data:
            return jsonify({'error': 'file_path is required'}), 400
        
        file_path = data['file_path']
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File does not exist'}), 404
        
        # Get movie assignment for this file
        movie_assignments = config.get_movie_assignments()
        movie_data = movie_assignments.get(file_path)
        
        if not movie_data:
            return jsonify({'error': 'File has no movie assignment'}), 400
        
        # Generate folder name from movie title
        movie_title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        # Clean title and add year if available
        import re
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '', movie_title.replace(' ', '_'))
        if release_date:
            year = release_date.split('-')[0]
            folder_name = f"{clean_title}_{year}"
        else:
            folder_name = clean_title
        
        # Create folder path
        file_dir = os.path.dirname(file_path)
        new_folder_path = os.path.join(file_dir, folder_name)
        
        # Create folder if it doesn't exist
        os.makedirs(new_folder_path, exist_ok=True)
        
        # Move file to new folder
        file_name = os.path.basename(file_path)
        new_file_path = os.path.join(new_folder_path, file_name)
        
        # Check if destination already exists
        if os.path.exists(new_file_path):
            return jsonify({'error': 'Destination file already exists'}), 409
        
        # Move the file
        os.rename(file_path, new_file_path)
        
        # Update movie assignment to new path
        config.remove_movie_assignment(file_path)
        config.assign_movie_to_file(new_file_path, movie_data)
        
        logger.info(f"Successfully moved {file_path} to {new_file_path}")
        
        return jsonify({
            'message': 'File moved successfully',
            'old_path': file_path,
            'new_path': new_file_path,
            'folder_name': folder_name
        }), 200
        
    except Exception as e:
        logger.error(f"Error moving file to folder: {str(e)}")
        return jsonify({'error': f'Failed to move file: {str(e)}'}), 500

@app.route('/duplicates', methods=['GET'])
def find_duplicates():
    """Find files that are assigned to the same movie."""
    try:
        movie_assignments = config.get_movie_assignments()
        
        # Group files by movie ID to find duplicates
        movie_groups = {}
        for file_path, movie_data in movie_assignments.items():
            movie_id = movie_data.get('id')
            if movie_id:
                # ONLY include files that actually exist
                if os.path.exists(file_path):
                    if movie_id not in movie_groups:
                        movie_groups[movie_id] = {
                            'movie_info': {
                                'id': movie_id,
                                'title': movie_data.get('title', 'Unknown'),
                                'release_date': movie_data.get('release_date'),
                                'vote_average': movie_data.get('vote_average')
                            },
                            'files': []
                        }
                    
                    movie_groups[movie_id]['files'].append({
                        'path': file_path,
                        'name': os.path.basename(file_path),
                        'directory': os.path.dirname(file_path),
                        'size': os.path.getsize(file_path),
                        'modified': int(os.path.getmtime(file_path))
                    })
        
        # Filter to only include movies with multiple EXISTING files
        duplicates = {
            movie_id: group_data 
            for movie_id, group_data in movie_groups.items() 
            if len(group_data['files']) > 1
        }
        
        logger.info(f"Found {len(duplicates)} movies with duplicate files")
        
        return jsonify({
            'duplicates': duplicates,
            'total_duplicate_movies': len(duplicates),
            'total_duplicate_files': sum(len(group['files']) for group in duplicates.values())
        }), 200
        
    except Exception as e:
        logger.error(f"Error finding duplicates: {str(e)}")
        return jsonify({'error': f'Failed to find duplicates: {str(e)}'}), 500

# Initialize Plex client
plex_client = PlexClient()

@app.route('/plex/libraries', methods=['GET'])
def get_plex_libraries():
    """Get all Plex libraries."""
    try:
        libraries = plex_client.get_libraries()
        return jsonify({
            'libraries': libraries,
            'total_libraries': len(libraries),
            'movie_libraries': [lib for lib in libraries if lib['type'] == 'movie']
        }), 200
    except Exception as e:
        logger.error(f"Error getting Plex libraries: {str(e)}")
        return jsonify({'error': f'Failed to get Plex libraries: {str(e)}'}), 500

@app.route('/plex/movie-count', methods=['GET'])
def get_plex_movie_count():
    """Get movie count from Plex by library."""
    try:
        counts = plex_client.get_movie_count()
        total_count = sum(counts.values())
        return jsonify({
            'counts_by_library': counts,
            'total_movies': total_count,
            'libraries_count': len(counts)
        }), 200
    except Exception as e:
        logger.error(f"Error getting Plex movie count: {str(e)}")
        return jsonify({'error': f'Failed to get Plex movie count: {str(e)}'}), 500

@app.route('/plex/movies', methods=['GET'])
def get_plex_movies():
    """Get all movies from Plex."""
    try:
        movies = plex_client.get_all_movies()
        return jsonify({
            'movies': movies,
            'total_movies': len(movies)
        }), 200
    except Exception as e:
        logger.error(f"Error getting Plex movies: {str(e)}")
        return jsonify({'error': f'Failed to get Plex movies: {str(e)}'}), 500

@app.route('/plex/search', methods=['GET'])
def search_plex_movies():
    """Search movies in Plex."""
    try:
        query = request.args.get('q', '')
        library_id = request.args.get('library_id')
        
        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400
        
        movies = plex_client.search_movies(query, library_id)
        return jsonify({
            'movies': movies,
            'query': query,
            'library_id': library_id,
            'total_results': len(movies)
        }), 200
    except Exception as e:
        logger.error(f"Error searching Plex movies: {str(e)}")
        return jsonify({'error': f'Failed to search Plex movies: {str(e)}'}), 500

@app.route('/compare-movies', methods=['GET'])
def compare_movies():
    """Compare Plex movies with assigned movies."""
    try:
        logger.info("=== STARTING MOVIE COMPARISON ===")
        import time
        start_time = time.time()
        
        # Get Plex movie count first
        logger.info("Step 1: Getting Plex movie count...")
        step_start = time.time()
        try:
            plex_counts = plex_client.get_movie_count()
            plex_total = sum(plex_counts.values())
            logger.info(f"Successfully got Plex count: {plex_total}")
        except Exception as e:
            logger.error(f"Failed to get Plex count: {e}")
            return jsonify({'error': f'Failed to get Plex movie count: {str(e)}'}), 500
        step_time = time.time() - step_start
        logger.info(f"Step 1 completed in {step_time:.2f}s - Plex total: {plex_total}")
        
        # Get assigned movies from config
        logger.info("Step 2: Fetching assigned movies from config...")
        step_start = time.time()
        logger.info("  Calling config.get_movie_assignments()...")
        assigned_movies = config.get_movie_assignments()
        logger.info(f"  config.get_movie_assignments() returned {len(assigned_movies)} items")
        step_time = time.time() - step_start
        logger.info(f"Step 2 completed in {step_time:.2f}s - Retrieved {len(assigned_movies)} assigned movies")
        
        # Process assigned movies
        logger.info("Step 3: Processing assigned movies...")
        step_start = time.time()
        assigned_titles = set()
        assigned_original_titles = set()
        assigned_files = []
        orphaned_assignments = []
        
        processed_count = 0
        for file_path, movie_data in assigned_movies.items():
            processed_count += 1
            if processed_count % 100 == 0:
                logger.info(f"  Processed {processed_count}/{len(assigned_movies)} assigned movies...")
                
            original_title = movie_data.get('title', '')
            title = original_title.lower().strip()
            
            if os.path.exists(file_path):  # Only include existing files
                if title:
                    assigned_titles.add(title)
                    assigned_original_titles.add(original_title)
                    assigned_files.append({
                        'title': original_title,
                        'file_path': file_path,
                        'year': movie_data.get('release_date', '').split('-')[0] if movie_data.get('release_date') else None
                    })
            else:
                # Track orphaned assignments
                orphaned_assignments.append({
                    'file_path': file_path,
                    'title': original_title
                })
                logger.info(f"🚨 Found orphaned assignment during comparison: {file_path} -> {original_title}")
        
        logger.info(f"Found {len(orphaned_assignments)} orphaned assignments during comparison")
        
        step_time = time.time() - step_start
        logger.info(f"Step 3 completed in {step_time:.2f}s - Processed {len(assigned_files)} existing assigned files")
        
        # Calculate difference
        logger.info("Step 4: Calculating difference...")
        step_start = time.time()
        difference = plex_total - len(assigned_files)
        step_time = time.time() - step_start
        logger.info(f"Step 4 completed in {step_time:.2f}s - Difference: {difference}")
        
        # Get Plex movies for detailed comparison
        logger.info("Step 5: Getting Plex movies for detailed comparison...")
        step_start = time.time()
        try:
            plex_movies = plex_client.get_all_movies()
            logger.info(f"Retrieved {len(plex_movies)} movies from Plex")
            
            # Debug: Check for movies without titles
            movies_without_titles = [movie for movie in plex_movies if not movie.get('title')]
            if movies_without_titles:
                logger.warning(f"Found {len(movies_without_titles)} movies without titles: {[movie.get('id', 'unknown') for movie in movies_without_titles]}")
            
            # Store original titles WITH YEAR for side-by-side comparison
            all_titles_with_year = []
            for movie in plex_movies:
                if movie.get('title'):
                    title = movie['title']
                    year = movie.get('year') or movie.get('release_date', '').split('-')[0] if movie.get('release_date') else ''
                    title_with_year = f"{title} ({year})" if year else title
                    all_titles_with_year.append(title_with_year)
                    # Debug: Show a few examples
                    if len(all_titles_with_year) <= 5:
                        logger.info(f"🔍 DEBUG: Title with year: '{title}' -> '{title_with_year}' (year: {year}, raw year: {movie.get('year')}, release_date: {movie.get('release_date')})")
                        
                    # Debug: Show the raw movie data for the first few movies
                    if len(all_titles_with_year) <= 3:
                        logger.info(f"🔍 DEBUG: Raw movie data: {movie}")
            
            plex_original_titles = set(all_titles_with_year)
            # Store lowercase titles with year for matching
            plex_titles = {title.lower().strip() for title in all_titles_with_year}
            
            logger.info(f"🔍 DEBUG: Movies with titles: {len(plex_original_titles)} out of {len(plex_movies)} total")
            logger.info(f"🔍 DEBUG: All titles with year list length: {len(all_titles_with_year)}")
            logger.info(f"🔍 DEBUG: Set length: {len(plex_original_titles)}")
            
            # Check for duplicates WITH YEAR
            if len(all_titles_with_year) != len(set(all_titles_with_year)):
                logger.warning(f"🔍 DEBUG: Found {len(all_titles_with_year) - len(set(all_titles_with_year))} ACTUAL duplicate titles!")
                from collections import Counter
                title_counts = Counter(all_titles_with_year)
                duplicates = [title for title, count in title_counts.items() if count > 1]
                logger.warning(f"🔍 DEBUG: ACTUAL Duplicate titles: {duplicates}")
            else:
                logger.info(f"🔍 DEBUG: No actual duplicates found - all movies with same title have different years")
                
            # Show the actual titles that are being used for comparison
            logger.info(f"🔍 DEBUG: First 10 titles with year: {all_titles_with_year[:10]}")
                
            # Show sample titles to verify year format
            logger.info(f"🔍 DEBUG: Sample titles with year: {list(plex_original_titles)[:5]}")
        except Exception as e:
            logger.warning(f"Failed to get Plex movies: {e}")
            plex_original_titles = set()
            plex_titles = set()
        step_time = time.time() - step_start
        logger.info(f"Step 5 completed in {step_time:.2f}s")
        
        # Normalize titles for better matching
        logger.info("Step 6: Normalizing titles...")
        step_start = time.time()
        
        # Simple direct comparison - no fancy matching
        logger.info("Step 7: Calculating differences with proper year-aware matching...")
        step_start = time.time()
        
        # Create a mapping of base titles to full titles with years for Plex
        plex_title_mapping = {}
        for title in plex_original_titles:
            # Extract base title and year
            base_title = title
            year = None
            if ' (' in title and title.endswith(')'):
                parts = title.rsplit(' (', 1)
                if len(parts) == 2 and parts[1].endswith(')') and parts[1][:-1].isdigit():
                    base_title = parts[0]
                    year = parts[1][:-1]  # Remove the closing parenthesis
            
            base_title_lower = base_title.lower().strip()
            if base_title_lower not in plex_title_mapping:
                plex_title_mapping[base_title_lower] = []
            plex_title_mapping[base_title_lower].append({
                'full_title': title,
                'base_title': base_title,
                'year': year
            })
        
        # Create a mapping for assigned titles (they don't have years)
        # Include both existing files and orphaned assignments
        assigned_title_mapping = {}
        
        # Add titles from existing files
        for title in assigned_original_titles:
            base_title_lower = title.lower().strip()
            if base_title_lower not in assigned_title_mapping:
                assigned_title_mapping[base_title_lower] = []
            assigned_title_mapping[base_title_lower].append({
                'full_title': title,
                'base_title': title,
                'year': None,
                'status': 'existing'
            })
        
        # Add titles from orphaned assignments
        for orphaned in orphaned_assignments:
            title = orphaned['title']
            base_title_lower = title.lower().strip()
            if base_title_lower not in assigned_title_mapping:
                assigned_title_mapping[base_title_lower] = []
            assigned_title_mapping[base_title_lower].append({
                'full_title': title,
                'base_title': title,
                'year': None,
                'status': 'orphaned'
            })
        
        # Find matches and differences with year awareness
        in_both_original = set()
        only_in_plex_original = set()
        only_in_assigned_original = set()
        
        # Get all unique base titles
        all_base_titles = set(plex_title_mapping.keys()) | set(assigned_title_mapping.keys())
        
        for base_title in all_base_titles:
            plex_versions = plex_title_mapping.get(base_title, [])
            assigned_versions = assigned_title_mapping.get(base_title, [])
            
            if plex_versions and assigned_versions:
                # We have matches - add all plex versions to "in both"
                for plex_version in plex_versions:
                    in_both_original.add(plex_version['full_title'])
                # Add only existing assigned versions to "in both"
                for assigned_version in assigned_versions:
                    if assigned_version['status'] == 'existing':
                        in_both_original.add(assigned_version['full_title'])
                    else:  # orphaned
                        only_in_assigned_original.add(assigned_version['full_title'])
            elif plex_versions:
                # Only in Plex
                for plex_version in plex_versions:
                    only_in_plex_original.add(plex_version['full_title'])
            else:
                # Only in assigned
                for assigned_version in assigned_versions:
                    only_in_assigned_original.add(assigned_version['full_title'])
        
        # Debug: Show some examples of the matching
        logger.info(f"🔍 TITLE MATCHING EXAMPLES:")
        sample_titles = list(all_base_titles)[:5]
        for base_title in sample_titles:
            plex_versions = plex_title_mapping.get(base_title, [])
            assigned_versions = assigned_title_mapping.get(base_title, [])
            logger.info(f"  Base title '{base_title}':")
            logger.info(f"    Plex versions: {[v['full_title'] for v in plex_versions]}")
            logger.info(f"    Assigned versions: {[v['full_title'] for v in assigned_versions]}")
        
        # Verify the math
        logger.info(f"Math verification:")
        logger.info(f"  Plex total: {len(plex_original_titles)}")
        logger.info(f"  Assigned total: {len(assigned_original_titles)}")
        logger.info(f"  In both: {len(in_both_original)}")
        logger.info(f"  Only in Plex: {len(only_in_plex_original)}")
        logger.info(f"  Only in Assigned: {len(only_in_assigned_original)}")
        logger.info(f"  Plex math: {len(only_in_plex_original)} + {len(in_both_original)} = {len(only_in_plex_original) + len(in_both_original)} (should be {len(plex_original_titles)})")
        logger.info(f"  Assigned math: {len(only_in_assigned_original)} + {len(in_both_original)} = {len(only_in_assigned_original) + len(in_both_original)} (should be {len(assigned_original_titles)})")
        
        logger.info(f"Summary: {len(in_both_original)} in both, {len(only_in_plex_original)} only in Plex, {len(only_in_assigned_original)} only in assigned")
        
        step_time = time.time() - step_start
        logger.info(f"Step 7 completed in {step_time:.2f}s")
        
        step_time = time.time() - step_start
        logger.info(f"Step 6 completed in {step_time:.2f}s")
        
        # Prepare response
        logger.info("Step 8: Preparing response...")
        step_start = time.time()
        
        # Create sorted lists for side-by-side comparison
        # Return ONLY the differences, not all movies
        only_in_plex_list = sorted(list(only_in_plex_original))
        only_in_assigned_list = sorted(list(only_in_assigned_original))
        
        # FIX THE FUCKING MATH - Use the actual Plex count from API
        actual_plex_count = plex_total  # Use the real Plex count from API
        actual_assigned_count = len(assigned_movies)  # Count ALL assignments, not just existing files
        actual_in_both = len(in_both_original)
        actual_only_plex = len(only_in_plex_original)
        actual_only_assigned = len(only_in_assigned_original)
        
        # Debug the discrepancy
        logger.info(f"🔍 PLEX COUNT DISCREPANCY:")
        logger.info(f"  API says Plex has: {plex_total} movies")
        logger.info(f"  Comparison found: {len(plex_original_titles)} movies")
        logger.info(f"  Missing: {plex_total - len(plex_original_titles)} movies")
        
        if len(plex_original_titles) != plex_total:
            logger.error(f"❌ PLEX COUNT MISMATCH: API says {plex_total} but comparison found {len(plex_original_titles)}")
            # Find the missing movies
            all_plex_titles = {movie['title'] for movie in plex_movies if movie.get('title')}
            missing_titles = all_plex_titles - plex_original_titles
            logger.error(f"❌ Missing titles: {list(missing_titles)}")
        
        response_data = {
            'summary': {
                'plex_total': actual_plex_count,
                'assigned_total': actual_assigned_count,
                'total_assignments': len(assigned_movies),
                'orphaned_assignments': len(orphaned_assignments),
                'only_in_plex': actual_only_plex,
                'only_in_assigned': actual_only_assigned,
                'in_both': actual_in_both
            },
            'only_in_plex': sorted(list(only_in_plex_original)),
            'only_in_assigned': sorted(list(only_in_assigned_original)),
            'side_by_side_count': actual_only_plex + actual_only_assigned,
            'orphaned_assignments': orphaned_assignments,
            'note': f'Plex has {actual_plex_count} unique movies, you have {actual_assigned_count} assigned movies. {actual_in_both} movies in both, {actual_only_plex} only in Plex, {actual_only_assigned} only in assigned. {len(orphaned_assignments)} orphaned assignments found.'
        }
        step_time = time.time() - step_start
        logger.info(f"Step 5 completed in {step_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== COMPARISON COMPLETED IN {total_time:.2f}s ===")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"=== ERROR IN MOVIE COMPARISON ===")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to compare movies: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'movie_paths_count': len(config.get_movie_paths()),
        'tmdb_configured': bool(TMDB_API_KEY),
        'openai_configured': bool(OPENAI_API_KEY),
        'firebase_configured': bool(firebase_app),
        'firebase_connection': config.use_firebase,
        'storage_type': 'Firebase' if config.use_firebase else 'Local JSON',
        'plex_configured': True
    })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/firebase-cleanup', methods=['POST'])
def firebase_cleanup():
    """Trigger Firebase cleanup to remove orphaned movie assignments."""
    try:
        logger.info("🔥 FIREBASE CLEANUP ENDPOINT CALLED")
        
        # Import the cleanup script
        from cleanup_firebase_assignments import FirebaseCleanup
        
        # Initialize cleanup
        cleanup = FirebaseCleanup()
        
        # Run cleanup (dry run first to analyze)
        analysis = cleanup.cleanup(dry_run=True)
        
        # If there are orphaned assignments, remove them
        if analysis['orphaned_assignments'] > 0:
            logger.info(f"🗑️ Found {analysis['orphaned_assignments']} orphaned assignments, removing...")
            removed_count = cleanup.remove_orphaned_assignments(analysis['orphaned_assignments_list'])
            analysis['removed_count'] = removed_count
            logger.info(f"🎉 Firebase cleanup completed! Removed {removed_count} orphaned assignments")
        else:
            logger.info("🎉 No orphaned assignments found - no cleanup needed")
            analysis['removed_count'] = 0
        
        return jsonify({
            'message': 'Firebase cleanup completed successfully',
            'total_assignments': analysis['total_assignments'],
            'valid_assignments': analysis['valid_assignments'],
            'orphaned_assignments': analysis['orphaned_assignments'],
            'removed_assignments': analysis['removed_count'],
            'summary': f"Cleaned up {analysis['removed_count']} orphaned assignments, {analysis['valid_assignments']} valid assignments remaining"
        }), 200
        
    except Exception as e:
        logger.error(f"Error during Firebase cleanup: {str(e)}")
        return jsonify({'error': f'Failed to cleanup Firebase: {str(e)}'}), 500

@app.route('/verify-assignment', methods=['GET'])
def verify_assignment():
    """Verify if a movie assignment exists for a file."""
    file_path = request.args.get('file_path')
    
    if not file_path:
        return jsonify({'error': 'file_path parameter is required'}), 400
    
    try:
        assignments = config.get_movie_assignments()
        if file_path in assignments:
            movie_data = assignments[file_path]
            return jsonify({
                'exists': True,
                'file_path': file_path,
                'movie': movie_data,
                'message': 'Assignment confirmed in database'
            }), 200
        else:
            return jsonify({
                'exists': False,
                'file_path': file_path,
                'message': 'No assignment found for this file'
            }), 404
    except Exception as e:
        logger.error(f"Error verifying assignment: {str(e)}")
        return jsonify({'error': f'Failed to verify assignment: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("Starting Movie Management API...")
    logger.info(f"TMDB API configured: {bool(TMDB_API_KEY)}")
    logger.info(f"OpenAI API configured: {bool(OPENAI_API_KEY)}")
    logger.info(f"Firebase configured: {bool(firebase_app)}")
    logger.info(f"Storage type: {'Firebase' if config.use_firebase else 'Local JSON'}")
    logger.info(f"Config file (fallback): {CONFIG_FILE}")
    logger.info(f"Movie paths configured: {len(config.get_movie_paths())}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
