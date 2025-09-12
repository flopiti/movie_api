#!/usr/bin/env python3
"""
Download Monitor Service
Monitors movie downloads in Radarr and sends SMS notifications when downloads start.
"""

import os
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
import redis

from radarr_client import RadarrClient
from twilio_client import TwilioClient
from config import config

logger = logging.getLogger(__name__)

@dataclass
class DownloadRequest:
    """Represents a download request from SMS"""
    tmdb_id: int
    movie_title: str
    movie_year: str
    phone_number: str
    requested_at: datetime
    radarr_movie_id: Optional[int] = None
    status: str = "requested"  # requested, added_to_radarr, downloading, completed, failed
    download_started_at: Optional[datetime] = None
    download_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class DownloadMonitor:
    """Monitors movie downloads and sends SMS notifications"""
    
    def __init__(self):
        self.radarr_client = None
        self.twilio_client = TwilioClient()
        self.running = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
        
        # Initialize Redis for storing download requests
        self._init_redis()
        
        # Initialize Radarr client
        self._init_radarr_client()
        
        # Track download requests
        self.download_requests: Dict[int, DownloadRequest] = {}  # tmdb_id -> DownloadRequest
        
    def _init_redis(self):
        """Initialize Redis connection for storing download requests"""
        # Redis disabled - just using in-memory storage
        self.redis_client = None
        logger.info("ℹ️ Download Monitor: Redis disabled - using in-memory storage only")
    
    def _init_radarr_client(self):
        """Initialize Radarr client"""
        try:
            self.radarr_client = config.get_radarr_client()
            if self.radarr_client and self.radarr_client.test_connection():
                logger.info("✅ Download Monitor: Radarr connection established")
                
                # Log detailed Radarr configuration for debugging
                config_info = self.radarr_client.get_radarr_config_info()
                logger.info(f"🔧 Download Monitor: Radarr Config - {config_info}")
                
            else:
                self.radarr_client = None
                # Check if it's a configuration issue
                radarr_api_key = config.data.get('radarr_api_key', '')
                if not radarr_api_key:
                    logger.error("❌ Download Monitor: Radarr API key not configured. Please set RADARR_API_KEY environment variable or configure in settings.")
                else:
                    logger.error("❌ Download Monitor: Radarr connection failed - check URL and API key")
        except Exception as e:
            self.radarr_client = None
            logger.error(f"❌ Download Monitor: Radarr client initialization failed: {str(e)}")
    
    def add_download_request(self, tmdb_id: int, movie_title: str, movie_year: str, phone_number: str) -> bool:
        """
        Add a new download request
        
        Args:
            tmdb_id: TMDB movie ID
            movie_title: Movie title
            movie_year: Movie year
            phone_number: Phone number to notify
            
        Returns:
            True if request was added successfully, False otherwise
        """
        try:
            # Check if movie is already being requested
            if tmdb_id in self.download_requests:
                existing_request = self.download_requests[tmdb_id]
                logger.info(f"📱 Download Monitor: Movie {movie_title} ({movie_year}) already requested by {existing_request.phone_number}")
                return False
            
            # Create new download request
            request = DownloadRequest(
                tmdb_id=tmdb_id,
                movie_title=movie_title,
                movie_year=movie_year,
                phone_number=phone_number,
                requested_at=datetime.now()
            )
            
            # Store in memory
            self.download_requests[tmdb_id] = request
            
            # Store in memory only (Redis disabled)
            # self._store_download_request(request)
            
            logger.info(f"📱 Download Monitor: Added download request for {movie_title} ({movie_year}) from {phone_number}")
            
            # Try to add movie to Radarr immediately
            self._process_download_request(request)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Failed to add download request: {str(e)}")
            return False
    
    def _store_download_request(self, request: DownloadRequest):
        """Store download request in Redis"""
        if not self.redis_client:
            return
        
        try:
            import json
            request_data = {
                'tmdb_id': request.tmdb_id,
                'movie_title': request.movie_title,
                'movie_year': request.movie_year,
                'phone_number': request.phone_number,
                'requested_at': request.requested_at.isoformat(),
                'radarr_movie_id': request.radarr_movie_id,
                'status': request.status,
                'download_started_at': request.download_started_at.isoformat() if request.download_started_at else None,
                'download_completed_at': request.download_completed_at.isoformat() if request.download_completed_at else None,
                'error_message': request.error_message
            }
            
            redis_key = f"download_request:{request.tmdb_id}"
            self.redis_client.set(redis_key, json.dumps(request_data))
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Failed to store download request in Redis: {str(e)}")
    
    def _load_download_requests(self):
        """Load download requests from Redis"""
        if not self.redis_client:
            return
        
        try:
            import json
            keys = self.redis_client.keys("download_request:*")
            
            for key in keys:
                request_data = self.redis_client.get(key)
                if request_data:
                    data = json.loads(request_data)
                    
                    request = DownloadRequest(
                        tmdb_id=data['tmdb_id'],
                        movie_title=data['movie_title'],
                        movie_year=data['movie_year'],
                        phone_number=data['phone_number'],
                        requested_at=datetime.fromisoformat(data['requested_at']),
                        radarr_movie_id=data.get('radarr_movie_id'),
                        status=data['status'],
                        download_started_at=datetime.fromisoformat(data['download_started_at']) if data.get('download_started_at') else None,
                        download_completed_at=datetime.fromisoformat(data['download_completed_at']) if data.get('download_completed_at') else None,
                        error_message=data.get('error_message')
                    )
                    
                    self.download_requests[request.tmdb_id] = request
            
            logger.info(f"📱 Download Monitor: Loaded {len(self.download_requests)} download requests from Redis")
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Failed to load download requests from Redis: {str(e)}")
    
    def _process_download_request(self, request: DownloadRequest):
        """Process a download request by adding movie to Radarr"""
        if not self.radarr_client:
            logger.error("❌ Download Monitor: Radarr client not available - check configuration")
            request.status = "failed"
            request.error_message = "Radarr not configured - please check API key and URL settings"
            # self._store_download_request(request)  # Redis disabled
            return
        
        try:
            # Check if movie already exists in Radarr
            existing_movie = self.radarr_client.get_movie_by_tmdb_id(request.tmdb_id)
            
            if existing_movie:
                logger.info(f"📱 Download Monitor: Movie {request.movie_title} already exists in Radarr")
                request.radarr_movie_id = existing_movie['id']
                request.status = "added_to_radarr"
                
                # Check if it's already downloading
                if self.radarr_client.is_movie_downloading(existing_movie['id']):
                    request.status = "downloading"
                    request.download_started_at = datetime.now()
                    logger.info(f"📱 Download Monitor: Movie {request.movie_title} is already downloading")
                else:
                    # Trigger search for the movie
                    if self.radarr_client.search_for_movie(existing_movie['id']):
                        logger.info(f"📱 Download Monitor: Triggered search for {request.movie_title}")
                    else:
                        logger.error(f"❌ Download Monitor: Failed to trigger search for {request.movie_title}")
                
            else:
                # Add movie to Radarr using title and year search (skip TMDB ID)
                logger.info(f"📱 Download Monitor: Adding {request.movie_title} ({request.movie_year}) to Radarr using title search")
                
                added_movie = self.radarr_client.add_movie_by_title_and_year(
                    title=request.movie_title,
                    year=int(request.movie_year) if request.movie_year else 0,
                    monitored=True,
                    search_for_movie=True
                )
                
                if added_movie:
                    request.radarr_movie_id = added_movie['id']
                    request.status = "added_to_radarr"
                    logger.info(f"✅ Download Monitor: Successfully added {request.movie_title} ({request.movie_year}) to Radarr")
                else:
                    request.status = "failed"
                    request.error_message = "Failed to add movie to Radarr - title search failed"
                    logger.error(f"❌ Download Monitor: Failed to add {request.movie_title} ({request.movie_year}) to Radarr")
            
            # Update stored request (Redis disabled)
            # self._store_download_request(request)
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error processing download request: {str(e)}")
            request.status = "failed"
            request.error_message = str(e)
            # self._store_download_request(request)  # Redis disabled
    
    def _check_download_status(self):
        """Check download status for all active requests"""
        if not self.radarr_client:
            return
        
        try:
            for tmdb_id, request in self.download_requests.items():
                if request.status in ["added_to_radarr", "downloading"] and request.radarr_movie_id:
                    
                    # Check if download has started
                    if request.status == "added_to_radarr":
                        if self.radarr_client.is_movie_downloading(request.radarr_movie_id):
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Send SMS notification
                            self._send_download_started_notification(request)
                            
                            logger.info(f"📱 Download Monitor: Download started for {request.movie_title}")
                    
                    # Check if download has completed
                    elif request.status == "downloading":
                        download_status = self.radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        
                        if not download_status:
                            # Download completed (no longer in queue)
                            request.status = "completed"
                            request.download_completed_at = datetime.now()
                            
                            # Send SMS notification
                            self._send_download_completed_notification(request)
                            
                            logger.info(f"📱 Download Monitor: Download completed for {request.movie_title}")
                        
                        elif download_status.get('status') == 'failed':
                            request.status = "failed"
                            request.error_message = download_status.get('errorMessage', 'Download failed')
                            
                            # Send SMS notification
                            self._send_download_failed_notification(request)
                            
                            logger.error(f"❌ Download Monitor: Download failed for {request.movie_title}")
                    
                    # Update stored request
                    # self._store_download_request(request)  # Redis disabled
                    
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error checking download status: {str(e)}")
    
    def _send_download_started_notification(self, request: DownloadRequest):
        """Send SMS notification when download starts"""
        try:
            message = f"🎬 Download started for {request.movie_title} ({request.movie_year})! I'll let you know when it's ready."
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Download Monitor: Sent download started notification to {request.phone_number}")
            else:
                logger.error(f"❌ Download Monitor: Failed to send download started notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error sending download started notification: {str(e)}")
    
    def _send_download_completed_notification(self, request: DownloadRequest):
        """Send SMS notification when download completes"""
        try:
            message = f"✅ {request.movie_title} ({request.movie_year}) is ready! The movie has been downloaded and added to your library."
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Download Monitor: Sent download completed notification to {request.phone_number}")
            else:
                logger.error(f"❌ Download Monitor: Failed to send download completed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error sending download completed notification: {str(e)}")
    
    def _send_download_failed_notification(self, request: DownloadRequest):
        """Send SMS notification when download fails"""
        try:
            message = f"❌ Sorry, the download for {request.movie_title} ({request.movie_year}) failed. {request.error_message or 'Please try again later.'}"
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Download Monitor: Sent download failed notification to {request.phone_number}")
            else:
                logger.error(f"❌ Download Monitor: Failed to send download failed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error sending download failed notification: {str(e)}")
    
    def start_monitoring(self):
        """Start the download monitoring service"""
        if self.running:
            logger.warning("📱 Download Monitor: Already running")
            return
        
        # Load existing download requests from Redis (disabled)
        # self._load_download_requests()
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("📱 Download Monitor: Started monitoring service")
    
    def stop_monitoring(self):
        """Stop the download monitoring service"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("📱 Download Monitor: Stopped monitoring service")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self._check_download_status()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Download Monitor: Error in monitoring loop: {str(e)}")
                time.sleep(self.check_interval)
    
    def get_download_requests(self) -> List[Dict[str, Any]]:
        """Get all download requests"""
        requests = []
        for request in self.download_requests.values():
            requests.append({
                'tmdb_id': request.tmdb_id,
                'movie_title': request.movie_title,
                'movie_year': request.movie_year,
                'phone_number': request.phone_number,
                'requested_at': request.requested_at.isoformat(),
                'radarr_movie_id': request.radarr_movie_id,
                'status': request.status,
                'download_started_at': request.download_started_at.isoformat() if request.download_started_at else None,
                'download_completed_at': request.download_completed_at.isoformat() if request.download_completed_at else None,
                'error_message': request.error_message
            })
        
        return requests
    
    def get_download_request(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific download request"""
        request = self.download_requests.get(tmdb_id)
        if request:
            return {
                'tmdb_id': request.tmdb_id,
                'movie_title': request.movie_title,
                'movie_year': request.movie_year,
                'phone_number': request.phone_number,
                'requested_at': request.requested_at.isoformat(),
                'radarr_movie_id': request.radarr_movie_id,
                'status': request.status,
                'download_started_at': request.download_started_at.isoformat() if request.download_started_at else None,
                'download_completed_at': request.download_completed_at.isoformat() if request.download_completed_at else None,
                'error_message': request.error_message
            }
        return None
    
    def is_radarr_configured(self) -> bool:
        """Check if Radarr is properly configured"""
        try:
            radarr_api_key = config.data.get('radarr_api_key', '')
            radarr_url = config.data.get('radarr_url', '')
            return bool(radarr_api_key and radarr_url)
        except Exception:
            return False
    
    def get_radarr_config_status(self) -> Dict[str, Any]:
        """Get Radarr configuration status"""
        try:
            radarr_api_key = config.data.get('radarr_api_key', '')
            radarr_url = config.data.get('radarr_url', '')
            
            return {
                'configured': bool(radarr_api_key and radarr_url),
                'url': radarr_url,
                'api_key_set': bool(radarr_api_key),
                'client_available': self.radarr_client is not None,
                'connection_test': self.radarr_client.test_connection() if self.radarr_client else False
            }
        except Exception as e:
            return {
                'configured': False,
                'url': '',
                'api_key_set': False,
                'client_available': False,
                'connection_test': False,
                'error': str(e)
            }

# Global instance
download_monitor = DownloadMonitor()
