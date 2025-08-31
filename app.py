#!/usr/bin/env python3
"""
Movie Management REST API
A Flask-based REST API for managing movie file paths and discovering media files,
with TMDB API integration for movie metadata.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
CONFIG_FILE = "config.json"
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Supported media file extensions
MEDIA_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.asf', '.rm', '.rmvb', '.vob', '.ts'
}

class Config:
    """Manages the application configuration including movie file paths."""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
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
    
    def _save_config(self) -> None:
        """Save configuration to JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            raise Exception(f"Failed to save configuration: {str(e)}")
    
    def get_movie_paths(self) -> List[str]:
        """Get list of movie file paths."""
        return self.data.get("movie_file_paths", [])
    
    def add_movie_path(self, path: str) -> bool:
        """Add a movie file path if it doesn't already exist."""
        paths = self.data.setdefault("movie_file_paths", [])
        if path not in paths:
            paths.append(path)
            self._save_config()
            return True
        return False
    
    def remove_movie_path(self, path: str) -> bool:
        """Remove a movie file path."""
        paths = self.data.get("movie_file_paths", [])
        if path in paths:
            paths.remove(path)
            self._save_config()
            return True
        return False

# Initialize configuration
config = Config()

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
            return {"error": "TMDB API key not configured"}
        
        url = f"{self.base_url}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': query,
            'language': 'en-US'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": f"TMDB API error: {str(e)}"}

# Initialize TMDB client
tmdb_client = TMDBClient(TMDB_API_KEY)

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
    """Search for movie metadata using TMDB API."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    result = tmdb_client.search_movie(query)
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'movie_paths_count': len(config.get_movie_paths()),
        'tmdb_configured': bool(TMDB_API_KEY)
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
    print("Starting Movie Management API...")
    print(f"TMDB API configured: {bool(TMDB_API_KEY)}")
    print(f"Config file: {CONFIG_FILE}")
    print(f"Movie paths configured: {len(config.get_movie_paths())}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
