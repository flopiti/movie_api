#!/usr/bin/env python3
"""
Download paths management API routes.
"""

import os
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def register_download_routes(app, config):
    """Register download paths management routes with the Flask app."""
    
    @app.route('/download-paths', methods=['GET'])
    def get_download_paths():
        """Get all configured download paths."""
        try:
            paths = config.get_download_paths()
            return jsonify({'paths': paths})
        except Exception as e:
            logger.error(f"Error getting download paths: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-paths', methods=['PUT'])
    def add_download_path():
        """Add a new download path."""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': 'Path is required'}), 400
            
            path = data['path']
            if not os.path.exists(path):
                return jsonify({'error': f'Path does not exist: {path}'}), 400
            
            if not os.path.isdir(path):
                return jsonify({'error': f'Path is not a directory: {path}'}), 400
            
            success = config.add_download_path(path)
            if success:
                return jsonify({'message': f'Download path added successfully: {path}'})
            else:
                return jsonify({'message': f'Download path already exists: {path}'})
                
        except Exception as e:
            logger.error(f"Error adding download path: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-paths', methods=['DELETE'])
    def remove_download_path():
        """Remove a download path."""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': 'Path is required'}), 400
            
            path = data['path']
            success = config.remove_download_path(path)
            
            if success:
                return jsonify({'message': f'Download path removed successfully: {path}'})
            else:
                return jsonify({'error': f'Download path not found: {path}'}), 404
                
        except Exception as e:
            logger.error(f"Error removing download path: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-paths/contents', methods=['GET'])
    def get_download_path_contents():
        """Get contents of a download path (folders and files)."""
        try:
            path = request.args.get('path')
            if not path:
                return jsonify({'error': 'Path parameter is required'}), 400
            
            contents = config.get_download_path_contents(path)
            return jsonify(contents)
            
        except Exception as e:
            logger.error(f"Error getting download path contents: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-files', methods=['GET'])
    def get_download_files():
        """Get all media files from download paths (flattened, no folders)."""
        try:
            files = config.get_download_files()
            return jsonify({'files': files})
        except Exception as e:
            logger.error(f"Error getting download files: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-files/search-radarr', methods=['GET'])
    def search_radarr_movies():
        """Search for movies using Radarr API."""
        try:
            query = request.args.get('q', '').strip()
            if not query:
                return jsonify({'error': 'Query parameter is required'}), 400
            
            movies = config.search_radarr_movies(query)
            return jsonify({'movies': movies})
            
        except Exception as e:
            logger.error(f"Error searching Radarr movies: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-files/assign-movie', methods=['POST'])
    def assign_movie_to_download_file():
        """Assign a movie to a download file."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            file_path = data.get('file_path')
            movie_data = data.get('movie')
            
            if not file_path:
                return jsonify({'error': 'file_path is required'}), 400
            
            if not movie_data:
                return jsonify({'error': 'movie data is required'}), 400
            
            # Validate required movie fields
            required_fields = ['id', 'title']
            for field in required_fields:
                if field not in movie_data:
                    return jsonify({'error': f'movie.{field} is required'}), 400
            
            logger.info(f"Assigning movie '{movie_data['title']}' to download file: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                return jsonify({'error': f'File does not exist: {file_path}'}), 400
            
            # Assign movie to file
            success = config.assign_movie_to_file(file_path, movie_data)
            
            if success:
                logger.info(f"Successfully assigned movie '{movie_data['title']}' to download file: {file_path}")
                return jsonify({
                    'message': f'Movie "{movie_data["title"]}" assigned to download file successfully',
                    'file_path': file_path,
                    'movie': movie_data
                })
            else:
                return jsonify({'error': 'Failed to assign movie to download file'}), 500
                
        except Exception as e:
            logger.error(f"Error assigning movie to download file: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/download-files/remove-assignment', methods=['DELETE'])
    def remove_movie_assignment_from_download_file():
        """Remove movie assignment from a download file."""
        try:
            data = request.get_json()
            if not data or 'file_path' not in data:
                return jsonify({'error': 'file_path is required'}), 400
            
            file_path = data['file_path']
            logger.info(f"Removing movie assignment from download file: {file_path}")
            
            success = config.remove_movie_assignment(file_path)
            
            if success:
                return jsonify({'message': f'Movie assignment removed from download file: {file_path}'})
            else:
                return jsonify({'error': f'No movie assignment found for download file: {file_path}'}), 404
                
        except Exception as e:
            logger.error(f"Error removing movie assignment from download file: {str(e)}")
            return jsonify({'error': str(e)}), 500
