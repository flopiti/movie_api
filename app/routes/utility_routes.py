#!/usr/bin/env python3
"""
Utility API routes (health check, duplicates, etc.).
"""

import os
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def register_utility_routes(app, config):
    """Register utility routes with the Flask app."""
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        try:
            return jsonify({
                'status': 'healthy',
                'message': 'Movie Management API is running',
                'redis_connected': config.use_redis,
                'version': '1.0.0'
            })
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

    @app.route('/duplicates', methods=['GET'])
    def find_duplicates():
        """Find files that are assigned to the same movie."""
        try:
            movie_assignments = config.get_movie_assignments()
            
            # Group files by movie title and year
            movie_groups = {}
            for file_path, movie_data in movie_assignments.items():
                title = movie_data.get('title', 'Unknown')
                year = movie_data.get('release_date', '').split('-')[0] if movie_data.get('release_date') else ''
                movie_key = f"{title} ({year})" if year else title
                
                if movie_key not in movie_groups:
                    movie_groups[movie_key] = []
                
                movie_groups[movie_key].append({
                    'file_path': file_path,
                    'movie': movie_data
                })
            
            # Find duplicates (movies with more than one file)
            duplicates = {}
            for movie_key, files in movie_groups.items():
                if len(files) > 1:
                    duplicates[movie_key] = {
                        'movie_title': files[0]['movie'].get('title', 'Unknown'),
                        'movie_year': files[0]['movie'].get('release_date', '').split('-')[0] if files[0]['movie'].get('release_date') else '',
                        'files': files,
                        'count': len(files)
                    }
            
            return jsonify({
                'duplicates': duplicates,
                'total_duplicates': len(duplicates),
                'total_movies': len(movie_groups)
            })
            
        except Exception as e:
            logger.error(f"Error finding duplicates: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/redis-cleanup', methods=['POST'])
    def redis_cleanup():
        """Clean up Redis data."""
        try:
            if not config.use_redis:
                return jsonify({'error': 'Redis is not enabled'}), 400
            
            # Get current data
            data = config._get_redis_data()
            
            # Clean up orphaned assignments
            movie_assignments = data.get('movie_assignments', {})
            orphaned_assignments = []
            valid_assignments = {}
            
            for file_path, movie_data in movie_assignments.items():
                if os.path.exists(file_path):
                    valid_assignments[file_path] = movie_data
                else:
                    orphaned_assignments.append(file_path)
            
            # Update data with only valid assignments
            data['movie_assignments'] = valid_assignments
            
            # Save cleaned data
            config._save_redis_data(data)
            
            logger.info(f"Redis cleanup completed: {len(orphaned_assignments)} orphaned assignments removed")
            
            return jsonify({
                'message': f'Redis cleanup completed! Removed {len(orphaned_assignments)} orphaned assignments.',
                'orphaned_assignments_removed': len(orphaned_assignments),
                'valid_assignments_remaining': len(valid_assignments)
            })
            
        except Exception as e:
            logger.error(f"Error cleaning up Redis: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/test-cleanup', methods=['POST'])
    def test_cleanup():
        """Test cleanup functionality without making changes."""
        try:
            movie_assignments = config.get_movie_assignments()
            
            # Check for orphaned assignments
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
                'message': 'Test cleanup completed (no changes made)',
                'total_assignments': len(movie_assignments),
                'valid_assignments': len(valid_assignments),
                'orphaned_assignments': len(orphaned_assignments),
                'orphaned_files': orphaned_assignments,
                'valid_files': valid_assignments
            })
            
        except Exception as e:
            logger.error(f"Error testing cleanup: {str(e)}")
            return jsonify({'error': str(e)}), 500
