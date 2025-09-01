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
from pathlib import Path
from typing import List, Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, db

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
                    "tmdb_api_key": TMDB_API_KEY
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
                logger.info(f"🔥 Assignment file paths: {list(data['movie_assignments'].keys())}")
            
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
        logger.info(f"🎬 ASSIGN MOVIE START: {movie_data.get('title', 'Unknown')} -> {file_path}")
        logger.info(f"🔥 Using Firebase: {self.use_firebase}")
        
        if self.use_firebase:
            try:
                logger.info("📡 Getting Firebase data...")
                data = self._get_firebase_data()
                logger.info(f"📡 Firebase data keys: {list(data.keys()) if data else 'None'}")
                
                assignments = data.setdefault("movie_assignments", {})
                logger.info(f"📊 Current assignments count: {len(assignments)}")
                
                # Encode file path for Firebase (Firebase keys can't contain / . etc.)
                encoded_path = self._encode_path_for_firebase(file_path)
                logger.info(f"🔑 Encoded path: {encoded_path}")
                
                assignments[encoded_path] = {**movie_data, 'original_path': file_path}
                logger.info(f"➕ Added assignment, new count: {len(assignments)}")
                
                logger.info("💾 Saving to Firebase...")
                self._save_firebase_data(data)
                logger.info("✅ Firebase save completed!")
                
                logger.info(f"🎉 SUCCESS: Movie '{movie_data.get('title', 'Unknown')}' assigned to Firebase!")
                return True
            except Exception as e:
                logger.error(f"❌ FIREBASE FAILED: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                # Fallback to local storage
                logger.info("🔄 Falling back to local storage...")
                assignments = self.data.setdefault("movie_assignments", {})
                assignments[file_path] = movie_data
                self._save_local_config()
                logger.info("✅ Local fallback completed!")
                return True
        else:
            logger.info("💾 Using local storage only...")
            assignments = self.data.setdefault("movie_assignments", {})
            assignments[file_path] = movie_data
            self._save_local_config()
            logger.info("✅ Local save completed!")
            return True
    
    def remove_movie_assignment(self, file_path: str) -> bool:
        """Remove a movie assignment from a file."""
        if self.use_firebase:
            try:
                data = self._get_firebase_data()
                assignments = data.get("movie_assignments", {})
                if file_path in assignments:
                    del assignments[file_path]
                    self._save_firebase_data(data)
                    logger.info(f"Removed movie assignment for file: {file_path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Firebase error when removing assignment, falling back to local: {str(e)}")
                # Fallback to local storage
                assignments = self.data.get("movie_assignments", {})
                if file_path in assignments:
                    del assignments[file_path]
                    self._save_local_config()
                    return True
                return False
        else:
            assignments = self.data.get("movie_assignments", {})
            if file_path in assignments:
                del assignments[file_path]
                self._save_local_config()
                return True
            return False

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
                        
                        # Add filename information for existing assignments
                        standard_filename = FilenameFormatter.generate_standard_filename(movie_data, file_path_str)
                        current_filename = file_path.name
                        needs_rename = FilenameFormatter.should_rename_file(file_path_str, standard_filename)
                        
                        file_info['filenameInfo'] = {
                            'current_filename': current_filename,
                            'standard_filename': standard_filename,
                            'needs_rename': needs_rename
                        }
                        
                        logger.info(f"🎬 Added filename info for existing assignment: {file_path_str}")
                        logger.info(f"📝 Current: {current_filename}, Standard: {standard_filename}, Needs rename: {needs_rename}")
                    else:
                        logger.debug(f"📂 No assignment found for: {file_path_str}")
                    
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
        """Search for a movie by title."""
        if not self.api_key:
            logger.error("TMDB API key not configured")
            return {"error": "TMDB API key not configured"}
        
        url = f"{self.base_url}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': query,
            'language': 'en-US'
        }
        
        try:
            logger.debug(f"Making TMDB API request for query: {query}")
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"TMDB API response received with {len(result.get('results', []))} results")
            return result
        except requests.RequestException as e:
            logger.error(f"TMDB API error for query '{query}': {str(e)}")
            return {"error": f"TMDB API error: {str(e)}"}

class FilenameFormatter:
    """Utility class for formatting movie filenames to standard format."""
    
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
    def should_rename_file(current_filename: str, standard_filename: str) -> bool:
        """Check if the current filename differs from the standard format."""
        # Extract just the filename without path
        current_name = Path(current_filename).name
        return current_name != standard_filename

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
        
        # Create a prompt to extract clean movie title from filename
        prompt = f"""
You are a movie filename parser. Given a movie filename, extract the clean movie title by removing:
- File extensions (.mp4, .mkv, .avi, etc.)
- Years in brackets or parentheses like (2023), [2023]
- Quality indicators like 1080p, 720p, 4K, BluRay, WEBRip, etc.
- Release group tags in brackets like [YIFY], [RARBG]
- Extra periods, underscores, and dashes used as separators
- Any other technical metadata

Return ONLY the clean movie title, nothing else.

Filename: {filename}
Clean title:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that cleans movie filenames."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            cleaned_title = response.choices[0].message.content.strip()
            logger.info(f"OpenAI cleaned '{filename}' to '{cleaned_title}'")
            
            return {
                "cleaned_title": cleaned_title,
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
    logger.debug(f"🎬 Assignment keys: {list(movie_assignments.keys())}")
    
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
            standard_filename = FilenameFormatter.generate_standard_filename(movie_data, file_path)
            current_filename = Path(file_path).name
            needs_rename = FilenameFormatter.should_rename_file(file_path, standard_filename)
            
            logger.info(f"Successfully assigned movie '{movie_data.get('title')}' to file: {file_path}")
            
            response_data = {
                'message': 'Movie assigned successfully',
                'file_path': file_path,
                'movie': movie_data,
                'filename_info': {
                    'current_filename': current_filename,
                    'standard_filename': standard_filename,
                    'needs_rename': needs_rename
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

@app.route('/assigned-movies', methods=['GET'])
def get_assigned_movies():
    """Get all movies that are currently assigned to files."""
    try:
        assignments = config.get_movie_assignments()
        
        # Extract just the movie data from assignments
        assigned_movies = []
        for file_path, movie_data in assignments.items():
            if isinstance(movie_data, dict) and movie_data.get('id'):
                assigned_movies.append({
                    'movie': movie_data,
                    'file_path': file_path
                })
        
        return jsonify({
            'assigned_movies': assigned_movies,
            'count': len(assigned_movies)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting assigned movies: {str(e)}")
        return jsonify({'error': f'Failed to get assigned movies: {str(e)}'}), 500

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
        
        # Update movie assignments if they exist
        movie_assignments = config.get_movie_assignments()
        if current_path in movie_assignments:
            movie_data = movie_assignments[current_path]
            config.remove_movie_assignment(current_path)
            config.assign_movie_to_file(str(new_path), movie_data)
        
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

@app.route('/debug-assignments', methods=['GET'])
def debug_assignments():
    """Debug endpoint to check movie assignments."""
    try:
        assignments = config.get_movie_assignments()
        return jsonify({
            'assignments_count': len(assignments),
            'assignments': assignments,
            'assignment_keys': list(assignments.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        'storage_type': 'Firebase' if config.use_firebase else 'Local JSON'
    })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("Starting Movie Management API...")
    logger.info(f"TMDB API configured: {bool(TMDB_API_KEY)}")
    logger.info(f"OpenAI API configured: {bool(OPENAI_API_KEY)}")
    logger.info(f"Firebase configured: {bool(firebase_app)}")
    logger.info(f"Storage type: {'Firebase' if config.use_firebase else 'Local JSON'}")
    logger.info(f"Config file (fallback): {CONFIG_FILE}")
    logger.info(f"Movie paths configured: {len(config.get_movie_paths())}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
