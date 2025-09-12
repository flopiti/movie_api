#!/usr/bin/env python3
"""
Movie Management Routes
Routes for movie search, assignment, and management operations.
"""

import os
from pathlib import Path
from flask import Blueprint, request, jsonify
from config import config
from openai_client import OpenAIClient
from tmdb_client import TMDBClient
from config import TMDB_API_KEY, OPENAI_API_KEY

# Create blueprint
movies_bp = Blueprint('movies', __name__)

# Initialize clients
tmdb_client = TMDBClient(TMDB_API_KEY)
openai_client = OpenAIClient(OPENAI_API_KEY)

@movies_bp.route('/search-movie', methods=['GET'])
def search_movie():
    """Search for movie metadata using OpenAI to clean filename first, then TMDB API."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400

    # Step 1: Clean the filename using OpenAI
    openai_result = openai_client.clean_filename(query)
    
    # Prepare the search query - use cleaned title if available, otherwise fallback to original
    if openai_result.get('success') and openai_result.get('cleaned_title'):
        search_query = openai_result['cleaned_title']
    else:
        search_query = query

    # Step 2: Search TMDB with the cleaned query
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
        if tmdb_result['results']:
            top_result = tmdb_result['results'][0]
    else:
        pass
    return jsonify(response)

@movies_bp.route('/assign-movie', methods=['POST'])
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
            standard_filename = config._generate_standard_filename(movie_data, file_path)
            current_filename = file_path_obj.name
            needs_rename = config._should_rename_file(file_path, standard_filename)
            
            # Generate standard folder information
            current_folder_path = str(file_path_obj.parent)
            standard_foldername = config._generate_standard_foldername(movie_data)
            folder_needs_rename = config._should_rename_folder(current_folder_path, standard_foldername)
            current_foldername = file_path_obj.parent.name

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
        pass
        return jsonify({'error': f'Failed to assign movie: {str(e)}'}), 500

@movies_bp.route('/remove-movie-assignment', methods=['DELETE'])
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
        pass
        return jsonify({'error': f'Failed to remove movie assignment: {str(e)}'}), 500

@movies_bp.route('/assigned-movies', methods=['GET'])
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
        pass
        return jsonify({'error': f'Failed to get assigned movies: {str(e)}'}), 500

@movies_bp.route('/download-files/search-radarr', methods=['GET'])
def search_radarr_movies():
    """Search for movies using Radarr API."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    try:
        movies = config.search_radarr_movies(query)
        return jsonify({
            'movies': movies,
            'count': len(movies),
            'query': query
        })
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to search Radarr: {str(e)}'}), 500

@movies_bp.route('/download-files/assign-movie', methods=['POST'])
def assign_movie_to_download_file():
    """Assign a movie to a download file."""
    data = request.get_json()
    
    if not data or 'file_path' not in data or 'movie' not in data:
        return jsonify({'error': 'file_path and movie are required'}), 400
    
    file_path = data['file_path']
    movie_data = data['movie']
    
    try:
        if config.assign_movie_to_file(file_path, movie_data):
            # Generate filename and folder info for download files
            filename_info = config._generate_filename_info(movie_data, file_path)
            folder_info = config._generate_folder_info(movie_data, file_path)

            return jsonify({
                'message': 'Movie assigned successfully',
                'file_path': file_path,
                'movie': movie_data,
                'filenameInfo': filename_info,
                'folderInfo': folder_info
            }), 200
        else:
            return jsonify({'error': 'Failed to assign movie'}), 500
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to assign movie: {str(e)}'}), 500

@movies_bp.route('/download-files/remove-assignment', methods=['DELETE'])
def remove_movie_assignment_from_download_file():
    """Remove movie assignment from a download file."""
    data = request.get_json()
    
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path is required'}), 400
    
    file_path = data['file_path']
    
    try:
        if config.remove_movie_assignment(file_path):
            return jsonify({
                'message': 'Movie assignment removed successfully',
                'file_path': file_path
            }), 200
        else:
            return jsonify({'error': 'Failed to remove movie assignment'}), 500
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to remove movie assignment: {str(e)}'}), 500

@movies_bp.route('/compare-radarr-plex', methods=['GET'])
def compare_radarr_plex():
    """Compare movies between Radarr and Plex to find differences."""
    try:
        comparison_result = config.compare_radarr_vs_plex()
        
        if comparison_result.get('success'):
            return jsonify(comparison_result), 200
        else:
            return jsonify(comparison_result), 500
            
    except Exception as e:
        pass
        return jsonify({
            'error': f'Failed to compare Radarr vs Plex: {str(e)}',
            'success': False
        }), 500

@movies_bp.route('/verify-assignment', methods=['GET'])
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
        pass
        return jsonify({'error': f'Failed to verify assignment: {str(e)}'}), 500
