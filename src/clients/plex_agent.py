import logging
from datetime import datetime
from config.config import OPENAI_API_KEY, TMDB_API_KEY
from ..clients.openai_client import OpenAIClient
from ..clients.tmdb_client import TMDBClient
from ..clients.PROMPTS import SMS_RESPONSE_PROMPT
from ..services.download_monitor import download_monitor

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
                    else:
                        # Movie exists in Radarr but not downloaded - trigger search
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' is already in your download queue - triggering search for available releases)"
                        logger.info(f"🔍 PlexAgent: Movie in Radarr but not downloaded, triggering search: {movie_data.get('title')}")
                        # Trigger search for the existing movie
                        if radarr_status.get('radarr_movie_id'):
                            self.download_monitor.radarr_client.search_for_movie(radarr_status['radarr_movie_id'])
                            # Send notification that search was triggered
                            self._send_search_triggered_notification(movie_data, phone_number)
                else:
                    # Movie not in Radarr, request download
                    logger.info(f"🔍 PlexAgent: Movie not in Radarr, requesting download for {movie_data.get('title')}")
                    movie_downloaded = self.request_movie_download(movie_data, phone_number)
                    logger.info(f"📱 PlexAgent: Download request result: {movie_downloaded}")
                    if movie_downloaded:
                        movie_status_message = f" (Note: The movie '{movie_data.get('title')}' has been added to your download queue)"
                        logger.info(f"✅ PlexAgent: Successfully added {movie_data.get('title')} to download queue")
                        
                        # Send immediate SMS notification that movie was added
                        self._send_movie_added_notification(movie_data, phone_number)
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
            else:
                logger.error(f"❌ PlexAgent: Failed to send search triggered notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ PlexAgent: Error sending search triggered notification: {str(e)}")