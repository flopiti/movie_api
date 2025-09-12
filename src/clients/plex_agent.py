import logging
from datetime import datetime
from config.config import openai_client, tmdb_client, download_monitor, SMS_RESPONSE_PROMPT

logger = logging.getLogger(__name__)

class PlexAgent:
    """
    Agent responsible for processing SMS messages and handling movie-related requests.
    Detects movies in conversations, searches TMDB, and manages download requests.
    """
    
    def __init__(self):
        self.openai_client = openai_client
        self.tmdb_client = tmdb_client
        self.download_monitor = download_monitor
        self.sms_response_prompt = SMS_RESPONSE_PROMPT
    
    def Answer(self, message_data, conversation_history=None):
        """
        Process an incoming SMS message and generate an appropriate response.
        
        Args:
            message_data (dict): The incoming SMS message data
            conversation_history (list, optional): Previous messages in the conversation
            
        Returns:
            dict: Response containing the generated message and any relevant metadata
        """
        logger.info(f"🎬 PlexAgent: Processing message from {message_data['From']}")
        
        # Try to detect movie in conversation
        movie_result = None
        response_message = None  # Initialize response message
        
        if conversation_history:
            logger.info(f"🎬 PlexAgent: Analyzing conversation for movie detection...")
            logger.info(f"🎬 PlexAgent: Conversation history ({len(conversation_history)} messages): {conversation_history}")
            movie_result = self.openai_client.getMovieName(conversation_history)
            logger.info(f"🎬 PlexAgent: Movie detection result: {movie_result}")
        else:
            # Fallback: analyze just the current message
            logger.info(f"🎬 PlexAgent: No conversation history, analyzing current message...")
            logger.info(f"🎬 PlexAgent: Current message: {[message_data['Body']]}")
            movie_result = self.openai_client.getMovieName([message_data['Body']])
            logger.info(f"🎬 PlexAgent: Movie detection result: {movie_result}")
        
        if movie_result and movie_result.get('success') and movie_result.get('movie_name') and movie_result.get('movie_name') != "No movie identified":
            logger.info(f"🎬 PlexAgent: Movie detected: {movie_result['movie_name']}")
            
            # Search TMDB for the movie
            tmdb_result = self.tmdb_client.search_movie(movie_result['movie_name'])
            if tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
                movie_data = tmdb_result['results'][0]  # Get first result
                
                # Extract year from release_date (format: YYYY-MM-DD)
                release_date = movie_data.get('release_date', '')
                year = release_date.split('-')[0] if release_date else 'Unknown year'
                
                logger.info(f"🎬 PlexAgent: TMDB found movie: {movie_data.get('title')} ({year})")
                
                # Add download request to the monitor
                tmdb_id = movie_data.get('id')
                if tmdb_id:
                    logger.info(f"📱 PlexAgent: Adding download request for {movie_data.get('title')} ({year}) from {message_data['From']}")
                    
                    # Check if Radarr is configured first
                    if not self.download_monitor.is_radarr_configured():
                        response_message = f"🎬 I found '{movie_data.get('title')} ({year})' but Radarr is not configured yet. Please set up your Radarr API key to enable downloads!"
                        logger.warning(f"⚠️ PlexAgent: Radarr not configured - cannot process download request for {movie_data.get('title')}")
                    else:
                        success = self.download_monitor.add_download_request(
                            tmdb_id=tmdb_id,
                            movie_title=movie_data.get('title'),
                            movie_year=year,
                            phone_number=message_data['From']
                        )
                        
                        if success:
                            response_message = f"🎬 Great! I found '{movie_data.get('title')} ({year})' and added it to your download queue. I'll send you updates as the download progresses!"
                            logger.info(f"✅ PlexAgent: Download request added successfully for {movie_data.get('title')}")
                        else:
                            response_message = f"🎬 I found '{movie_data.get('title')} ({year})' but it's already in your download queue. I'll keep you updated on the progress!"
                            logger.info(f"ℹ️ PlexAgent: Download request already exists for {movie_data.get('title')}")
                
                # Don't set response_message - let it fall through to ChatGPT with movie context
            else:
                logger.info(f"🎬 PlexAgent: Movie not found in TMDB: {movie_result['movie_name']}")
                # Don't set response_message - let it fall through to ChatGPT with movie context
        else:
            logger.info(f"🎬 PlexAgent: No movie identified in conversation")
            # Don't set response_message - let it fall through to ChatGPT
        
        # Always try ChatGPT if no movie-specific response was generated
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
            
            logger.info(f"🤖 PlexAgent OpenAI Request: Generating response for message '{message_data['Body']}' from '{message_data['From']}'{movie_context}")
            chatgpt_result = self.openai_client.generate_sms_response(
                message_data['Body'], 
                message_data['From'], 
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

        # Return the response data
        return {
            'response_message': response_message,
            'movie_result': movie_result,
            'tmdb_result': tmdb_result if 'tmdb_result' in locals() else None,
            'success': True
        }
