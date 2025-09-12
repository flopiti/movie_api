#!/usr/bin/env python3
"""
System Routes
Routes for health checks, cleanup operations, and system utilities.
"""

import os
from flask import Blueprint, request, jsonify
from config import config, TMDB_API_KEY, OPENAI_API_KEY, redis_client

# Create blueprint
system_bp = Blueprint('system', __name__)

@system_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'movie_paths_count': len(config.get_movie_paths()),
        'tmdb_configured': bool(TMDB_API_KEY),
        'openai_configured': bool(OPENAI_API_KEY),
        'redis_configured': bool(redis_client),
        'redis_connection': config.use_redis,
        'storage_type': 'Redis' if config.use_redis else 'Local JSON',
        'plex_configured': True
    })

@system_bp.route('/cleanup-orphaned-assignments', methods=['POST'])
def cleanup_orphaned_assignments():
    """Remove all movie assignments for files that no longer exist."""
    try:
        # Get all current movie assignments
        movie_assignments = config.get_movie_assignments()

        orphaned_assignments = []
        removed_count = 0
        valid_assignments = []
        
        # Check each assignment
        for file_path, movie_data in movie_assignments.items():
            if os.path.exists(file_path):
                valid_assignments.append({
                    'file_path': file_path,
                    'movie_title': movie_data.get('title', 'Unknown'),
                    'movie_id': movie_data.get('id', 'Unknown')
                })
            else:
                orphaned_assignments.append({
                    'file_path': file_path,
                    'movie_title': movie_data.get('title', 'Unknown'),
                    'movie_id': movie_data.get('id', 'Unknown')
                })
                
                # Remove the assignment
                try:
                    result = config.remove_movie_assignment(file_path)
                    if result:
                        removed_count += 1
                    else:
                        pass
                except Exception as e:
                    pass
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
        pass
        return jsonify({'error': f'Failed to cleanup orphaned assignments: {str(e)}'}), 500

@system_bp.route('/debug-assignments', methods=['GET'])
def debug_assignments():
    """Debug endpoint to check current assignments."""
    try:
        assignments = config.get_movie_assignments()

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
        pass
        return jsonify({'error': f'Debug endpoint failed: {str(e)}'})

@system_bp.route('/test-cleanup', methods=['POST'])
def test_cleanup():
    """Test endpoint to manually trigger cleanup and see what happens."""
    try:
        # Get current assignments
        assignments = config.get_movie_assignments()

        # Find first orphaned assignment
        for file_path, movie_data in assignments.items():
            if not os.path.exists(file_path):
                # Try to remove it
                result = config.remove_movie_assignment(file_path)

                # Check if it was actually removed
                new_assignments = config.get_movie_assignments()

                return jsonify({
                    'test_file': file_path,
                    'remove_result': result,
                    'assignments_before': len(assignments),
                    'assignments_after': len(new_assignments),
                    'success': result and len(new_assignments) < len(assignments)
                })
        
        return jsonify({'message': 'No orphaned assignments found to test'})
        
    except Exception as e:
        pass
        return jsonify({'error': f'Test cleanup failed: {str(e)}'})

@system_bp.route('/redis-cleanup', methods=['POST'])
def redis_cleanup():
    """Trigger Redis cleanup to remove orphaned movie assignments."""
    try:
        # Get all current assignments
        assignments = config.get_movie_assignments()
        total_assignments = len(assignments)
        
        # Get all current files
        all_files = file_discovery.get_all_files()
        file_paths = {file_info['path'] for file_info in all_files['files']}
        
        # Find orphaned assignments
        orphaned_assignments = []
        for file_path in assignments.keys():
            if file_path not in file_paths:
                orphaned_assignments.append(file_path)
        
        orphaned_count = len(orphaned_assignments)
        valid_count = total_assignments - orphaned_count

        if orphaned_count > 0:
            for file_path in orphaned_assignments:
                config.remove_movie_assignment(file_path)
        else:
            pass

        return jsonify({
            'message': 'Redis cleanup completed successfully',
            'total_assignments': total_assignments,
            'valid_assignments': valid_count,
            'orphaned_assignments': orphaned_count,
            'removed_assignments': orphaned_count,
            'summary': f"Cleaned up {orphaned_count} orphaned assignments, {valid_count} valid assignments remaining"
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to cleanup Redis: {str(e)}'}), 500
