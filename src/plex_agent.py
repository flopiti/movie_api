import logging
import time
import threading
from datetime import datetime
from config.config import OPENAI_API_KEY, TMDB_API_KEY
from ..clients.openai_client import OpenAIClient
from ..clients.tmdb_client import TMDBClient
from ..clients.PROMPTS import SMS_RESPONSE_PROMPT
from ..services.download_monitor import get_download_monitor
from ..services.movie_identification_service import MovieIdentificationService
from ..services.movie_library_service import MovieLibraryService
from ..services.radarr_service import RadarrService
from ..services.notification_service import NotificationService
from ..services.agentic_service import AgenticService

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
    
    def _process_agentic_response(self, conversation_history, phone_number):
        """Process agentic response with function calling support"""
        # Prepare services dictionary for the agentic service
        services = {
            'movie_identification': self.movie_identification_service,
            'movie_library': self.movie_library_service,
            'radarr': self.radarr_service,
            'notification': self.notification_service,
            'sms_response_prompt': self.sms_response_prompt
        }
        
        return self.agentic_service.process_agentic_response(conversation_history, phone_number, services)
    
    # =============================================================================
    # SERVICE WRAPPER METHODS - Delegate to appropriate services
    # =============================================================================
    
    def identify_movie_request(self, conversation_history):
        """Delegate to movie identification service"""
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
    
    def Answer(self, conversation_history, phone_number):
        """
        Original Answer method - procedural approach
        """
        # Validate input
        if not conversation_history:
            logger.error(f"❌ PlexAgent: No conversation history provided - this should not happen")
            return {
                'response_message': "I received your message but couldn't process it. Please try again.",
                'movie_result': None,
                'tmdb_result': None,
                'success': False
            }
        
        # Extract current message from the latest USER message in conversation history
        current_message = None
        for message in reversed(conversation_history):
            if message.startswith("USER: "):
                current_message = message.replace("USER: ", "")
                break
        
        # Step 1: Detect movie in conversation
        # Send last 10 messages (both USER and SYSTEM) instead of filtering to only USER messages
        last_10_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        
        movie_result = self.openai_client.getMovieName(last_10_messages)
        
        # Step 2: Search TMDB for the movie if detected
        tmdb_result, movie_data, radarr_status, release_status = self.get_movie(movie_result)
        
        # Step 3: Check movie status and handle accordingly
        movie_downloaded = False
        movie_status_message = ""
        
        if movie_data and tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
            # Check if movie is released
            if release_status and not release_status.get('is_released', True):
                # Movie is not released yet
                release_date = release_status.get('release_date_formatted', 'Unknown date')
                days_until = release_status.get('days_until_release', 0)
                if days_until:
                    movie_status_message = f" (Note: The movie '{movie_data.get('title')}' is not released yet. It will be available on {release_date} - {days_until} days from now)"
                else:
                    movie_status_message = f" (Note: The movie '{movie_data.get('title')}' is not released yet. Release date: {release_date})"
                logger.info(f"📅 PlexAgent: Movie not released yet: {movie_data.get('title')}")
            else:
                # Movie is released, check Radarr status
                if radarr_status and radarr_status.get('exists_in_radarr'):
                    if radarr_status.get('is_downloaded'):
                        # Movie is already downloaded
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' is already downloaded and available in your library)"
                        logger.info(f"✅ PlexAgent: Movie already downloaded: {movie_data.get('title')}")
                    elif radarr_status.get('is_downloading'):
                        # Movie is currently downloading
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' is already being downloaded)"
                        logger.info(f"📥 PlexAgent: Movie already downloading: {movie_data.get('title')}")
                        
                        # Create download request to monitor this already downloading movie
                        tmdb_id = movie_data.get('id')
                        release_date = movie_data.get('release_date', '')
                        year = release_date.split('-')[0] if release_date else 'Unknown year'
                        
                        logger.info(f"📱 PlexAgent: Creating download request to monitor already downloading movie: {movie_data.get('title')}")
                        download_request_created = self._get_download_monitor().add_download_request(
                            tmdb_id=tmdb_id,
                            movie_title=movie_data.get('title'),
                            movie_year=year,
                            phone_number=phone_number
                        )
                        
                        if download_request_created:
                            logger.info(f"✅ PlexAgent: Download request created for already downloading movie: {movie_data.get('title')}")
                        else:
                            logger.info(f"ℹ️ PlexAgent: Download request already exists for: {movie_data.get('title')}")
                    else:
                        # Movie exists in Radarr but not downloaded - trigger search and create download request
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' is already in your download queue - triggering search for available releases)"
                        logger.info(f"🔍 PlexAgent: Movie in Radarr but not downloaded, triggering search: {movie_data.get('title')}")
                        # Trigger search for the existing movie
                        if radarr_status.get('radarr_movie_id'):
                            self._get_download_monitor().radarr_client.search_for_movie(radarr_status['radarr_movie_id'])
                            
                            # Create download request to monitor this existing movie
                            tmdb_id = movie_data.get('id')
                            release_date = movie_data.get('release_date', '')
                            year = release_date.split('-')[0] if release_date else 'Unknown year'
                            
                            logger.info(f"📱 PlexAgent: Creating download request to monitor existing movie: {movie_data.get('title')}")
                            download_request_created = self._get_download_monitor().add_download_request(
                                tmdb_id=tmdb_id,
                                movie_title=movie_data.get('title'),
                                movie_year=year,
                                phone_number=phone_number
                            )
                            
                            if download_request_created:
                                logger.info(f"✅ PlexAgent: Download request created for existing movie: {movie_data.get('title')}")
                            else:
                                logger.info(f"ℹ️ PlexAgent: Download request already exists for: {movie_data.get('title')}")
                            
                            # Don't send notification yet - wait for download to actually start
                else:
                    # Movie not in Radarr, request download
                    logger.info(f"🔍 PlexAgent: Movie not in Radarr, requesting download for {movie_data.get('title')}")
                    movie_downloaded = self.request_movie_download(movie_data, phone_number)
                    logger.info(f"📱 PlexAgent: Download request result: {movie_downloaded}")
                    if movie_downloaded:
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' has been added to your download queue)"
                        logger.info(f"✅ PlexAgent: Successfully added {movie_data.get('title')} to download queue")
                        
                        # Don't send notification yet - wait for download to actually start
                    else:
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' could not be added to your download queue - it may already be requested or unavailable)"
                        logger.info(f"❌ PlexAgent: Failed to add {movie_data.get('title')} to download queue")
        
        # Step 4: Always generate GPT response with full context
        # Build comprehensive context about movie detection and download status
        movie_context = ""
        if movie_result and movie_result.get('success') and movie_result.get('movie_name') and movie_result.get('movie_name') != "No movie identified":
            if movie_status_message:
                # Use the detailed status message we built
                movie_context = movie_status_message
            elif tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
                # Fallback to basic message if no detailed status
                movie_data = tmdb_result['results'][0]
                release_date = movie_data.get('release_date', '')
                year = release_date.split('-')[0] if release_date else 'Unknown year'
                movie_context = f" (Note: A movie '{movie_data.get('title')} ({year})' was identified and found in our database)"
            else:
                movie_context = f" (Note: A movie '{movie_result['movie_name']}' was identified but not found in our database)"
        else:
            movie_context = " (Note: No movie was identified in the conversation)"
        
        if current_message and phone_number:
            chatgpt_result = self.openai_client.generate_sms_response(
                current_message, 
                phone_number, 
                self.sms_response_prompt,
                movie_context=movie_context
            )
            
            if chatgpt_result.get('success'):
                response_message = chatgpt_result['response']
            else:
                logger.error(f"❌ PlexAgent OpenAI Failed: {chatgpt_result.get('error', 'Unknown error')}")
                response_message = "I received your message but couldn't process it properly. Could you please specify which movie you'd like me to get?"
        else:
            logger.error(f"❌ PlexAgent: Could not extract current message or phone number from conversation history")
            response_message = "I received your message but couldn't process it properly. Could you please specify which movie you'd like me to get?"

        # Return the response data
        return {
            'response_message': response_message,
            'movie_result': movie_result,
            'tmdb_result': tmdb_result,
            'success': True
        }
    
    def AnswerAgentic(self, conversation_history, phone_number):
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
        
        logger.info(f"🎬 Agent: Processing agentic request from {phone_number}")
        
        # Use the new agentic processing method
        result = self._process_agentic_response(conversation_history, phone_number)
        
        return result
    
    def AnswerAgenticSimple(self, conversation_history, phone_number):
        """
        Simplified agentic approach - uses discrete functions but with simpler logic
        """
        # Validate input
        if not conversation_history:
            logger.error(f"❌ Agent: No conversation history provided")
            return {
                'response_message': "I received your message but couldn't process it. Please try again.",
                'success': False
            }
        
        # Extract current message
        current_message = None
        for message in reversed(conversation_history):
            if message.startswith("USER: "):
                current_message = message.replace("USER: ", "")
                break
        
        if not current_message:
            return {
                'response_message': "I received your message but couldn't process it properly.",
                'success': False
            }
        
        logger.info(f"🎬 Agent: Processing simple agentic request from {phone_number}: {current_message}")
        
        # Step 1: Try to identify movie using discrete function
        movie_identification = self.identify_movie_request(conversation_history)
        
        if movie_identification.get('success') and movie_identification.get('movie_name') != "No movie identified":
            movie_name = movie_identification['movie_name']
            logger.info(f"🎬 Agent: Movie identified: {movie_name}")
            
            # Step 2: Check library status
            library_status = self.check_movie_library_status(movie_name)
            
            if library_status.get('success'):
                movie_data = library_status['movie_data']
                release_status = library_status['release_status']
                
                # Step 3: Check if movie is released
                if release_status and not release_status.get('is_released', True):
                    # Movie not released
                    release_date = release_status.get('release_date_formatted', 'Unknown date')
                    days_until = release_status.get('days_until_release', 0)
                    if days_until:
                        response_message = f"The movie '{movie_data.get('title')}' isn't released yet. It comes out on {release_date} ({days_until} days from now)!"
                    else:
                        response_message = f"The movie '{movie_data.get('title')}' isn't released yet. Release date: {release_date}"
                else:
                    # Movie is released, check Radarr status
                    radarr_status = self.check_radarr_status(library_status['tmdb_id'], movie_data)
                    
                    if radarr_status.get('success'):
                        if radarr_status.get('exists_in_radarr'):
                            if radarr_status.get('is_downloaded'):
                                response_message = f"Great news! '{movie_data.get('title')}' is already downloaded and ready to watch!"
                            elif radarr_status.get('is_downloading'):
                                response_message = f"'{movie_data.get('title')}' is already downloading! I'll let you know when it's ready."
                                # Set up monitoring
                                self.request_download(movie_data, phone_number)
                            else:
                                response_message = f"'{movie_data.get('title')}' is in your queue but not downloading yet. I'll trigger a search for it!"
                                # Trigger search and set up monitoring
                                if radarr_status.get('radarr_movie_id'):
                                    self._get_download_monitor().radarr_client.search_for_movie(radarr_status['radarr_movie_id'])
                                self.request_download(movie_data, phone_number)
                        else:
                            # Movie not in Radarr - request download
                            download_request = self.request_download(movie_data, phone_number)
                            if download_request.get('success'):
                                response_message = f"Perfect! I'm adding '{movie_data.get('title')}' to your download queue. I'll text you when it starts downloading!"
                            else:
                                response_message = f"I couldn't add '{movie_data.get('title')}' to your queue right now. It might already be requested or unavailable."
                    else:
                        response_message = f"I found '{movie_data.get('title')}' but couldn't check your library status. Please try again later."
            else:
                # Movie not found in TMDB
                response_message = f"I couldn't find '{movie_name}' in our movie database. Could you check the spelling or try a different title?"
        else:
            # No movie identified - generate friendly response
            response_message = "Hi! I'd be happy to help you get a movie. Just tell me the name of the movie you'd like to watch!"
        
        # Ensure response is SMS-friendly
        if len(response_message) > 160:
            response_message = response_message[:157] + "..."
        
        return {
            'response_message': response_message,
            'movie_result': movie_identification,
            'success': True
        }

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
                                self._send_download_started_notification(request)
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
                                self._send_download_started_notification(request)
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
                            
                            # Send SMS notification
                            self._send_download_completed_notification(request)
                            
                            logger.info(f"📱 PlexAgent: Download completed for {request.movie_title}")
                            
                            # Remove from active monitoring and Redis
                            self._get_download_monitor().cancel_download_request(tmdb_id)
                            
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error checking download status: {str(e)}")
    
    def _send_download_started_notification(self, request):
        """Send SMS notification when download starts using agentic function"""
        self.notification_service.send_download_started_notification(request)
    
    def _send_download_completed_notification(self, request):
        """Send SMS notification when download completes using agentic function"""
        self.notification_service.send_download_completed_notification(request)

# Global instance
plex_agent = PlexAgent()