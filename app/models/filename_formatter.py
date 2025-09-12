#!/usr/bin/env python3
"""
Utility class for formatting movie filenames and folder names to standard format.
"""

from pathlib import Path
from typing import Dict, Any

class FilenameFormatter:
    """Utility class for formatting movie filenames and folder names to standard format."""
    
    @staticmethod
    def generate_standard_filename(movie_data: Dict[str, Any], original_filename: str) -> str:
        """Generate a standard filename format: Title_YYYY.extension"""
        title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        # Extract year from release date
        year = ''
        if release_date:
            try:
                year = release_date.split('-')[0]  # Extract year from YYYY-MM-DD format
            except (IndexError, ValueError):
                pass
        
        # Clean title: remove special characters and replace spaces with underscores
        clean_title = title.replace(' ', '_')
        clean_title = ''.join(c for c in clean_title if c.isalnum() or c in '_-')
        
        # Extract original file extension
        original_path = Path(original_filename)
        extension = original_path.suffix.lower()
        
        # Build standard filename
        if year:
            standard_filename = f"{clean_title}_{year}{extension}"
        else:
            standard_filename = f"{clean_title}{extension}"
        
        return standard_filename
    
    @staticmethod
    def generate_standard_foldername(movie_data: Dict[str, Any]) -> str:
        """Generate a standard folder name format: Title_YYYY"""
        title = movie_data.get('title', 'Unknown_Movie')
        release_date = movie_data.get('release_date', '')
        
        # Extract year from release date
        year = ''
        if release_date:
            try:
                year = release_date.split('-')[0]  # Extract year from YYYY-MM-DD format
            except (IndexError, ValueError):
                pass
        
        # Clean title: remove special characters and replace spaces with underscores
        clean_title = title.replace(' ', '_')
        clean_title = ''.join(c for c in clean_title if c.isalnum() or c in '_-')
        
        # Build standard folder name
        if year:
            standard_foldername = f"{clean_title}_{year}"
        else:
            standard_foldername = clean_title
        
        return standard_foldername
    
    @staticmethod
    def should_rename_file(current_filename: str, standard_filename: str) -> bool:
        """Check if a file should be renamed."""
        return current_filename != standard_filename
    
    @staticmethod
    def should_rename_folder(current_folder_path: str, standard_foldername: str) -> bool:
        """Check if a folder should be renamed."""
        current_foldername = Path(current_folder_path).name
        return current_foldername != standard_foldername

    @staticmethod
    def generate_filename_info(movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
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
            'should_rename': FilenameFormatter.should_rename_file(Path(file_path).name, standard_filename)
        }
    
    @staticmethod
    def generate_folder_info(movie_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
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
            'should_rename': FilenameFormatter.should_rename_folder(current_foldername, standard_foldername)
        }
