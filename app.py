#!/usr/bin/env python3
"""
Movie Management REST API
A Flask-based REST API for managing movie file paths and discovering media files,
with TMDB API integration for movie metadata.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, db

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), 'env')
print(f"Loading env file from: {env_path}")
print(f"Env file exists: {os.path.exists(env_path)}")
load_dotenv(env_path)

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
    
    def __init__(self, config_file: str = CONFIG_FILE, use_firebase: bool = True):
        self.config_file = config_file
        self.use_firebase = use_firebase and firebase_app is not None
        self.firebase_ref = db.reference('movie_config') if self.use_firebase else None
        
        # Initialize with local JSON config as fallback if Firebase is not available
        if not self.use_firebase:
            logger.info(f"Using local JSON config at: {self.config_file}")
            self.data = self._load_local_config()
    
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
            "tmdb_api_key": TMDB_API_KEY
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
            self.firebase_ref.set(data)
        except Exception as e:
            logger.error(f"Failed to save Firebase data: {str(e)}")
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

# Initialize configuration with Firebase enabled by default when available
config = Config(use_firebase=True)

class FileDiscovery:
    """Handles recursive file discovery in movie directories."""
    
    @staticmethod
    def is_media_file(file_path: Path) -> bool:
        """Check if a file is a media file based on its extension."""
        return file_path.suffix.lower() in MEDIA_EXTENSIONS
    
    @staticmethod
    def discover_files(root_path: str) -> List[Dict[str, Any]]:
        """Recursively discover all media files in a directory."""
        files = []
        root = Path(root_path)
        
        if not root.exists():
            return files
        
        try:
            for file_path in root.rglob('*'):
                if file_path.is_file() and FileDiscovery.is_media_file(file_path):
                    files.append({
                        'path': str(file_path),
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime,
                        'directory': str(file_path.parent)
                    })
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

class OpenAIClient:
    """OpenAI API client for cleaning movie filenames."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            try:
                # Initialize OpenAI client with minimal parameters to avoid proxy issues
                self.client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {str(e)}")
                self.client = None
        else:
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
    
    for path in paths:
        files = FileDiscovery.discover_files(path)
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
