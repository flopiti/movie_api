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

from ..clients.radarr_client import RadarrClient
from ..clients.twilio_client import TwilioClient
from ..clients.redis_client import RedisClient
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))
from config.config import config

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
    status: str = "requested"  # requested, added_to_radarr, queued, downloading, completed, failed
    download_started_at: Optional[datetime] = None
    download_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    download_started_notification_sent: bool = False  # Track if notification was already sent

class DownloadMonitor:
    """Monitors movie downloads and sends SMS notifications"""
    
    def __init__(self):
        self.radarr_client = None
        self.twilio_client = TwilioClient()
        self.running = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
        
        # Initialize Redis client
        self.redis_client = RedisClient()
        
        # Initialize Radarr client
        self._init_radarr_client()
        
        # Track download requests
        self.download_requests: Dict[int, DownloadRequest] = {}  # tmdb_id -> DownloadRequest
        
    
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
            True if request was added successfully AND movie was added to Radarr, False otherwise
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
            
            # Store in Redis for persistence
            self._store_download_request(request)
            
            logger.info(f"📱 Download Monitor: Added download request for {movie_title} ({movie_year}) from {phone_number}")
            
            # Try to add movie to Radarr immediately and wait for result
            self._process_download_request(request)
            
            # Only return True if the movie was actually added to Radarr
            if request.status in ["added_to_radarr", "downloading"]:
                logger.info(f"✅ Download Monitor: Movie {movie_title} successfully added to Radarr")
                return True
            else:
                logger.warning(f"⚠️ Download Monitor: Movie {movie_title} could not be added to Radarr - status: {request.status}")
                return False
            
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
                'error_message': request.error_message,
                'download_started_notification_sent': request.download_started_notification_sent
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
                        error_message=data.get('error_message'),
                        download_started_notification_sent=data.get('download_started_notification_sent', False)
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
            self._store_download_request(request)
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
                    
                    # Send notification that movie is already downloading (only if not already sent)
                    if not request.download_started_notification_sent:
                        self._send_download_started_notification(request)
                        request.download_started_notification_sent = True
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
            
            # Update stored request
            self._store_download_request(request)
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error processing download request: {str(e)}")
            request.status = "failed"
            request.error_message = str(e)
            self._store_download_request(request)
    
    def _check_download_status(self):
        """Check download status for all active requests"""
        if not self.radarr_client:
            return
        
        try:
            # Get current downloads from Radarr
            current_downloads = self.radarr_client.get_downloads()
            
            for tmdb_id, request in self.download_requests.items():
                
                if request.status in ["added_to_radarr", "queued", "downloading"] and request.radarr_movie_id:
                    
                    # Check if download has started
                    if request.status == "added_to_radarr":
                        # Check if movie is actually downloading (not just queued)
                        download_status = self.radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        if download_status and download_status.get('status', '').lower() == 'downloading':
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Send SMS notification (only if not already sent)
                            if not request.download_started_notification_sent:
                                self._send_download_started_notification(request)
                                request.download_started_notification_sent = True
                            
                            logger.info(f"📱 Download Monitor: Download started for {request.movie_title}")
                        elif download_status and download_status.get('status', '').lower() == 'queued':
                            # Movie is queued but not yet downloading - update status but don't notify yet
                            request.status = "queued"
                            logger.info(f"📱 Download Monitor: Movie {request.movie_title} is queued for download")
                        else:
                            pass  # Not yet downloading
                    
                    # Check if queued movie has started downloading
                    elif request.status == "queued":
                        download_status = self.radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        if download_status and download_status.get('status', '').lower() == 'downloading':
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Send SMS notification (only if not already sent)
                            if not request.download_started_notification_sent:
                                self._send_download_started_notification(request)
                                request.download_started_notification_sent = True
                            
                            logger.info(f"📱 Download Monitor: Download started for {request.movie_title}")
                        elif not download_status:
                            # No longer in queue - might have completed or failed
                            logger.info(f"📱 Download Monitor: Movie {request.movie_title} no longer in download queue")
                    
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
                        else:
                            pass  # Still downloading
                    
                    # Update stored request
                    self._store_download_request(request)
                    
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error checking download status: {str(e)}")
    
    def _store_outgoing_sms(self, phone_number: str, message: str, message_type: str = "notification") -> bool:
        """Store outgoing SMS message in Redis conversation"""
        try:
            if not self.redis_client.is_available():
                logger.warning("📱 Download Monitor: Redis not available - cannot store outgoing SMS")
                return False
            
            # Prepare message data for Redis storage
            message_data = {
                'MessageSid': f"outgoing_{datetime.now().timestamp()}",
                'status': 'sent',
                'To': phone_number,
                'From': 'system',  # System-generated message
                'Body': message,
                'timestamp': datetime.now().isoformat(),
                'direction': 'outbound',
                'message_type': message_type
            }
            
            success = self.redis_client.store_sms_message(message_data)
            if success:
                logger.info(f"📱 Download Monitor: Stored outgoing SMS in Redis conversation")
            else:
                logger.error(f"❌ Download Monitor: Failed to store outgoing SMS in Redis")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error storing outgoing SMS in Redis: {str(e)}")
            return False

    def _send_download_started_notification(self, request: DownloadRequest):
        """Send SMS notification when download starts"""
        try:
            message = f"🎬 Great! I'm getting {request.movie_title} ({request.movie_year}) ready for you. I'll text you when it's ready to watch!"
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Download Monitor: Sent download started notification to {request.phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(request.phone_number, message, "download_started")
            else:
                logger.error(f"❌ Download Monitor: Failed to send download started notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error sending download started notification: {str(e)}")
    
    def _send_download_completed_notification(self, request: DownloadRequest):
        """Send SMS notification when download completes"""
        try:
            message = f"🎉 {request.movie_title} ({request.movie_year}) is ready to watch! Enjoy your movie!"
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Download Monitor: Sent download completed notification to {request.phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(request.phone_number, message, "download_completed")
            else:
                logger.error(f"❌ Download Monitor: Failed to send download completed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error sending download completed notification: {str(e)}")
    
    def _send_download_failed_notification(self, request: DownloadRequest):
        """Send SMS notification when download fails"""
        try:
            message = f"😔 Sorry, I couldn't get {request.movie_title} ({request.movie_year}) ready for you. {request.error_message or 'Please try again later.'}"
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Download Monitor: Sent download failed notification to {request.phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(request.phone_number, message, "download_failed")
            else:
                logger.error(f"❌ Download Monitor: Failed to send download failed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Download Monitor: Error sending download failed notification: {str(e)}")
    
    def start_monitoring(self):
        """Start the download monitoring service"""
        if self.running:
            logger.warning("📱 Download Monitor: Already running")
            return
        
        try:
            # Load existing download requests from Redis
            self._load_download_requests()
            
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("📱 Download Monitor: Started monitoring service")
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Failed to start monitoring service: {str(e)}")
            self.running = False
            raise
    
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
                'error_message': request.error_message,
                'download_started_notification_sent': request.download_started_notification_sent
            })
        
        return requests
    
    def clear_all_requests(self):
        """Clear all download requests from memory and Redis"""
        logger.info(f"🧹 Clearing {len(self.download_requests)} download requests from memory and Redis")
        
        # Clear from memory
        self.download_requests.clear()
        
        # Clear from Redis
        if self.redis_client:
            try:
                keys = self.redis_client.keys("download_request:*")
                if keys:
                    self.redis_client.delete(*keys)
                    logger.info(f"✅ Cleared {len(keys)} download requests from Redis")
                else:
                    logger.info("ℹ️ No download requests found in Redis")
            except Exception as e:
                logger.error(f"❌ Failed to clear Redis: {str(e)}")
        
        logger.info("✅ All download requests cleared")
    
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
    
    def cancel_download_request(self, tmdb_id: int) -> bool:
        """Cancel/remove a specific download request"""
        try:
            request = self.download_requests.get(tmdb_id)
            if not request:
                logger.warning(f"📱 Download Monitor: No download request found for TMDB ID {tmdb_id}")
                return False
            
            movie_title = request.movie_title
            movie_year = request.movie_year
            
            # Remove from memory
            del self.download_requests[tmdb_id]
            
            # Remove from Redis
            if self.redis_client:
                try:
                    redis_key = f"download_request:{tmdb_id}"
                    self.redis_client.delete(redis_key)
                    logger.info(f"✅ Removed download request for {movie_title} ({movie_year}) from Redis")
                except Exception as e:
                    logger.error(f"❌ Failed to remove from Redis: {str(e)}")
            
            logger.info(f"📱 Download Monitor: Cancelled download request for {movie_title} ({movie_year})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Download Monitor: Failed to cancel download request: {str(e)}")
            return False
    
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

# Global instance - lazy initialization
download_monitor = None

def get_download_monitor():
    """Get the global download monitor instance, creating it if needed"""
    global download_monitor
    if download_monitor is None:
        download_monitor = DownloadMonitor()
    return download_monitor
