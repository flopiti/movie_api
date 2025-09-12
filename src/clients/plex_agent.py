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
        Returns response message based on download request success/failure.
        """
        if not movie_data or not phone_number:
            logger.warning(f"⚠️ PlexAgent: Missing movie data or phone number for download request")
            return None
        
        # Extract year from release_date (format: YYYY-MM-DD)
        release_date = movie_data.get('release_date', '')
        year = release_date.split('-')[0] if release_date else 'Unknown year'
        tmdb_id = movie_data.get('id')
        
        logger.info(f"📱 PlexAgent: Adding download request for {movie_data.get('title')} ({year}) from {phone_number}")
        
        # Check if Radarr is configured first
        if not self.download_monitor.is_radarr_configured():
            response_message = f"🎬 I found '{movie_data.get('title')} ({year})' but Radarr is not configured yet. Please set up your Radarr API key to enable downloads!"
            logger.warning(f"⚠️ PlexAgent: Radarr not configured - cannot process download request for {movie_data.get('title')}")
            return response_message
        
        # Add download request to the monitor
        success = self.download_monitor.add_download_request(
            tmdb_id=tmdb_id,
            movie_title=movie_data.get('title'),
            movie_year=year,
            phone_number=phone_number
        )
        
        if success:
            response_message = f"🎬 Great! I found '{movie_data.get('title')} ({year})' and added it to your download queue. I'll send you updates as the download progresses!"
            logger.info(f"✅ PlexAgent: Download request added successfully for {movie_data.get('title')}")
        else:
            response_message = f"🎬 I found '{movie_data.get('title')} ({year})' but it's already in your download queue. I'll keep you updated on the progress!"
            logger.info(f"ℹ️ PlexAgent: Download request already exists for {movie_data.get('title')}")
        
        return response_message
    
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
        movie_result = self.openai_client.getMovieName(conversation_history)
        logger.info(f"🎬 PlexAgent: Movie detection result: {movie_result}")
        
        # Step 2: Search TMDB for the movie if detected
        tmdb_result, movie_data = self.get_movie(movie_result)
        
        # Step 3: Request download if movie was found in TMDB
        response_message = None
        if movie_data and tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
            response_message = self.request_movie_download(movie_data, phone_number)
        
        # Step 4: Generate GPT response if no movie-specific response was generated
        if not response_message:
            logger.info(f"🤖 PlexAgent: No movie response, calling ChatGPT...")
            
            # Add context about movie detection result
            movie_context = ""
            if movie_result and movie_result.get('success') and movie_result.get('movie_name') and movie_result.get('movie_name') != "No movie identified":
                # Check if movie was found in TMDB
                if tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
                    movie_data = tmdb_result['results'][0]
                    release_date = movie_data.get('release_date', '')
                    year = release_date.split('-')[0] if release_date else 'Unknown year'
                    movie_context = f" (Note: A movie '{movie_data.get('title')} ({year})' was identified and found in our database)"
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
                    response_message = "I received your message but couldn't identify a movie. Could you please specify which movie you'd like me to get?"
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