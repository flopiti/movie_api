import logging
import time
import threading
from datetime import datetime
from config.config import OPENAI_API_KEY, TMDB_API_KEY
from ..clients.openai_client import OpenAIClient
from ..clients.tmdb_client import TMDBClient
from ..clients.PROMPTS import SMS_RESPONSE_PROMPT
from ..services.download_monitor import download_monitor
from ..clients.twilio_client import TwilioClient

logger = logging.getLogger(__name__)

class PlexAgent:
    """
    Agent responsible for processing SMS messages and handling movie-related requests.
    Detects movies in conversations, searches TMDB, and manages download requests.
    """
    
    def __init__(self):
        self.openai_client = OpenAIClient(OPENAI_API_KEY)
        self.tmdb_client = TMDBClient(TMDB_API_KEY)
        self.download_monitor = download_monitor
        self.sms_response_prompt = SMS_RESPONSE_PROMPT
        self.twilio_client = TwilioClient()
        
        # Download monitoring
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
    
    def get_movie(self, movie_result):
        """
        Service method to handle TMDB search for a detected movie.
        Returns TMDB result, movie data, Radarr status, and release status if found.
        """
        if not movie_result or not movie_result.get('success') or not movie_result.get('movie_name') or movie_result.get('movie_name') == "No movie identified":
            logger.info(f"🎬 PlexAgent: No movie identified in conversation")
            return None, None, None, None
        
        logger.info(f"🎬 PlexAgent: Movie detected: {movie_result['movie_name']}")
        
        # Search TMDB for the movie
        tmdb_result = self.tmdb_client.search_movie(movie_result['movie_name'])
        if not tmdb_result.get('results') or len(tmdb_result.get('results', [])) == 0:
            logger.info(f"🎬 PlexAgent: Movie not found in TMDB: {movie_result['movie_name']}")
            return tmdb_result, None, None, None
        
        movie_data = tmdb_result['results'][0]  # Get first result
        tmdb_id = movie_data.get('id')
        
        # Extract year from release_date (format: YYYY-MM-DD)
        release_date = movie_data.get('release_date', '')
        year = release_date.split('-')[0] if release_date else 'Unknown year'
        
        logger.info(f"🎬 PlexAgent: TMDB found movie: {movie_data.get('title')} ({year})")
        
        # Check Radarr status if Radarr is configured
        radarr_status = None
        if self.download_monitor.is_radarr_configured() and tmdb_id:
            logger.info(f"🔍 PlexAgent: Checking Radarr status for {movie_data.get('title')}")
            radarr_status = self.download_monitor.radarr_client.get_movie_status_by_tmdb_id(tmdb_id)
            logger.info(f"📱 PlexAgent: Radarr status: {radarr_status}")
        
        # Check release status
        release_status = self.tmdb_client.is_movie_released(movie_data)
        logger.info(f"📅 PlexAgent: Release status: {release_status}")
        
        return tmdb_result, movie_data, radarr_status, release_status
    
    def request_movie_download(self, movie_data, phone_number):
        """
        Service method to handle Radarr download requests.
        Returns binary success/failure status.
        """
        if not movie_data or not phone_number:
            logger.warning(f"⚠️ PlexAgent: Missing movie data or phone number for download request")
            return False
        
        # Extract year from release_date (format: YYYY-MM-DD)
        release_date = movie_data.get('release_date', '')
        year = release_date.split('-')[0] if release_date else 'Unknown year'
        tmdb_id = movie_data.get('id')
        
        logger.info(f"📱 PlexAgent: Adding download request for {movie_data.get('title')} ({year}) from {phone_number}")
        
        # Check if Radarr is configured first
        if not self.download_monitor.is_radarr_configured():
            logger.warning(f"⚠️ PlexAgent: Radarr not configured - cannot process download request for {movie_data.get('title')}")
            return False
        
        # Add download request to the monitor
        logger.info(f"📱 PlexAgent: Calling download_monitor.add_download_request for {movie_data.get('title')}")
        success = self.download_monitor.add_download_request(
            tmdb_id=tmdb_id,
            movie_title=movie_data.get('title'),
            movie_year=year,
            phone_number=phone_number
        )
        logger.info(f"📱 PlexAgent: download_monitor.add_download_request returned: {success}")
        
        if success:
            logger.info(f"✅ PlexAgent: Download request added successfully for {movie_data.get('title')}")
        else:
            logger.info(f"ℹ️ PlexAgent: Download request already exists for {movie_data.get('title')}")
        
        return success
    
    def Answer(self, conversation_history, phone_number):
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
                        download_request_created = self.download_monitor.add_download_request(
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
                            self.download_monitor.radarr_client.search_for_movie(radarr_status['radarr_movie_id'])
                            
                            # Create download request to monitor this existing movie
                            tmdb_id = movie_data.get('id')
                            release_date = movie_data.get('release_date', '')
                            year = release_date.split('-')[0] if release_date else 'Unknown year'
                            
                            logger.info(f"📱 PlexAgent: Creating download request to monitor existing movie: {movie_data.get('title')}")
                            download_request_created = self.download_monitor.add_download_request(
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
    
    def _store_outgoing_sms(self, phone_number: str, message: str, message_type: str = "notification") -> bool:
        """Store outgoing SMS message in Redis conversation"""
        try:
            from ..clients.redis_client import RedisClient
            redis_client = RedisClient()
            
            if not redis_client.is_available():
                logger.warning("📱 PlexAgent: Redis not available - cannot store outgoing SMS")
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
            
            success = redis_client.store_sms_message(message_data)
            if success:
                logger.info(f"📱 PlexAgent: Stored outgoing SMS in Redis conversation")
            else:
                logger.error(f"❌ PlexAgent: Failed to store outgoing SMS in Redis")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error storing outgoing SMS in Redis: {str(e)}")
            return False

    def _send_movie_added_notification(self, movie_data, phone_number):
        """Send SMS notification when movie is added to download queue"""
        try:
            from ..clients.twilio_client import TwilioClient
            twilio_client = TwilioClient()
            
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            message = f"🎬 Adding '{movie_data.get('title')}' ({year}) to your download queue. I'll let you know when it starts downloading!"
            
            result = twilio_client.send_sms(phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 PlexAgent: Sent movie added notification to {phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(phone_number, message, "movie_added")
            else:
                logger.error(f"❌ PlexAgent: Failed to send movie added notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error sending movie added notification: {str(e)}")
    
    def _send_search_triggered_notification(self, movie_data, phone_number):
        """Send SMS notification when search is triggered for existing movie"""
        try:
            from ..clients.twilio_client import TwilioClient
            twilio_client = TwilioClient()
            
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            message = f"🔍 Searching for '{movie_data.get('title')}' ({year}) releases. I'll let you know when download starts!"
            
            result = twilio_client.send_sms(phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 PlexAgent: Sent search triggered notification to {phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(phone_number, message, "search_triggered")
            else:
                logger.error(f"❌ PlexAgent: Failed to send search triggered notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error sending search triggered notification: {str(e)}")
    
    def start_monitoring(self):
        """Start the download monitoring service"""
        if self.monitoring:
            logger.warning("📱 PlexAgent: Already monitoring downloads")
            return
        
        # Start the DownloadMonitor service first
        self.download_monitor.start_monitoring()
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("📱 PlexAgent: Started download monitoring service")
    
    def stop_monitoring(self):
        """Stop the download monitoring service"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        # Stop the DownloadMonitor service
        self.download_monitor.stop_monitoring()
        
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
        if not self.download_monitor.radarr_client:
            return
        
        try:
            # Get current downloads from Radarr
            current_downloads = self.download_monitor.radarr_client.get_downloads()
            
            for tmdb_id, request in self.download_monitor.download_requests.items():
                
                if request.status in ["added_to_radarr", "queued", "downloading"] and request.radarr_movie_id:
                    
                    # Check if download has started
                    if request.status == "added_to_radarr":
                        # Check if movie is actually downloading (not just queued)
                        download_status = self.download_monitor.radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        if download_status and download_status.get('status', '').lower() == 'downloading':
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Update Redis with new status
                            self.download_monitor._store_download_request(request)
                            
                            # Send SMS notification (only if not already sent)
                            if not request.download_started_notification_sent:
                                self._send_download_started_notification(request)
                                request.download_started_notification_sent = True
                                # Update Redis again with notification flag
                                self.download_monitor._store_download_request(request)
                            
                            logger.info(f"📱 PlexAgent: Download started for {request.movie_title}")
                        elif download_status and download_status.get('status', '').lower() == 'queued':
                            # Movie is queued but not yet downloading - update status but don't notify yet
                            request.status = "queued"
                            logger.info(f"📱 PlexAgent: Movie {request.movie_title} is queued for download")
                        else:
                            pass  # Not yet downloading
                    
                    # Check if queued movie has started downloading
                    elif request.status == "queued":
                        download_status = self.download_monitor.radarr_client.get_download_status_for_movie(request.radarr_movie_id)
                        if download_status and download_status.get('status', '').lower() == 'downloading':
                            request.status = "downloading"
                            request.download_started_at = datetime.now()
                            
                            # Update Redis with new status
                            self.download_monitor._store_download_request(request)
                            
                            # Send SMS notification (only if not already sent)
                            if not request.download_started_notification_sent:
                                self._send_download_started_notification(request)
                                request.download_started_notification_sent = True
                                # Update Redis again with notification flag
                                self.download_monitor._store_download_request(request)
                            
                            logger.info(f"📱 PlexAgent: Download started for {request.movie_title}")
                        elif not download_status:
                            # No longer in queue - might have completed or failed
                            logger.info(f"📱 PlexAgent: Movie {request.movie_title} no longer in download queue")
                    
                    # Check if download has completed
                    elif request.status == "downloading":
                        if self.download_monitor.radarr_client.is_movie_downloaded(request.radarr_movie_id):
                            request.status = "completed"
                            request.download_completed_at = datetime.now()
                            
                            # Update Redis with completed status
                            self.download_monitor._store_download_request(request)
                            
                            # Send SMS notification
                            self._send_download_completed_notification(request)
                            
                            logger.info(f"📱 PlexAgent: Download completed for {request.movie_title}")
                            
                            # Remove from active monitoring and Redis
                            self.download_monitor.cancel_download_request(tmdb_id)
                            
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error checking download status: {str(e)}")
    
    def _send_download_started_notification(self, request):
        """Send SMS notification when download starts"""
        try:
            message = f"🎬 Great! I'm getting {request.movie_title} ({request.movie_year}) ready for you. I'll text you when it's ready to watch!"
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 PlexAgent: Sent download started notification to {request.phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(request.phone_number, message, "download_started")
            else:
                logger.error(f"❌ PlexAgent: Failed to send download started notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error sending download started notification: {str(e)}")
    
    def _send_download_completed_notification(self, request):
        """Send SMS notification when download completes"""
        try:
            message = f"🎉 {request.movie_title} ({request.movie_year}) is ready to watch! Enjoy your movie!"
            
            result = self.twilio_client.send_sms(request.phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 PlexAgent: Sent download completed notification to {request.phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(request.phone_number, message, "download_completed")
            else:
                logger.error(f"❌ PlexAgent: Failed to send download completed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error sending download completed notification: {str(e)}")

# Global instance
plex_agent = PlexAgent()