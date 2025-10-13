#!/usr/bin/env python3
"""
File Management Routes
Routes for file operations, discovery, renaming, and management.
"""

import os
import sys
import shutil
from pathlib import Path
from flask import Blueprint, request, jsonify
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))
from config.config import config
from ..utils.file_discovery import FileDiscovery

# Create blueprint
files_bp = Blueprint('files', __name__)

@files_bp.route('/all-files', methods=['GET'])
def get_all_files():
    """Get all media files from all configured movie paths."""
    all_files = []
    paths = config.get_movie_paths() or []
    
    if not paths:
        return jsonify({
            'files': [],
            'count': 0,
            'message': 'No movie file paths configured'
        })
    
    # Get movie assignments
    movie_assignments = config.get_movie_assignments()

    # Debug: Show some example assignments
    if movie_assignments:
        sample_key = list(movie_assignments.keys())[0]
        sample_assignment = movie_assignments[sample_key]

    for path in paths:
        files = FileDiscovery.discover_files(path, movie_assignments)
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

@files_bp.route('/download-files', methods=['GET'])
def get_download_files():
    """Get all media files from download paths (flattened, no folders)."""
    try:
        files = config.get_download_files()
        return jsonify({
            'files': files,
            'count': len(files),
            'message': f'Found {len(files)} media files in download paths'
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get download files: {str(e)}'}), 500

@files_bp.route('/rename-file', methods=['POST'])
def rename_file():
    """Rename a movie file to standard format."""
    data = request.get_json()
    
    if not data or 'file_path' not in data or 'new_filename' not in data:
        return jsonify({'error': 'file_path and new_filename are required'}), 400
    
    current_path = data['file_path'].strip()
    new_filename = data['new_filename'].strip()
    
    if not current_path or not new_filename:
        return jsonify({'error': 'file_path and new_filename cannot be empty'}), 400
    
    try:
        current_file = Path(current_path)
        
        # Validate current file exists
        if not current_file.exists():
            return jsonify({'error': 'File does not exist'}), 404
        
        # Create new path with same directory but new filename
        new_path = current_file.parent / new_filename
        
        # Check if new filename already exists
        if new_path.exists():
            return jsonify({'error': 'A file with the new name already exists'}), 409
        
        # Perform the rename
        current_file.rename(new_path)
        
        # Update movie assignments if they exist - use batch update for better performance
        movie_assignments = config.get_movie_assignments()
        if current_path in movie_assignments:
            movie_data = movie_assignments[current_path]
            # Use batch update instead of individual calls
            config.batch_update_assignments([(current_path, str(new_path), movie_data)])

        return jsonify({
            'message': 'File renamed successfully',
            'old_path': current_path,
            'new_path': str(new_path),
            'new_filename': new_filename
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to rename file: {str(e)}'}), 500

@files_bp.route('/rename-folder', methods=['POST'])
def rename_folder():
    """Rename a movie folder to standard format."""
    data = request.get_json()
    
    if not data or 'folder_path' not in data or 'new_foldername' not in data:
        return jsonify({'error': 'folder_path and new_foldername are required'}), 400
    
    current_folder_path = data['folder_path'].strip()
    new_foldername = data['new_foldername'].strip()
    
    if not current_folder_path or not new_foldername:
        return jsonify({'error': 'folder_path and new_foldername cannot be empty'}), 400
    
    try:
        current_folder = Path(current_folder_path)
        
        # Validate current folder exists
        if not current_folder.exists():
            return jsonify({'error': 'Folder does not exist'}), 404
        
        if not current_folder.is_dir():
            return jsonify({'error': 'Path is not a directory'}), 400
        
        # Create new path with same parent but new folder name
        new_folder_path = current_folder.parent / new_foldername
        
        # Check if new folder name already exists
        if new_folder_path.exists():
            return jsonify({'error': 'A folder with the new name already exists'}), 409
        
        # Get all files in the folder that have movie assignments
        movie_assignments = config.get_movie_assignments()
        files_to_update = []
        
        for file_path, movie_data in movie_assignments.items():
            if file_path.startswith(current_folder_path):
                # Calculate the new file path after folder rename
                relative_path = Path(file_path).relative_to(current_folder)
                new_file_path = new_folder_path / relative_path
                files_to_update.append((file_path, str(new_file_path), movie_data))
        
        # Perform the folder rename
        current_folder.rename(new_folder_path)
        
        # Batch update all movie assignments that were in the renamed folder
        if files_to_update:
            config.batch_update_assignments(files_to_update)

        return jsonify({
            'message': 'Folder renamed successfully',
            'old_path': current_folder_path,
            'new_path': str(new_folder_path),
            'new_foldername': new_foldername,
            'updated_assignments': len(files_to_update)
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to rename folder: {str(e)}'}), 500

@files_bp.route('/delete-file', methods=['DELETE'])
def delete_file():
    """Delete a movie file from the filesystem."""
    data = request.get_json()
    
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path is required'}), 400
    
    file_path = data['file_path'].strip()
    
    if not file_path:
        return jsonify({'error': 'file_path cannot be empty'}), 400
    
    try:
        file_to_delete = Path(file_path)
        
        # Validate file exists
        if not file_to_delete.exists():
            return jsonify({'error': 'File does not exist'}), 404
        
        # Validate it's actually a file (not a directory)
        if not file_to_delete.is_file():
            return jsonify({'error': 'Path is not a file'}), 400
        
        # Check if it's a media file (safety check)
        if not FileDiscovery.is_media_file(file_to_delete):
            return jsonify({'error': 'File is not a supported media file'}), 400
        
        # Store file info before deletion for response
        file_name = file_to_delete.name
        file_size = file_to_delete.stat().st_size
        
        # Remove movie assignment if it exists
        movie_assignments = config.get_movie_assignments()
        had_assignment = file_path in movie_assignments
        if had_assignment:
            config.remove_movie_assignment(file_path)

        # Delete the file
        file_to_delete.unlink()

        return jsonify({
            'message': 'File deleted successfully',
            'file_path': file_path,
            'file_name': file_name,
            'file_size': file_size,
            'had_movie_assignment': had_assignment
        }), 200
        
    except PermissionError:
        pass
        return jsonify({'error': 'Permission denied. Cannot delete file.'}), 403
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500

@files_bp.route('/orphaned-files', methods=['GET'])
def find_orphaned_files():
    """Find files that are directly in movie paths and need to be moved to folders."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🔍 Starting orphaned files search...")
        
        # Test Redis connection first
        logger.info(f"🔧 Redis connection status: {config.use_redis}")
        if config.use_redis:
            try:
                # Try to get a simple value to test Redis
                test_data = config._get_redis_data()
                logger.info("✅ Redis connection successful")
            except Exception as redis_error:
                logger.error(f"❌ Redis connection failed: {str(redis_error)}")
        
        movie_paths = config.get_movie_paths() or []
        logger.info(f"📁 Found {len(movie_paths)} movie paths configured")
        logger.info(f"📁 Movie paths details: {movie_paths}")
        
        # Let's also check what's in Redis directly
        if config.use_redis:
            try:
                redis_data = config._get_redis_data()
                redis_movie_paths = redis_data.get("movie_file_paths", [])
                logger.info(f"🔍 Redis movie_file_paths: {redis_movie_paths}")
                logger.info(f"🔍 Redis data keys: {list(redis_data.keys())}")
            except Exception as redis_debug_error:
                logger.error(f"❌ Error checking Redis data: {str(redis_debug_error)}")
        
        # Check local fallback data
        local_movie_paths = config.data.get("movie_file_paths", [])
        logger.info(f"🔍 Local fallback movie_file_paths: {local_movie_paths}")
        
        orphaned_files = []
        
        for movie_path in movie_paths:
            logger.info(f"🔍 Checking movie path: {movie_path}")
            if os.path.exists(movie_path):
                logger.info(f"✅ Path exists, scanning for files...")
                try:
                    # Get all files directly in this path (not in subdirectories)
                    items = os.listdir(movie_path)
                    logger.info(f"📄 Found {len(items)} items in path")
                    
                    for item in items:
                        item_path = os.path.join(movie_path, item)
                        if os.path.isfile(item_path) and FileDiscovery.is_media_file(Path(item_path)):
                            logger.info(f"🎬 Found media file: {item}")
                            
                            # Check if this file has a movie assignment
                            try:
                                movie_assignments = config.get_movie_assignments()
                                logger.info(f"📋 Retrieved {len(movie_assignments)} movie assignments")
                                movie_data = movie_assignments.get(item_path)
                                
                                orphaned_files.append({
                                    'path': item_path,
                                    'name': item,
                                    'directory': movie_path,
                                    'size': os.path.getsize(item_path),
                                    'modified': int(os.path.getmtime(item_path)),
                                    'movie_assigned': bool(movie_data),
                                    'movie_title': movie_data.get('title', 'Unknown') if movie_data else None,
                                    'movie_id': movie_data.get('id') if movie_data else None
                                })
                                logger.info(f"✅ Added orphaned file: {item}")
                            except Exception as assignment_error:
                                logger.error(f"❌ Error getting movie assignments: {str(assignment_error)}")
                                raise
                except Exception as path_error:
                    logger.error(f"❌ Error scanning path {movie_path}: {str(path_error)}")
                    raise
            else:
                logger.warning(f"⚠️ Path does not exist: {movie_path}")

        logger.info(f"✅ Orphaned files search completed. Found {len(orphaned_files)} orphaned files")
        return jsonify({
            'orphaned_files': orphaned_files,
            'total_orphaned_files': len(orphaned_files)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Failed to find orphaned files: {str(e)}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to find orphaned files: {str(e)}'}), 500

@files_bp.route('/move-to-folder', methods=['POST'])
def move_to_folder():
    """Move a file into its own folder based on its movie assignment."""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data:
            return jsonify({'error': 'file_path is required'}), 400
        
        file_path = data['file_path']
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File does not exist'}), 404
        
        # Get movie assignment for this file
        movie_assignments = config.get_movie_assignments()
        movie_data = movie_assignments.get(file_path)
        
        if not movie_data:
            return jsonify({'error': 'File has no movie assignment'}), 400
        
        # Generate folder name from movie title
        movie_title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        # Clean title and add year if available
        import re
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '', movie_title.replace(' ', '_'))
        if release_date:
            year = release_date.split('-')[0]
            folder_name = f"{clean_title}_{year}"
        else:
            folder_name = clean_title
        
        # Create folder path
        file_dir = os.path.dirname(file_path)
        new_folder_path = os.path.join(file_dir, folder_name)
        
        # Create folder if it doesn't exist
        os.makedirs(new_folder_path, exist_ok=True)
        
        # Move file to new folder
        file_name = os.path.basename(file_path)
        new_file_path = os.path.join(new_folder_path, file_name)
        
        # Check if destination already exists
        if os.path.exists(new_file_path):
            return jsonify({'error': 'Destination file already exists'}), 409
        
        # Move the file
        os.rename(file_path, new_file_path)
        
        # Update movie assignment to new path
        config.remove_movie_assignment(file_path)
        config.assign_movie_to_file(new_file_path, movie_data)

        return jsonify({
            'message': 'File moved successfully',
            'old_path': file_path,
            'new_path': new_file_path,
            'folder_name': folder_name
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to move file: {str(e)}'}), 500

@files_bp.route('/move-file', methods=['POST'])
def move_file():
    """Move a download file to the appropriate movie path."""
    import logging
    logger = logging.getLogger("move_file")
    data = request.get_json()
    logger.info(f"Received move_file request: {data}")

    if not data or 'file_path' not in data or 'movie' not in data:
        logger.warning("Missing file_path or movie in request data")
        return jsonify({'error': 'file_path and movie are required'}), 400

    file_path = data['file_path'].strip()
    movie_data = data['movie']
    logger.info(f"Parsed file_path: {file_path}")
    logger.info(f"Parsed movie_data: {movie_data}")

    if not file_path:
        logger.warning("file_path is empty")
        return jsonify({'error': 'file_path cannot be empty'}), 400

    try:
        source_file = Path(file_path)
        logger.info(f"Source file resolved: {source_file}")

        # Validate source file exists
        if not source_file.exists():
            logger.error(f"Source file does not exist: {source_file}")
            return jsonify({'error': 'Source file does not exist'}), 404

        # Get movie paths to determine destination
        movie_paths = config.get_movie_paths() or []
        logger.info(f"Configured movie paths: {movie_paths}")
        if not movie_paths:
            logger.error("No movie paths configured")
            return jsonify({'error': 'No movie paths configured'}), 400

        # Choose the best destination path
        # Strategy: Use the path with the most available space, or first path if space info unavailable
        destination_path = None
        max_available_space = 0

        logger.info(f"Checking {len(movie_paths)} movie paths for available space:")

        for i, path in enumerate(movie_paths):
            try:
                # Get available space for this path
                statvfs = os.statvfs(path)
                available_space = statvfs.f_frsize * statvfs.f_bavail
                available_gb = available_space / (1024**3)

                logger.info(f"  Path {i+1}: {path}")
                logger.info(f"    Available space: {available_gb:.2f} GB")

                if available_space > max_available_space:
                    max_available_space = available_space
                    destination_path = Path(path)
                    logger.info(f"    ✓ New best choice!")
                else:
                    logger.info(f"    (not selected)")

            except (OSError, PermissionError) as e:
                logger.warning(f"  Path {i+1}: {path}")
                logger.warning(f"    Error checking space: {e}")
                # If we can't get space info, just use the first path
                if destination_path is None:
                    destination_path = Path(path)
                    logger.info(f"    ✓ Using as fallback choice")

        # Fallback to first path if no path was selected
        if destination_path is None:
            destination_path = Path(movie_paths[0])
            logger.info(f"Using fallback: {destination_path}")

        # Log final decision
        final_space_gb = max_available_space / (1024**3)
        logger.info(f"Final choice: {destination_path}")
        logger.info(f"Final available space: {final_space_gb:.2f} GB")

        # Generate destination folder name from movie data
        movie_title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        logger.info(f"Movie title: {movie_title}, release_date: {release_date}")

        # Clean title and add year if available
        import re
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '', movie_title.replace(' ', '_'))
        if release_date:
            year = release_date.split('-')[0]
            folder_name = f"{clean_title}_{year}"
        else:
            folder_name = clean_title
        logger.info(f"Destination folder name: {folder_name}")

        # Create destination folder
        destination_folder = destination_path / folder_name
        logger.info(f"Destination folder path: {destination_folder}")
        destination_folder.mkdir(parents=True, exist_ok=True)

        # Create destination file path
        destination_file = destination_folder / source_file.name
        logger.info(f"Destination file path: {destination_file}")

        # Check if destination already exists
        if destination_file.exists():
            logger.error(f"Destination file already exists: {destination_file}")
            return jsonify({'error': 'Destination file already exists'}), 409

        # Move the file
        logger.info(f"Moving file from {source_file} to {destination_file}")
        shutil.move(str(source_file), str(destination_file))
        logger.info("File move completed")

        # Update movie assignment to new path
        movie_assignments = config.get_movie_assignments()
        if file_path in movie_assignments:
            logger.info(f"Removing old movie assignment for {file_path}")
            config.remove_movie_assignment(file_path)

        # Add new assignment
        logger.info(f"Assigning movie to new file path: {destination_file}")
        config.assign_movie_to_file(str(destination_file), movie_data)

        logger.info("Move file operation successful")
        return jsonify({
            'message': 'File moved successfully',
            'old_path': file_path,
            'new_path': str(destination_file),
            'destination_folder': str(destination_folder),
            'movie_title': movie_title
        }), 200

    except Exception as e:
        logger.exception(f"Failed to move file: {str(e)}")
        return jsonify({'error': f'Failed to move file: {str(e)}'}), 500

@files_bp.route('/duplicates', methods=['GET'])
def find_duplicates():
    """Find files that are assigned to the same movie."""
    try:
        movie_assignments = config.get_movie_assignments()
        
        # Group files by movie ID to find duplicates
        movie_groups = {}
        for file_path, movie_data in movie_assignments.items():
            movie_id = movie_data.get('id')
            if movie_id:
                # ONLY include files that actually exist
                if os.path.exists(file_path):
                    if movie_id not in movie_groups:
                        movie_groups[movie_id] = {
                            'movie_info': {
                                'id': movie_id,
                                'title': movie_data.get('title', 'Unknown'),
                                'release_date': movie_data.get('release_date'),
                                'vote_average': movie_data.get('vote_average')
                            },
                            'files': []
                        }
                    
                    movie_groups[movie_id]['files'].append({
                        'path': file_path,
                        'name': os.path.basename(file_path),
                        'directory': os.path.dirname(file_path),
                        'size': os.path.getsize(file_path),
                        'modified': int(os.path.getmtime(file_path))
                    })
        
        # Filter to only include movies with multiple EXISTING files
        duplicates = {
            movie_id: group_data 
            for movie_id, group_data in movie_groups.items() 
            if len(group_data['files']) > 1
        }

        return jsonify({
            'duplicates': duplicates,
            'total_duplicate_movies': len(duplicates),
            'total_duplicate_files': sum(len(group['files']) for group in duplicates.values())
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to find duplicates: {str(e)}'}), 500
