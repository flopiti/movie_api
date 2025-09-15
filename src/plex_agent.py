import logging
import time
import threading
from datetime import datetime
from config.config import OPENAI_API_KEY, TMDB_API_KEY
from src.clients.openai_client import OpenAIClient
from src.clients.tmdb_client import TMDBClient
from src.clients.PROMPTS import SMS_RESPONSE_PROMPT
from src.services.download_monitor import get_download_monitor
from src.services.movie_identification_service import MovieIdentificationService
from src.services.movie_library_service import MovieLibraryService
from src.services.radarr_service import RadarrService
from src.services.notification_service import NotificationService
from src.services.agentic_service import AgenticService

logger = logging.getLogger(__name__)

class PlexAgent:
    """
    Agent responsible for processing SMS messages and handling movie-related requests.
    Detects movies in conversations, searches TMDB, and manages download requests.
    """
    
    def __init__(self):
        self.openai_client = OpenAIClient(OPENAI_API_KEY)
        self.tmdb_client = TMDBClient(TMDB_API_KEY)
        self.download_monitor = None  # Will be initialized lazily
        self.sms_response_prompt = SMS_RESPONSE_PROMPT
        
        # Initialize services
        self.movie_identification_service = MovieIdentificationService(self.openai_client)
        self.movie_library_service = MovieLibraryService(self.tmdb_client)
        self.radarr_service = RadarrService()
        self.notification_service = NotificationService()
        self.agentic_service = AgenticService(self.openai_client)
        
        # Download monitoring
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
    
    def _get_download_monitor(self):
        """Get download monitor instance, creating it if needed"""
        if self.download_monitor is None:
            self.download_monitor = get_download_monitor()
        return self.download_monitor
    
    def _process_agentic_response(self, conversation_history):
        """Process agentic response with function calling support"""
        # Prepare services dictionary for the agentic service
        services = {
            'movie_identification': self.movie_identification_service,
            'movie_library': self.movie_library_service,
            'radarr': self.radarr_service,
            'notification': self.notification_service,
            'sms_response_prompt': self.sms_response_prompt
        }
        
        return self.agentic_service.process_agentic_response(conversation_history, services)
    
    # =============================================================================
    # SERVICE WRAPPER METHODS - Delegate to appropriate services
    # =============================================================================
    
    def identify_movie_request(self, conversation_history):
        """Delegate to movie identification service"""


        print('conversation_history line 69')
        return self.movie_identification_service.identify_movie_request(conversation_history)
    
    def check_movie_library_status(self, movie_name):
        """Delegate to movie library service"""
        return self.movie_library_service.check_movie_library_status(movie_name)
    
    def check_radarr_status(self, tmdb_id, movie_data):
        """Delegate to radarr service"""
        return self.radarr_service.check_radarr_status(tmdb_id, movie_data)
    
    def request_download(self, movie_data, phone_number):
        """Delegate to radarr service"""
        return self.radarr_service.request_download(movie_data, phone_number)
    
    def send_notification(self, phone_number, message_type, movie_data, additional_context=""):
        """Delegate to notification service"""
        return self.notification_service.send_notification(phone_number, message_type, movie_data, additional_context)
    
    def get_movie(self, movie_result):
        """
        Service method to handle TMDB search for a detected movie.
        Returns TMDB result, movie data, Radarr status, and release status if found.
        """
        # Use the movie library service
        tmdb_result, movie_data, _, release_status = self.movie_library_service.get_movie(movie_result)
        
        # Check Radarr status if Radarr is configured and we have movie data
        radarr_status = None
        if movie_data and self._get_download_monitor().is_radarr_configured():
            tmdb_id = movie_data.get('id')
            logger.info(f"🔍 PlexAgent: Checking Radarr status for {movie_data.get('title')}")
            radarr_status = self._get_download_monitor().radarr_client.get_movie_status_by_tmdb_id(tmdb_id)
            logger.info(f"📱 PlexAgent: Radarr status: {radarr_status}")
        
        return tmdb_result, movie_data, radarr_status, release_status
    
    def request_movie_download(self, movie_data, phone_number):
        """
        Service method to handle Radarr download requests.
        Returns binary success/failure status.
        """
        return self.radarr_service.request_movie_download(movie_data, phone_number)
    
    
    def AnswerAgentic(self, conversation_history):
        """
        Agentic Answer method using OpenAI function calling for dynamic decision making
        """
        # Validate input
        if not conversation_history:
            logger.error(f"❌ Agent: No conversation history provided")
            return {
                'response_message': "I received your message but couldn't process it. Please try again.",
                'success': False
            }
        
        # Use the new agentic processing method
        result = self._process_agentic_response(conversation_history)
        
        return result
    

    def _send_movie_added_notification(self, movie_data, phone_number):
        """Send SMS notification when movie is added to download queue"""
        self.notification_service.send_movie_added_notification(movie_data, phone_number)
    
    def _send_search_triggered_notification(self, movie_data, phone_number):
        """Send SMS notification when search is triggered for existing movie"""
        self.notification_service.send_search_triggered_notification(movie_data, phone_number)
    
    def start_monitoring(self):
        """Start the download monitoring service"""
        if self.monitoring:
            logger.warning("📱 PlexAgent: Already monitoring downloads")
            return
        
        try:
            # Start the DownloadMonitor service first
            self._get_download_monitor().start_monitoring()
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("📱 PlexAgent: Started download monitoring service")
            
        except Exception as e:
            logger.error(f"❌ PlexAgent: Failed to start monitoring service: {str(e)}")
            raise
    
    def stop_monitoring(self):
        """Stop the download monitoring service"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        # Stop the DownloadMonitor service
        self._get_download_monitor().stop_monitoring()
        
        logger.info("📱 PlexAgent: Stopped download monitoring service")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self._check_download_status()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ PlexAgent: Error in monitoring loop: {str(e)}")
                time.sleep(self.check_interval)
    
    def _check_download_status(self):
        """Check download status for all active requests"""
        if not self._get_download_monitor().radarr_client:
            return
        
        try:
            # Get current downloads from Radarr
            current_downloads = self._get_download_monitor().radarr_client.get_downloads()
            
            for tmdb_id, request in self._get_download_monitor().download_requests.items():
                
                if request.status in ["added_to_radarr", "queued", "downloading"] and request.radarr_movie_id:
                    
                    # Check if download has started
                    if request.status == "added_to_radarr":
                        # Check if movie is actually downloading (not just queued)
                        download_status = self._get_download_monitor().radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        if download_status and download_status.get('status', '').lower() == 'downloading':
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Update Redis with new status
                            self._get_download_monitor()._store_download_request(request)
                            
                            # Send SMS notification (only if not already sent)
                            if not request.download_started_notification_sent:
                                self._send_download_status_notification(request, "download_started")
                                request.download_started_notification_sent = True
                                # Update Redis again with notification flag
                                self._get_download_monitor()._store_download_request(request)
                            
                            logger.info(f"📱 PlexAgent: Download started for {request.movie_title}")
                        elif download_status and download_status.get('status', '').lower() == 'queued':
                            # Movie is queued but not yet downloading - update status but don't notify yet
                            request.status = "queued"
                            logger.info(f"📱 PlexAgent: Movie {request.movie_title} is queued for download")
                        else:
                            pass  # Not yet downloading
                    
                    # Check if queued movie has started downloading
                    elif request.status == "queued":
                        download_status = self._get_download_monitor().radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        if download_status and download_status.get('status', '').lower() == 'downloading':
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Update Redis with new status
                            self._get_download_monitor()._store_download_request(request)
                            
                            # Send SMS notification (only if not already sent)
                            if not request.download_started_notification_sent:
                                self._send_download_status_notification(request, "download_started")
                                request.download_started_notification_sent = True
                                # Update Redis again with notification flag
                                self._get_download_monitor()._store_download_request(request)
                            
                            logger.info(f"📱 PlexAgent: Download started for {request.movie_title}")
                        elif not download_status:
                            # No longer in queue - might have completed or failed
                            logger.info(f"📱 PlexAgent: Movie {request.movie_title} no longer in download queue")
                    
                    # Check if download has completed
                    elif request.status == "downloading":
                        if self._get_download_monitor().radarr_client.is_movie_downloaded(request.radarr_movie_id):
                            request.status = "completed"
                            request.download_completed_at = datetime.now()
                            
                            # Update Redis with completed status
                            self._get_download_monitor()._store_download_request(request)
                            
                            # Send SMS notification via agentic system
                            self._send_download_status_notification(request, "download_completed")
                            
                            logger.info(f"📱 PlexAgent: Download completed for {request.movie_title}")
                            
                            # Remove from active monitoring and Redis
                            self._get_download_monitor().cancel_download_request(tmdb_id)
                            
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error checking download status: {str(e)}")
    
    def _send_download_status_notification(self, request, status_type):
        """Send SMS notification for download status changes using agentic system"""
        try:
            # Create a conversation context for the agentic system
            movie_data = {
                'title': request.movie_title,
                'year': request.movie_year,
                'id': request.tmdb_id
            }
            
            # Create a simple conversation history for the agentic system
            conversation_history = [
                f"Download status update: {request.movie_title} ({request.movie_year}) - {status_type}"
            ]
            
            # Use agentic system to generate and send notification
            result = self._process_agentic_response(conversation_history)
            
            if result.get('success'):
                logger.info(f"📱 PlexAgent: Sent {status_type} notification via agentic system")
            else:
                logger.error(f"❌ PlexAgent: Failed to send {status_type} notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error sending {status_type} notification: {str(e)}")
    
    def _send_download_started_notification(self, request):
        """Send SMS notification when download starts using agentic function"""
        self.notification_service.send_download_started_notification(request)
    
    def _send_download_completed_notification(self, request):
        """Send SMS notification when download completes using agentic function"""
        self.notification_service.send_download_completed_notification(request)

# Global instance
plex_agent = PlexAgent()