#!/usr/bin/env python3
"""
Movie-related API routes.
"""

import os
import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Create blueprint
movie_bp = Blueprint('movie', __name__)

def register_movie_routes(app, config, tmdb_client, openai_client, file_discovery, filename_formatter):
    """Register movie-related routes with the Flask app."""
    
    @app.route('/movie-file-paths', methods=['GET'])
    def get_movie_file_paths():
        """Get all configured movie file paths."""
        try:
            paths = config.get_movie_paths()
            return jsonify({'paths': paths})
        except Exception as e:
            logger.error(f"Error getting movie file paths: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/movie-file-paths', methods=['PUT'])
    def add_movie_file_path():
        """Add a new movie file path."""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': 'Path is required'}), 400
            
            path = data['path']
            if not os.path.exists(path):
                return jsonify({'error': f'Path does not exist: {path}'}), 400
            
            if not os.path.isdir(path):
                return jsonify({'error': f'Path is not a directory: {path}'}), 400
            
            success = config.add_movie_path(path)
            if success:
                return jsonify({'message': f'Path added successfully: {path}'})
            else:
                return jsonify({'message': f'Path already exists: {path}'})
                
        except Exception as e:
            logger.error(f"Error adding movie file path: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/movie-file-paths', methods=['DELETE'])
    def remove_movie_file_path():
        """Remove a movie file path."""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': 'Path is required'}), 400
            
            path = data['path']
            success = config.remove_movie_path(path)
            
            if success:
                return jsonify({'message': f'Path removed successfully: {path}'})
            else:
                return jsonify({'error': f'Path not found: {path}'}), 404
                
        except Exception as e:
            logger.error(f"Error removing movie file path: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/all-files', methods=['GET'])
    def get_all_files():
        """Get all media files from all configured paths."""
        try:
            all_files = []
            movie_paths = config.get_movie_paths()
            movie_assignments = config.get_movie_assignments()
            
            logger.info(f"Getting files from {len(movie_paths)} paths")
            
            for path in movie_paths:
                try:
                    if not os.path.exists(path):
                        logger.warning(f"Path does not exist: {path}")
                        continue
                    
                    files = file_discovery.discover_files(path, movie_assignments)
                    all_files.extend(files)
                    logger.info(f"Found {len(files)} files in {path}")
                    
                except Exception as e:
                    logger.error(f"Error discovering files in {path}: {str(e)}")
                    continue
            
            # Sort files by name for consistent ordering
            all_files.sort(key=lambda x: x['name'].lower())
            
            logger.info(f"Total files found: {len(all_files)}")
            return jsonify({'files': all_files})
            
        except Exception as e:
            logger.error(f"Error getting all files: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/search-movie', methods=['GET'])
    def search_movie():
        """Search for a movie using TMDB API."""
        try:
            query = request.args.get('q', '').strip()
            if not query:
                return jsonify({'error': 'Query parameter is required'}), 400
            
            logger.info(f"Searching for movie: {query}")
            
            # Try OpenAI cleaning first if available
            cleaned_query = query
            if openai_client and openai_client.client:
                try:
                    openai_result = openai_client.clean_filename(query)
                    if openai_result.get('success') and 'cleaned_title' in openai_result:
                        cleaned_query = openai_result['cleaned_title']
                        logger.info(f"OpenAI cleaned query: '{query}' -> '{cleaned_query}'")
                except Exception as e:
                    logger.warning(f"OpenAI cleaning failed, using original query: {str(e)}")
            
            # Search TMDB
            result = tmdb_client.search_movie(cleaned_query)
            
            if 'error' in result:
                return jsonify(result), 500
            
            logger.info(f"TMDB search returned {len(result.get('results', []))} results")
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error searching movie: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/assign-movie', methods=['POST'])
    def assign_movie():
        """Assign a movie to a file."""
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
            
            logger.info(f"Assigning movie '{movie_data['title']}' to file: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                return jsonify({'error': f'File does not exist: {file_path}'}), 400
            
            # Assign movie to file
            success = config.assign_movie_to_file(file_path, movie_data)
            
            if success:
                logger.info(f"Successfully assigned movie '{movie_data['title']}' to file: {file_path}")
                return jsonify({
                    'message': f'Movie "{movie_data["title"]}" assigned to file successfully',
                    'file_path': file_path,
                    'movie': movie_data
                })
            else:
                return jsonify({'error': 'Failed to assign movie to file'}), 500
                
        except Exception as e:
            logger.error(f"Error assigning movie: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/remove-movie-assignment', methods=['DELETE'])
    def remove_movie_assignment():
        """Remove movie assignment from a file."""
        try:
            data = request.get_json()
            if not data or 'file_path' not in data:
                return jsonify({'error': 'file_path is required'}), 400
            
            file_path = data['file_path']
            logger.info(f"Removing movie assignment for file: {file_path}")
            
            success = config.remove_movie_assignment(file_path)
            
            if success:
                return jsonify({'message': f'Movie assignment removed from file: {file_path}'})
            else:
                return jsonify({'error': f'No movie assignment found for file: {file_path}'}), 404
                
        except Exception as e:
            logger.error(f"Error removing movie assignment: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/verify-assignment', methods=['GET'])
    def verify_assignment():
        """Verify if a movie assignment exists for a file."""
        try:
            file_path = request.args.get('file_path')
            if not file_path:
                return jsonify({'error': 'file_path parameter is required'}), 400
            
            movie_assignments = config.get_movie_assignments()
            movie_data = movie_assignments.get(file_path)
            
            if movie_data:
                return jsonify({
                    'assigned': True,
                    'file_path': file_path,
                    'movie': movie_data
                })
            else:
                return jsonify({
                    'assigned': False,
                    'file_path': file_path,
                    'movie': None
                })
                
        except Exception as e:
            logger.error(f"Error verifying assignment: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/assigned-movies', methods=['GET'])
    def get_assigned_movies():
        """Get all assigned movies."""
        try:
            movie_assignments = config.get_movie_assignments()
            
            # Convert to list format for easier frontend consumption
            assigned_movies = []
            for file_path, movie_data in movie_assignments.items():
                assigned_movies.append({
                    'file_path': file_path,
                    'movie': movie_data
                })
            
            # Sort by movie title
            assigned_movies.sort(key=lambda x: x['movie'].get('title', '').lower())
            
            return jsonify({
                'assigned_movies': assigned_movies,
                'total_count': len(assigned_movies)
            })
            
        except Exception as e:
            logger.error(f"Error getting assigned movies: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/debug-assignments', methods=['GET'])
    def debug_assignments():
        """Debug movie assignments."""
        try:
            movie_assignments = config.get_movie_assignments()
            
            # Check for orphaned assignments (files that no longer exist)
            orphaned_assignments = []
            valid_assignments = []
            
            for file_path, movie_data in movie_assignments.items():
                if os.path.exists(file_path):
                    valid_assignments.append({
                        'file_path': file_path,
                        'movie': movie_data,
                        'exists': True
                    })
                else:
                    orphaned_assignments.append({
                        'file_path': file_path,
                        'movie': movie_data,
                        'exists': False
                    })
            
            return jsonify({
                'total_assignments': len(movie_assignments),
                'valid_assignments': len(valid_assignments),
                'orphaned_assignments': len(orphaned_assignments),
                'orphaned_files': orphaned_assignments,
                'valid_files': valid_assignments
            })
            
        except Exception as e:
            logger.error(f"Error debugging assignments: {str(e)}")
            return jsonify({'error': str(e)}), 500
