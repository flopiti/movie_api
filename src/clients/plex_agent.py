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
        Returns TMDB result and movie data if found.
        """
        if not movie_result or not movie_result.get('success') or not movie_result.get('movie_name') or movie_result.get('movie_name') == "No movie identified":
            logger.info(f"🎬 PlexAgent: No movie identified in conversation")
            return None, None
        
        logger.info(f"🎬 PlexAgent: Movie detected: {movie_result['movie_name']}")
        
        # Search TMDB for the movie
        tmdb_result = self.tmdb_client.search_movie(movie_result['movie_name'])
        if not tmdb_result.get('results') or len(tmdb_result.get('results', [])) == 0:
            logger.info(f"🎬 PlexAgent: Movie not found in TMDB: {movie_result['movie_name']}")
            return tmdb_result, None
        
        movie_data = tmdb_result['results'][0]  # Get first result
        
        # Extract year from release_date (format: YYYY-MM-DD)
        release_date = movie_data.get('release_date', '')
        year = release_date.split('-')[0] if release_date else 'Unknown year'
        
        logger.info(f"🎬 PlexAgent: TMDB found movie: {movie_data.get('title')} ({year})")
        
        return tmdb_result, movie_data
    
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
        success = self.download_monitor.add_download_request(
            tmdb_id=tmdb_id,
            movie_title=movie_data.get('title'),
            movie_year=year,
            phone_number=phone_number
        )
        
        if success:
            logger.info(f"✅ PlexAgent: Download request added successfully for {movie_data.get('title')}")
        else:
            logger.info(f"ℹ️ PlexAgent: Download request already exists for {movie_data.get('title')}")
        
        return success
    
    def Answer(self, conversation_history, phone_number):
        logger.info(f"🎬 PlexAgent: Processing conversation with {len(conversation_history)} messages from {phone_number}")
        
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
        logger.info(f"🎬 PlexAgent: Analyzing conversation for movie detection...")
        logger.info(f"🎬 PlexAgent: Conversation history ({len(conversation_history)} messages): {conversation_history}")
        
        # Send last 10 messages (both USER and SYSTEM) instead of filtering to only USER messages
        last_10_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        logger.info(f"🎬 PlexAgent: Sending last {len(last_10_messages)} messages to OpenAI: {last_10_messages}")
        
        movie_result = self.openai_client.getMovieName(last_10_messages)
        logger.info(f"🎬 PlexAgent: Movie detection result: {movie_result}")
        
        # Step 2: Search TMDB for the movie if detected
        tmdb_result, movie_data = self.get_movie(movie_result)
        
        # Step 3: Request download if movie was found in TMDB
        movie_downloaded = False
        if movie_data and tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
            movie_downloaded = self.request_movie_download(movie_data, phone_number)
        
        # Step 4: Always generate GPT response with full context
        logger.info(f"🤖 PlexAgent: Generating ChatGPT response with full context...")
        
        # Build comprehensive context about movie detection and download status
        movie_context = ""
        if movie_result and movie_result.get('success') and movie_result.get('movie_name') and movie_result.get('movie_name') != "No movie identified":
            # Check if movie was found in TMDB
            if tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
                movie_data = tmdb_result['results'][0]
                release_date = movie_data.get('release_date', '')
                year = release_date.split('-')[0] if release_date else 'Unknown year'
                if movie_downloaded:
                    movie_context = f" (Note: A movie '{movie_data.get('title')} ({year})' was identified, found in our database, and successfully added to Radarr for downloading)"
                else:
                    movie_context = f" (Note: A movie '{movie_data.get('title')} ({year})' was identified and found in our database, but could not be added to Radarr - it may be unreleased or unavailable)"
            else:
                movie_context = f" (Note: A movie '{movie_result['movie_name']}' was identified but not found in our database)"
        else:
            movie_context = " (Note: No movie was identified in the conversation)"
        
        if current_message and phone_number:
            logger.info(f"🤖 PlexAgent OpenAI Request: Generating response for message '{current_message}' from '{phone_number}'{movie_context}")
            chatgpt_result = self.openai_client.generate_sms_response(
                current_message, 
                phone_number, 
                self.sms_response_prompt,
                movie_context=movie_context
            )
            
            logger.info(f"🤖 PlexAgent OpenAI Result: {chatgpt_result}")
            
            if chatgpt_result.get('success'):
                response_message = chatgpt_result['response']
                logger.info(f"✅ PlexAgent OpenAI Response: Generated response '{response_message}'")
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