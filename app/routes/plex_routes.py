#!/usr/bin/env python3
"""
Plex-related API routes.
"""

import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def register_plex_routes(app, plex_client, config):
    """Register Plex-related routes with the Flask app."""
    
    @app.route('/plex/libraries', methods=['GET'])
    def get_plex_libraries():
        """Get all Plex libraries."""
        try:
            libraries = plex_client.get_libraries()
            return jsonify({'libraries': libraries})
        except Exception as e:
            logger.error(f"Error getting Plex libraries: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/plex/movie-count', methods=['GET'])
    def get_plex_movie_count():
        """Get movie count from Plex."""
        try:
            count = plex_client.get_movie_count()
            return jsonify({'count': count})
        except Exception as e:
            logger.error(f"Error getting Plex movie count: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/plex/movies', methods=['GET'])
    def get_plex_movies():
        """Get all movies from Plex."""
        try:
            movies = plex_client.get_all_movies()
            return jsonify({'movies': movies})
        except Exception as e:
            logger.error(f"Error getting Plex movies: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/plex/search', methods=['GET'])
    def search_plex_movies():
        """Search movies in Plex."""
        try:
            query = request.args.get('q', '').strip()
            library_id = request.args.get('library_id')
            
            if not query:
                return jsonify({'error': 'Query parameter is required'}), 400
            
            movies = plex_client.search_movies(query, library_id)
            return jsonify({'movies': movies})
            
        except Exception as e:
            logger.error(f"Error searching Plex movies: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/compare-movies', methods=['GET'])
    def compare_movies():
        """Compare Plex movies with assigned movies."""
        try:
            # Get Plex movies
            plex_movies = plex_client.get_all_movies()
            
            # Get assigned movies
            movie_assignments = config.get_movie_assignments()
            
            # Create comparison data
            plex_titles = set()
            assigned_titles = set()
            
            # Process Plex movies
            for movie in plex_movies:
                title = movie.get('title', '')
                year = movie.get('year', '')
                if title:
                    normalized_title = f"{title.lower().strip()} ({year})" if year else title.lower().strip()
                    plex_titles.add(normalized_title)
            
            # Process assigned movies
            for file_path, movie_data in movie_assignments.items():
                title = movie_data.get('title', '')
                release_date = movie_data.get('release_date', '')
                year = release_date.split('-')[0] if release_date else ''
                if title:
                    normalized_title = f"{title.lower().strip()} ({year})" if year else title.lower().strip()
                    assigned_titles.add(normalized_title)
            
            # Find differences
            movies_in_plex_not_assigned = plex_titles - assigned_titles
            movies_assigned_not_in_plex = assigned_titles - plex_titles
            common_movies = plex_titles.intersection(assigned_titles)
            
            return jsonify({
                'plex_movies': list(plex_titles),
                'assigned_movies': list(assigned_titles),
                'movies_in_plex_not_assigned': list(movies_in_plex_not_assigned),
                'movies_assigned_not_in_plex': list(movies_assigned_not_in_plex),
                'common_movies': list(common_movies),
                'total_plex': len(plex_titles),
                'total_assigned': len(assigned_titles),
                'comparison_summary': {
                    'plex_count': len(plex_titles),
                    'assigned_count': len(assigned_titles),
                    'common_count': len(common_movies),
                    'plex_only_count': len(movies_in_plex_not_assigned),
                    'assigned_only_count': len(movies_assigned_not_in_plex)
                }
            })
            
        except Exception as e:
            logger.error(f"Error comparing movies: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/compare-radarr-plex', methods=['GET'])
    def compare_radarr_plex():
        """Compare Radarr vs Plex movies."""
        try:
            comparison = config.compare_radarr_vs_plex()
            return jsonify(comparison)
        except Exception as e:
            logger.error(f"Error comparing Radarr vs Plex: {str(e)}")
            return jsonify({'error': str(e)}), 500
