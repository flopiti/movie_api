#!/usr/bin/env python3
"""
File discovery utilities for finding media files in directories.
"""

import os
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
                        
                        # Add filename and folder info
                        file_info['filenameInfo'] = FileDiscovery._generate_filename_info(movie_data, file_path_str)
                        file_info['folderInfo'] = FileDiscovery._generate_folder_info(movie_data, file_path_str)
                    
                    files.append(file_info)
                    
        except Exception as e:
            print(f"Error discovering files in {root_path}: {str(e)}")
        
        return files
    
    @staticmethod
    def _generate_filename_info(movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Generate filename information for a movie."""
        # Generate standard filename: Title_YYYY.extension
        title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        year = ''
        if release_date:
            try:
                year = release_date.split('-')[0]  # Extract year from YYYY-MM-DD format
            except Exception:
                # Ignore error
                pass
        
        # Clean title for filename
        clean_title = title.replace(' ', '_').replace(':', '').replace('?', '').replace('*', '').replace('<', '').replace('>', '').replace('|', '').replace('"', '').replace('\\', '').replace('/', '')
        
        # Get file extension
        file_extension = Path(file_path).suffix
        
        # Generate standard filename
        if year:
            standard_filename = f"{clean_title}_{year}{file_extension}"
        else:
            standard_filename = f"{clean_title}{file_extension}"
        
        return {
            'standard_filename': standard_filename,
            'should_rename': FileDiscovery._should_rename_file(Path(file_path).name, standard_filename)
        }
    
    @staticmethod
    def _generate_folder_info(movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Generate folder information for a movie."""
        title = movie_data.get('title', 'Unknown Movie')
        release_date = movie_data.get('release_date', '')
        
        year = ''
        if release_date:
            try:
                year = release_date.split('-')[0]  # Extract year from YYYY-MM-DD format
            except Exception:
                # Ignore error
                pass
        
        # Generate standard folder name
        if year:
            standard_foldername = f"{title} ({year})"
        else:
            standard_foldername = title
        
        # Get current folder path
        current_folder_path = str(Path(file_path).parent)
        current_foldername = Path(file_path).parent.name
        
        return {
            'standard_foldername': standard_foldername,
            'should_rename': FileDiscovery._should_rename_folder(current_foldername, standard_foldername)
        }
    
    @staticmethod
    def _should_rename_file(current_filename: str, standard_filename: str) -> bool:
        """Check if a file should be renamed."""
        return current_filename != standard_filename
    
    @staticmethod
    def _should_rename_folder(current_folder_path: str, standard_foldername: str) -> bool:
        """Check if a folder should be renamed."""
        current_foldername = Path(current_folder_path).name
        return current_foldername != standard_foldername
