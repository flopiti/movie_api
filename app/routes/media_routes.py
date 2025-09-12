#!/usr/bin/env python3
"""
Media paths management API routes.
"""

import os
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def register_media_routes(app, config):
    """Register media paths management routes with the Flask app."""
    
    @app.route('/media-paths', methods=['GET'])
    def get_media_paths():
        """Get all configured media paths with space information."""
        try:
            paths = config.get_media_paths()
            return jsonify({'paths': paths})
        except Exception as e:
            logger.error(f"Error getting media paths: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/media-paths', methods=['PUT'])
    def add_media_path():
        """Add a new media path."""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': 'Path is required'}), 400
            
            path = data['path']
            if not os.path.exists(path):
                return jsonify({'error': f'Path does not exist: {path}'}), 400
            
            if not os.path.isdir(path):
                return jsonify({'error': f'Path is not a directory: {path}'}), 400
            
            success = config.add_media_path(path)
            if success:
                return jsonify({'message': f'Media path added successfully: {path}'})
            else:
                return jsonify({'message': f'Media path already exists: {path}'})
                
        except Exception as e:
            logger.error(f"Error adding media path: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/media-paths', methods=['DELETE'])
    def remove_media_path():
        """Remove a media path."""
        try:
            data = request.get_json()
            if not data or 'path' not in data:
                return jsonify({'error': 'Path is required'}), 400
            
            path = data['path']
            success = config.remove_media_path(path)
            
            if success:
                return jsonify({'message': f'Media path removed successfully: {path}'})
            else:
                return jsonify({'error': f'Media path not found: {path}'}), 404
                
        except Exception as e:
            logger.error(f"Error removing media path: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/media-paths/refresh', methods=['POST'])
    def refresh_media_paths_space():
        """Refresh space information for all media paths."""
        try:
            data = request.get_json() or {}
            path = data.get('path')
            
            if path:
                # Refresh specific path
                updated_info = config.refresh_media_path_space(path)
                if updated_info:
                    return jsonify({
                        'message': f'Space information refreshed for path: {path}',
                        'path_info': updated_info
                    })
                else:
                    return jsonify({'error': f'Path not found: {path}'}), 404
            else:
                # Refresh all paths
                updated_paths = config.refresh_all_media_paths_space()
                return jsonify({
                    'message': f'Space information refreshed for {len(updated_paths)} media paths',
                    'paths': updated_paths
                })
                
        except Exception as e:
            logger.error(f"Error refreshing media paths space: {str(e)}")
            return jsonify({'error': str(e)}), 500
