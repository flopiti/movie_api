#!/usr/bin/env python3
"""
File discovery utilities for finding media files.
"""

from pathlib import Path
from typing import List, Dict, Any

# Supported media file extensions
MEDIA_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.asf', '.rm', '.rmvb', '.vob', '.ts'
}

class FileDiscovery:
    """Handles recursive file discovery in movie directories."""
    
    @staticmethod
    def is_media_file(file_path: Path) -> bool:
        """Check if a file is a media file based on its extension."""
        return file_path.suffix.lower() in MEDIA_EXTENSIONS
    
    @staticmethod
    def discover_files(root_path: str, movie_assignments: Dict[str, Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recursively discover all media files in a directory."""
        files = []
        root = Path(root_path)
        
        if not root.exists():
            return files
        
        if movie_assignments is None:
            movie_assignments = {}
        
        try:
            for file_path in root.rglob('*'):
                if file_path.is_file() and FileDiscovery.is_media_file(file_path):
                    file_path_str = str(file_path)
                    file_info = {
                        'path': file_path_str,
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': file_path.stat().st_mtime,
                        'directory': str(file_path.parent)
                    }
                    
                    # Add movie assignment if it exists
                    if file_path_str in movie_assignments:
                        movie_data = movie_assignments[file_path_str]
                        file_info['movie'] = movie_data
                        
                        # Add filename information for existing assignments
                        from config import config
                        standard_filename = config._generate_standard_filename(movie_data, file_path_str)
                        current_filename = file_path.name
                        needs_rename = config._should_rename_file(file_path_str, standard_filename)
                        
                        # Add folder information for existing assignments
                        current_folder_path = str(file_path.parent)
                        standard_foldername = config._generate_standard_foldername(movie_data)
                        folder_needs_rename = config._should_rename_folder(current_folder_path, standard_foldername)
                        current_foldername = file_path.parent.name
                        
                        file_info['filenameInfo'] = {
                            'current_filename': current_filename,
                            'standard_filename': standard_filename,
                            'needs_rename': needs_rename
                        }
                        
                        file_info['folderInfo'] = {
                            'current_foldername': current_foldername,
                            'current_folder_path': current_folder_path,
                            'standard_foldername': standard_foldername,
                            'needs_rename': folder_needs_rename
                        }
                        
                    else:
                        # Debug: Check if this is a path normalization issue
                        if movie_assignments:
                            sample_key = list(movie_assignments.keys())[0]

                    files.append(file_info)
        except (PermissionError, OSError) as e:
            pass
        return files
