#!/usr/bin/env python3
"""
Radarr Service
Handles Radarr library status checks and download requests.
"""

import logging
from ..services.download_monitor import get_download_monitor

logger = logging.getLogger(__name__)

class RadarrService:
    """Service for managing Radarr operations"""
    
    def __init__(self):
        self.download_monitor = None  # Will be initialized lazily
    
    def _get_download_monitor(self):
        """Get download monitor instance, creating it if needed"""
        if self.download_monitor is None:
            self.download_monitor = get_download_monitor()
        return self.download_monitor
    
    def check_radarr_status(self, tmdb_id, movie_data):
        """
        Agentic function: Check if movie exists in user's Radarr library
        Returns detailed Radarr status including download state
        """
        try:
            if not tmdb_id or not movie_data:
                logger.warning(f"⚠️ RadarrService: Missing tmdb_id or movie_data for Radarr check")
                return {
                    'success': False,
                    'tmdb_id': tmdb_id,
                    'movie_title': movie_data.get('title') if movie_data else 'Unknown',
                    'error': 'Missing required parameters'
                }
            
            logger.info(f"🔍 RadarrService: Checking Radarr status for {movie_data.get('title')}")
            
            # Check if Radarr is configured first
            if not self._get_download_monitor().is_radarr_configured():
                logger.warning(f"⚠️ RadarrService: Radarr not configured")
                return {
                    'success': False,
                    'tmdb_id': tmdb_id,
                    'movie_title': movie_data.get('title'),
                    'radarr_status': None,
                    'error': 'Radarr not configured'
                }
            
            # Check Radarr status
            radarr_status = self._get_download_monitor().radarr_client.get_movie_status_by_tmdb_id(tmdb_id)
            logger.info(f"📱 RadarrService: Radarr status: {radarr_status}")
            
            return {
                'success': True,
                'tmdb_id': tmdb_id,
                'movie_title': movie_data.get('title'),
                'radarr_status': radarr_status,
                'exists_in_radarr': radarr_status.get('exists_in_radarr', False) if radarr_status else False,
                'is_downloaded': radarr_status.get('is_downloaded', False) if radarr_status else False,
                'is_downloading': radarr_status.get('is_downloading', False) if radarr_status else False,
                'radarr_movie_id': radarr_status.get('radarr_movie_id') if radarr_status else None
            }
            
        except Exception as e:
            logger.error(f"❌ RadarrService: Error checking Radarr status: {str(e)}")
            return {
                'success': False,
                'tmdb_id': tmdb_id,
                'movie_title': movie_data.get('title') if movie_data else 'Unknown',
                'error': str(e)
            }
    
    def request_download(self, movie_data, phone_number):
        """
        Agentic function: Add movie to download queue in Radarr
        Returns success/failure status and action taken
        """
        try:
            if not movie_data or not phone_number:
                logger.warning(f"⚠️ RadarrService: Missing movie data or phone number for download request")
                return {
                    'success': False,
                    'action': 'none',
                    'error': 'Missing movie data or phone number'
                }
            
            # Extract movie details
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            tmdb_id = movie_data.get('id')
            movie_title = movie_data.get('title')
            
            logger.info(f"📱 RadarrService: Processing download request for {movie_title} ({year}) from {phone_number}")
            
            # Check if Radarr is configured first
            if not self._get_download_monitor().is_radarr_configured():
                logger.warning(f"⚠️ RadarrService: Radarr not configured - cannot process download request")
                return {
                    'success': False,
                    'action': 'none',
                    'movie_title': movie_title,
                    'error': 'Radarr not configured'
                }
            
            # Add download request to the monitor
            success = self._get_download_monitor().add_download_request(
                tmdb_id=tmdb_id,
                movie_title=movie_title,
                movie_year=year,
                phone_number=phone_number
            )
            
            if success:
                logger.info(f"✅ RadarrService: Download request added successfully for {movie_title}")
                return {
                    'success': True,
                    'action': 'download_requested',
                    'movie_title': movie_title,
                    'movie_year': year,
                    'tmdb_id': tmdb_id
                }
            else:
                logger.info(f"ℹ️ RadarrService: Download request already exists for {movie_title}")
                return {
                    'success': True,
                    'action': 'already_requested',
                    'movie_title': movie_title,
                    'movie_year': year,
                    'tmdb_id': tmdb_id
                }
                
        except Exception as e:
            logger.error(f"❌ RadarrService: Error requesting download: {str(e)}")
            return {
                'success': False,
                'action': 'none',
                'movie_title': movie_data.get('title') if movie_data else 'Unknown',
                'error': str(e)
            }
    
    def request_movie_download(self, movie_data, phone_number):
        """
        Service method to handle Radarr download requests.
        Returns binary success/failure status.
        """
        if not movie_data or not phone_number:
            logger.warning(f"⚠️ RadarrService: Missing movie data or phone number for download request")
            return False
        
        # Extract year from release_date (format: YYYY-MM-DD)
        release_date = movie_data.get('release_date', '')
        year = release_date.split('-')[0] if release_date else 'Unknown year'
        tmdb_id = movie_data.get('id')
        
        logger.info(f"📱 RadarrService: Adding download request for {movie_data.get('title')} ({year}) from {phone_number}")
        
        # Check if Radarr is configured first
        if not self._get_download_monitor().is_radarr_configured():
            logger.warning(f"⚠️ RadarrService: Radarr not configured - cannot process download request for {movie_data.get('title')}")
            return False
        
        # Add download request to the monitor
        logger.info(f"📱 RadarrService: Calling download_monitor.add_download_request for {movie_data.get('title')}")
        success = self._get_download_monitor().add_download_request(
            tmdb_id=tmdb_id,
            movie_title=movie_data.get('title'),
            movie_year=year,
            phone_number=phone_number
        )
        logger.info(f"📱 RadarrService: download_monitor.add_download_request returned: {success}")
        
        if success:
            logger.info(f"✅ RadarrService: Download request added successfully for {movie_data.get('title')}")
        else:
            logger.info(f"ℹ️ RadarrService: Download request already exists for {movie_data.get('title')}")
        
        return success
