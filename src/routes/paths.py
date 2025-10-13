#!/usr/bin/env python3
"""
Path Management Routes
Routes for managing movie file paths, media paths, and download paths.
"""

import os
import sys
from flask import Blueprint, request, jsonify
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))
from config.config import config

# Create blueprint
paths_bp = Blueprint('paths', __name__)

@paths_bp.route('/movie-file-paths', methods=['GET'])
def get_movie_file_paths():
    """Get all configured movie file paths."""
    movie_paths = config.get_movie_paths() or []
    return jsonify({
        'movie_file_paths': movie_paths,
        'count': len(movie_paths)
    })

@paths_bp.route('/movie-file-paths', methods=['PUT'])
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
            'movie_file_paths': config.get_movie_paths() or []
        }), 201
    else:
        return jsonify({
            'message': 'Path already exists',
            'path': path,
            'movie_file_paths': config.get_movie_paths() or []
        }), 200

@paths_bp.route('/movie-file-paths', methods=['DELETE'])
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
            'movie_file_paths': config.get_movie_paths() or []
        }), 200
    else:
        return jsonify({
            'error': 'Path not found',
            'path': path,
            'movie_file_paths': config.get_movie_paths() or []
        }), 404

@paths_bp.route('/media-paths', methods=['GET'])
def get_media_paths():
    """Get all configured media paths with space information."""
    media_paths = config.get_media_paths() or []
    return jsonify({
        'media_paths': media_paths,
        'count': len(media_paths)
    })

@paths_bp.route('/media-paths', methods=['PUT'])
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

@paths_bp.route('/media-paths', methods=['DELETE'])
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

@paths_bp.route('/media-paths/refresh', methods=['POST'])
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
        return jsonify({'error': f'Failed to refresh space information: {str(e)}'}), 500

@paths_bp.route('/download-paths', methods=['GET'])
def get_download_paths():
    """Get all configured download paths."""
    download_paths = config.get_download_paths() or []
    return jsonify({
        'download_paths': download_paths,
        'count': len(download_paths)
    })

@paths_bp.route('/download-paths', methods=['PUT'])
def add_download_path():
    """Add a new download path."""
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
    
    if config.add_download_path(path):
        return jsonify({
            'message': 'Download path added successfully',
            'path': path,
            'download_paths': config.get_download_paths()
        }), 201
    else:
        return jsonify({
            'message': 'Download path already exists',
            'path': path,
            'download_paths': config.get_download_paths()
        }), 200

@paths_bp.route('/download-paths', methods=['DELETE'])
def remove_download_path():
    """Remove a download path."""
    data = request.get_json()
    
    if not data or 'path' not in data:
        return jsonify({'error': 'Path is required'}), 400
    
    path = data['path'].strip()
    if not path:
        return jsonify({'error': 'Path cannot be empty'}), 400
    
    if config.remove_download_path(path):
        return jsonify({
            'message': 'Download path removed successfully',
            'path': path,
            'download_paths': config.get_download_paths()
        }), 200
    else:
        return jsonify({
            'error': 'Download path not found',
            'path': path,
            'download_paths': config.get_download_paths()
        }), 404

@paths_bp.route('/download-paths/contents', methods=['GET'])
def get_download_path_contents():
    """Get contents of a download path (folders and files)."""
    path = request.args.get('path', '').strip()
    
    if not path:
        return jsonify({'error': 'Path parameter is required'}), 400
    
    contents = config.get_download_path_contents(path)
    return jsonify(contents)
