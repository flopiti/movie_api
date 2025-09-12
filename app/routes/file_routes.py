#!/usr/bin/env python3
"""
File management API routes.
"""

import os
import shutil
import logging
from flask import request, jsonify
from pathlib import Path

logger = logging.getLogger(__name__)

def register_file_routes(app, config, filename_formatter):
    """Register file management routes with the Flask app."""
    
    @app.route('/rename-file', methods=['POST'])
    def rename_file():
        """Rename a file to standard format."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            file_path = data.get('file_path')
            new_filename = data.get('new_filename')
            
            if not file_path:
                return jsonify({'error': 'file_path is required'}), 400
            
            if not new_filename:
                return jsonify({'error': 'new_filename is required'}), 400
            
            # Check if file exists
            if not os.path.exists(file_path):
                return jsonify({'error': f'File does not exist: {file_path}'}), 400
            
            # Get movie assignment
            movie_assignments = config.get_movie_assignments()
            movie_data = movie_assignments.get(file_path)
            
            if not movie_data:
                return jsonify({'error': 'No movie assignment found for this file'}), 400
            
            # Generate new file path
            file_dir = os.path.dirname(file_path)
            new_file_path = os.path.join(file_dir, new_filename)
            
            # Check if new file already exists
            if os.path.exists(new_file_path):
                return jsonify({'error': f'File already exists: {new_filename}'}), 400
            
            # Perform the rename
            try:
                shutil.move(file_path, new_file_path)
                logger.info(f"Renamed file: {file_path} -> {new_file_path}")
                
                # Update movie assignment with new path
                config.remove_movie_assignment(file_path)
                config.assign_movie_to_file(new_file_path, movie_data)
                
                return jsonify({
                    'message': f'File renamed successfully: {os.path.basename(file_path)} -> {new_filename}',
                    'old_path': file_path,
                    'new_path': new_file_path,
                    'movie': movie_data
                })
                
            except Exception as e:
                logger.error(f"Error renaming file: {str(e)}")
                return jsonify({'error': f'Failed to rename file: {str(e)}'}), 500
                
        except Exception as e:
            logger.error(f"Error in rename_file: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/rename-folder', methods=['POST'])
    def rename_folder():
        """Rename a folder to standard format."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            folder_path = data.get('folder_path')
            new_foldername = data.get('new_foldername')
            
            if not folder_path:
                return jsonify({'error': 'folder_path is required'}), 400
            
            if not new_foldername:
                return jsonify({'error': 'new_foldername is required'}), 400
            
            # Check if folder exists
            if not os.path.exists(folder_path):
                return jsonify({'error': f'Folder does not exist: {folder_path}'}), 400
            
            if not os.path.isdir(folder_path):
                return jsonify({'error': f'Path is not a directory: {folder_path}'}), 400
            
            # Generate new folder path
            parent_dir = os.path.dirname(folder_path)
            new_folder_path = os.path.join(parent_dir, new_foldername)
            
            # Check if new folder already exists
            if os.path.exists(new_folder_path):
                return jsonify({'error': f'Folder already exists: {new_foldername}'}), 400
            
            # Get all movie assignments that need to be updated
            movie_assignments = config.get_movie_assignments()
            files_to_update = []
            
            for file_path, movie_data in movie_assignments.items():
                if file_path.startswith(folder_path):
                    # Calculate new file path
                    relative_path = os.path.relpath(file_path, folder_path)
                    new_file_path = os.path.join(new_folder_path, relative_path)
                    files_to_update.append((file_path, new_file_path, movie_data))
            
            # Perform the folder rename
            try:
                shutil.move(folder_path, new_folder_path)
                logger.info(f"Renamed folder: {folder_path} -> {new_folder_path}")
                
                # Update all movie assignments
                updates = []
                for old_path, new_path, movie_data in files_to_update:
                    updates.append((old_path, new_path, movie_data))
                
                if updates:
                    config.batch_update_assignments(updates)
                
                return jsonify({
                    'message': f'Folder renamed successfully: {os.path.basename(folder_path)} -> {new_foldername}',
                    'old_path': folder_path,
                    'new_path': new_folder_path,
                    'files_updated': len(files_to_update)
                })
                
            except Exception as e:
                logger.error(f"Error renaming folder: {str(e)}")
                return jsonify({'error': f'Failed to rename folder: {str(e)}'}), 500
                
        except Exception as e:
            logger.error(f"Error in rename_folder: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/delete-file', methods=['DELETE'])
    def delete_file():
        """Delete a movie file."""
        try:
            data = request.get_json()
            if not data or 'file_path' not in data:
                return jsonify({'error': 'file_path is required'}), 400
            
            file_path = data['file_path']
            
            # Check if file exists
            if not os.path.exists(file_path):
                return jsonify({'error': f'File does not exist: {file_path}'}), 400
            
            # Get movie assignment for confirmation
            movie_assignments = config.get_movie_assignments()
            movie_data = movie_assignments.get(file_path)
            
            # Perform the deletion
            try:
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
                
                # Remove movie assignment
                if movie_data:
                    config.remove_movie_assignment(file_path)
                
                return jsonify({
                    'message': f'File deleted successfully: {os.path.basename(file_path)}',
                    'deleted_path': file_path,
                    'movie': movie_data
                })
                
            except Exception as e:
                logger.error(f"Error deleting file: {str(e)}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
                
        except Exception as e:
            logger.error(f"Error in delete_file: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/cleanup-orphaned-assignments', methods=['POST'])
    def cleanup_orphaned_assignments():
        """Clean up orphaned movie assignments (files that no longer exist)."""
        try:
            movie_assignments = config.get_movie_assignments()
            orphaned_assignments = []
            valid_assignments = []
            
            # Check each assignment
            for file_path, movie_data in movie_assignments.items():
                if os.path.exists(file_path):
                    valid_assignments.append(file_path)
                else:
                    orphaned_assignments.append(file_path)
            
            # Remove orphaned assignments
            removed_count = 0
            for file_path in orphaned_assignments:
                if config.remove_movie_assignment(file_path):
                    removed_count += 1
            
            logger.info(f"Cleanup completed: {removed_count} orphaned assignments removed out of {len(orphaned_assignments)} found")
            
            return jsonify({
                'message': f'Cleanup completed! Removed {removed_count} orphaned assignments out of {len(orphaned_assignments)} found.',
                'orphaned_assignments_found': len(orphaned_assignments),
                'assignments_removed': removed_count,
                'total_assignments_checked': len(movie_assignments),
                'valid_assignments_remaining': len(valid_assignments)
            })
            
        except Exception as e:
            logger.error(f"Error cleaning up orphaned assignments: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/orphaned-files', methods=['GET'])
    def find_orphaned_files():
        """Find files that are assigned to movies but don't exist."""
        try:
            movie_assignments = config.get_movie_assignments()
            orphaned_files = []
            
            for file_path, movie_data in movie_assignments.items():
                if not os.path.exists(file_path):
                    orphaned_files.append({
                        'file_path': file_path,
                        'movie': movie_data,
                        'movie_title': movie_data.get('title', 'Unknown'),
                        'movie_year': movie_data.get('release_date', '').split('-')[0] if movie_data.get('release_date') else ''
                    })
            
            # Sort by movie title
            orphaned_files.sort(key=lambda x: x['movie_title'].lower())
            
            return jsonify({
                'orphaned_files': orphaned_files,
                'total_count': len(orphaned_files)
            })
            
        except Exception as e:
            logger.error(f"Error finding orphaned files: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/move-to-folder', methods=['POST'])
    def move_to_folder():
        """Move an orphaned file to its own folder."""
        try:
            data = request.get_json()
            if not data or 'file_path' not in data:
                return jsonify({'error': 'file_path is required'}), 400
            
            file_path = data['file_path']
            
            # Get movie assignment
            movie_assignments = config.get_movie_assignments()
            movie_data = movie_assignments.get(file_path)
            
            if not movie_data:
                return jsonify({'error': 'No movie assignment found for this file'}), 400
            
            # Generate folder name based on movie data
            movie_title = movie_data.get('title', 'Unknown Movie')
            movie_year = movie_data.get('release_date', '').split('-')[0] if movie_data.get('release_date') else ''
            
            # Clean title for folder name
            clean_title = movie_title.replace(' ', '_').replace(':', '').replace('?', '').replace('*', '').replace('<', '').replace('>', '').replace('|', '').replace('"', '').replace('\\', '').replace('/', '')
            
            if movie_year:
                folder_name = f"{clean_title}_{movie_year}"
            else:
                folder_name = clean_title
            
            # Create new folder path
            file_dir = os.path.dirname(file_path)
            new_folder_path = os.path.join(file_dir, folder_name)
            
            # Create the folder
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                
                # Move the file
                filename = os.path.basename(file_path)
                new_file_path = os.path.join(new_folder_path, filename)
                
                shutil.move(file_path, new_file_path)
                
                # Update movie assignment
                config.remove_movie_assignment(file_path)
                config.assign_movie_to_file(new_file_path, movie_data)
                
                logger.info(f"Moved orphaned file to folder: {file_path} -> {new_file_path}")
                
                return jsonify({
                    'message': f'File moved to folder successfully: {folder_name}',
                    'old_path': file_path,
                    'new_path': new_file_path,
                    'folder_path': new_folder_path,
                    'movie': movie_data
                })
                
            except Exception as e:
                logger.error(f"Error moving file to folder: {str(e)}")
                return jsonify({'error': f'Failed to move file to folder: {str(e)}'}), 500
                
        except Exception as e:
            logger.error(f"Error in move_to_folder: {str(e)}")
            return jsonify({'error': str(e)}), 500
