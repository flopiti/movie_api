import logging
import time
import threading
from datetime import datetime
from config.config import OPENAI_API_KEY, TMDB_API_KEY
from ..clients.openai_client import OpenAIClient
from ..clients.tmdb_client import TMDBClient
from ..clients.PROMPTS import SMS_RESPONSE_PROMPT, MOVIE_AGENT_PRIMARY_PURPOSE, MOVIE_AGENT_PROCEDURES, MOVIE_AGENT_AVAILABLE_FUNCTIONS, MOVIE_AGENT_FUNCTION_SCHEMA
from ..services.download_monitor import get_download_monitor
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
        self.download_monitor = None  # Will be initialized lazily
        self.sms_response_prompt = SMS_RESPONSE_PROMPT
        self.twilio_client = TwilioClient()
        
        # Agentic prompts
        self.primary_purpose = MOVIE_AGENT_PRIMARY_PURPOSE
        self.procedures = MOVIE_AGENT_PROCEDURES
        self.available_functions = MOVIE_AGENT_AVAILABLE_FUNCTIONS
        self.function_schema = MOVIE_AGENT_FUNCTION_SCHEMA
        
        # Download monitoring
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
    
    def _get_download_monitor(self):
        """Get download monitor instance, creating it if needed"""
        if self.download_monitor is None:
            self.download_monitor = get_download_monitor()
        return self.download_monitor
    
    def _build_agentic_prompt(self, conversation_context=""):
        """Build the complete agentic prompt by combining all prompt components"""
        return f"""{self.primary_purpose}

{self.procedures}

{self.available_functions}

CURRENT CONTEXT:
{conversation_context}

Based on the above context and available functions, analyze the user's request and determine the appropriate actions to take. 

IMPORTANT: You must either:
1. Call the appropriate functions to gather information and take actions, OR
2. Provide a direct SMS response to the user

DO NOT return internal instructions or prompts to the user. Always provide a user-friendly SMS response."""
    
    def _execute_function_call(self, function_name: str, parameters: dict):
        """Execute a function call based on the function name and parameters"""
        try:
            logger.info(f"🔧 Agent: Executing function {function_name} with parameters: {parameters}")
            
            if function_name == "identify_movie_request":
                conversation_history = parameters.get('conversation_history', [])
                return self.identify_movie_request(conversation_history)
                
            elif function_name == "check_movie_library_status":
                movie_name = parameters.get('movie_name', '')
                return self.check_movie_library_status(movie_name)
                
            elif function_name == "check_radarr_status":
                tmdb_id = parameters.get('tmdb_id')
                movie_data = parameters.get('movie_data')
                return self.check_radarr_status(tmdb_id, movie_data)
                
            elif function_name == "request_download":
                movie_data = parameters.get('movie_data')
                phone_number = parameters.get('phone_number')
                return self.request_download(movie_data, phone_number)
                
            elif function_name == "send_notification":
                phone_number = parameters.get('phone_number')
                message_type = parameters.get('message_type')
                movie_data = parameters.get('movie_data')
                additional_context = parameters.get('additional_context', '')
                return self.send_notification(phone_number, message_type, movie_data, additional_context)
                
            else:
                logger.error(f"❌ Agent: Unknown function name: {function_name}")
                return {
                    'success': False,
                    'error': f'Unknown function: {function_name}'
                }
                
        except Exception as e:
            logger.error(f"❌ Agent: Error executing function {function_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _process_agentic_response(self, conversation_history, phone_number):
        """Process agentic response with function calling support"""
        try:
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
            
            # Build conversation context
            conversation_context = f"""
CONVERSATION HISTORY:
{chr(10).join(conversation_history[-5:])}

CURRENT USER MESSAGE: {current_message}
USER PHONE NUMBER: {phone_number}
"""
            
            # Build agentic prompt
            agentic_prompt = self._build_agentic_prompt(conversation_context)
            
            # Generate agentic response with function calling
            response = self.openai_client.generate_agentic_response(
                prompt=agentic_prompt,
                functions=[self.function_schema]
            )
            
            if not response.get('success'):
                logger.error(f"❌ Agent: OpenAI response failed: {response.get('error')}")
                return {
                    'response_message': "I received your message but couldn't process it properly.",
                    'success': False
                }
            
            # Process function calls if any
            if response.get('has_function_calls') and response.get('tool_calls'):
                logger.info(f"🔧 Agent: Processing {len(response['tool_calls'])} function calls")
                
                function_results = []
                for tool_call in response['tool_calls']:
                    try:
                        # Parse function call arguments
                        function_args = tool_call.function.arguments
                        import json
                        parsed_args = json.loads(function_args)
                        
                        function_name = parsed_args.get('function_name')
                        parameters = parsed_args.get('parameters', {})
                        
                        # Execute the function
                        result = self._execute_function_call(function_name, parameters)
                        function_results.append({
                            'function_name': function_name,
                            'result': result
                        })
                        
                        logger.info(f"✅ Agent: Function {function_name} executed successfully")
                        
                    except Exception as e:
                        logger.error(f"❌ Agent: Error processing function call: {str(e)}")
                        function_results.append({
                            'function_name': 'unknown',
                            'result': {'success': False, 'error': str(e)}
                        })
                
                # Generate final response based on function results
                final_context = f"""
FUNCTION EXECUTION RESULTS:
{chr(10).join([f"- {fr['function_name']}: {fr['result']}" for fr in function_results])}

ORIGINAL USER MESSAGE: {current_message}
"""
                
                final_response = self.openai_client.generate_sms_response(
                    message=current_message,
                    sender=phone_number,
                    prompt_template=self.sms_response_prompt,
                    movie_context=final_context
                )
                
                if final_response.get('success'):
                    return {
                        'response_message': final_response['response'],
                        'function_results': function_results,
                        'success': True
                    }
                else:
                    return {
                        'response_message': "I processed your request but couldn't generate a proper response.",
                        'function_results': function_results,
                        'success': True
                    }
            else:
                # No function calls - check if response contains internal instructions
                ai_response = response.get('response', '')
                
                # Check if the response contains internal prompt text that shouldn't be sent to user
                if any(phrase in ai_response.lower() for phrase in [
                    "let's use the", "we need to prompt", "internal instructions", 
                    "function calling", "available functions", "procedures for"
                ]):
                    logger.warning(f"⚠️ Agent: AI returned internal instructions instead of user response")
                    # Fall back to simple SMS response
                    fallback_response = self.openai_client.generate_sms_response(
                        message=current_message,
                        sender=phone_number,
                        prompt_template=self.sms_response_prompt,
                        movie_context=""
                    )
                    
                    if fallback_response.get('success'):
                        return {
                            'response_message': fallback_response['response'],
                            'function_results': [],
                            'success': True
                        }
                    else:
                        return {
                            'response_message': "I received your message. How can I help you with a movie?",
                            'function_results': [],
                            'success': True
                        }
                else:
                    # Response looks like a proper user message
                    return {
                        'response_message': ai_response,
                        'function_results': [],
                        'success': True
                    }
                
        except Exception as e:
            logger.error(f"❌ Agent: Error in agentic response processing: {str(e)}")
            return {
                'response_message': "I received your message but encountered an error processing it.",
                'success': False,
                'error': str(e)
            }
    
    # =============================================================================
    # AGENTIC FUNCTION CALLS - Discrete capabilities for agentic decision making
    # =============================================================================
    
    def identify_movie_request(self, conversation_history):
        """
        Agentic function: Extract movie title and year from SMS conversation
        Returns movie name with year or "No movie identified"
        """
        try:
            # Send last 10 messages (both USER and SYSTEM) for context
            last_10_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            
            movie_result = self.openai_client.getMovieName(last_10_messages)
            
            if movie_result and movie_result.get('success') and movie_result.get('movie_name'):
                logger.info(f"🎬 Agent: Movie identified: {movie_result['movie_name']}")
                return {
                    'success': True,
                    'movie_name': movie_result['movie_name'],
                    'confidence': movie_result.get('confidence', 'medium')
                }
            else:
                logger.info(f"🎬 Agent: No movie identified in conversation")
                return {
                    'success': False,
                    'movie_name': "No movie identified",
                    'confidence': 'none'
                }
                
        except Exception as e:
            logger.error(f"❌ Agent: Error identifying movie request: {str(e)}")
            return {
                'success': False,
                'movie_name': "No movie identified",
                'confidence': 'none',
                'error': str(e)
            }
    
    def check_movie_library_status(self, movie_name):
        """
        Agentic function: Search TMDB and check release status for a movie
        Returns comprehensive movie information and availability status
        """
        try:
            logger.info(f"🔍 Agent: Checking library status for: {movie_name}")
            
            # Search TMDB for the movie
            tmdb_result = self.tmdb_client.search_movie(movie_name)
            if not tmdb_result.get('results') or len(tmdb_result.get('results', [])) == 0:
                logger.info(f"🔍 Agent: Movie not found in TMDB: {movie_name}")
                return {
                    'success': False,
                    'movie_name': movie_name,
                    'tmdb_result': tmdb_result,
                    'movie_data': None,
                    'release_status': None,
                    'error': 'Movie not found in TMDB'
                }
            
            movie_data = tmdb_result['results'][0]  # Get first result
            tmdb_id = movie_data.get('id')
            
            # Extract year from release_date (format: YYYY-MM-DD)
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            
            logger.info(f"🔍 Agent: TMDB found movie: {movie_data.get('title')} ({year})")
            
            # Check release status
            release_status = self.tmdb_client.is_movie_released(movie_data)
            logger.info(f"📅 Agent: Release status: {release_status}")
            
            return {
                'success': True,
                'movie_name': movie_name,
                'tmdb_result': tmdb_result,
                'movie_data': movie_data,
                'tmdb_id': tmdb_id,
                'year': year,
                'release_status': release_status
            }
            
        except Exception as e:
            logger.error(f"❌ Agent: Error checking movie library status: {str(e)}")
            return {
                'success': False,
                'movie_name': movie_name,
                'error': str(e)
            }
    
    def check_radarr_status(self, tmdb_id, movie_data):
        """
        Agentic function: Check if movie exists in user's Radarr library
        Returns detailed Radarr status including download state
        """
        try:
            if not tmdb_id or not movie_data:
                logger.warning(f"⚠️ Agent: Missing tmdb_id or movie_data for Radarr check")
                return {
                    'success': False,
                    'tmdb_id': tmdb_id,
                    'movie_title': movie_data.get('title') if movie_data else 'Unknown',
                    'error': 'Missing required parameters'
                }
            
            logger.info(f"🔍 Agent: Checking Radarr status for {movie_data.get('title')}")
            
            # Check if Radarr is configured first
            if not self._get_download_monitor().is_radarr_configured():
                logger.warning(f"⚠️ Agent: Radarr not configured")
                return {
                    'success': False,
                    'tmdb_id': tmdb_id,
                    'movie_title': movie_data.get('title'),
                    'radarr_status': None,
                    'error': 'Radarr not configured'
                }
            
            # Check Radarr status
            radarr_status = self._get_download_monitor().radarr_client.get_movie_status_by_tmdb_id(tmdb_id)
            logger.info(f"📱 Agent: Radarr status: {radarr_status}")
            
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
            logger.error(f"❌ Agent: Error checking Radarr status: {str(e)}")
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
                logger.warning(f"⚠️ Agent: Missing movie data or phone number for download request")
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
            
            logger.info(f"📱 Agent: Processing download request for {movie_title} ({year}) from {phone_number}")
            
            # Check if Radarr is configured first
            if not self._get_download_monitor().is_radarr_configured():
                logger.warning(f"⚠️ Agent: Radarr not configured - cannot process download request")
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
                logger.info(f"✅ Agent: Download request added successfully for {movie_title}")
                return {
                    'success': True,
                    'action': 'download_requested',
                    'movie_title': movie_title,
                    'movie_year': year,
                    'tmdb_id': tmdb_id
                }
            else:
                logger.info(f"ℹ️ Agent: Download request already exists for {movie_title}")
                return {
                    'success': True,
                    'action': 'already_requested',
                    'movie_title': movie_title,
                    'movie_year': year,
                    'tmdb_id': tmdb_id
                }
                
        except Exception as e:
            logger.error(f"❌ Agent: Error requesting download: {str(e)}")
            return {
                'success': False,
                'action': 'none',
                'movie_title': movie_data.get('title') if movie_data else 'Unknown',
                'error': str(e)
            }
    
    def send_notification(self, phone_number, message_type, movie_data, additional_context=""):
        """
        Agentic function: Send SMS notification to user
        Returns delivery status and message sent
        """
        try:
            if not phone_number or not message_type or not movie_data:
                logger.warning(f"⚠️ Agent: Missing parameters for notification")
                return {
                    'success': False,
                    'message_type': message_type,
                    'error': 'Missing required parameters'
                }
            
            # Extract movie details
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            movie_title = movie_data.get('title')
            
            # Generate appropriate message based on type
            if message_type == "movie_added":
                message = f"🎬 Adding '{movie_title}' ({year}) to your download queue. I'll let you know when it starts downloading!"
            elif message_type == "search_triggered":
                message = f"🔍 Searching for '{movie_title}' ({year}) releases. I'll let you know when download starts!"
            elif message_type == "download_started":
                message = f"🎬 Great! I'm getting {movie_title} ({year}) ready for you. I'll text you when it's ready to watch!"
            elif message_type == "download_completed":
                message = f"🎉 {movie_title} ({year}) is ready to watch! Enjoy your movie!"
            else:
                message = f"📱 Update on {movie_title} ({year}): {additional_context}"
            
            # Send SMS
            result = self.twilio_client.send_sms(phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 Agent: Sent {message_type} notification to {phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(phone_number, message, message_type)
                return {
                    'success': True,
                    'message_type': message_type,
                    'message_sent': message,
                    'phone_number': phone_number
                }
            else:
                logger.error(f"❌ Agent: Failed to send {message_type} notification: {result.get('error')}")
                return {
                    'success': False,
                    'message_type': message_type,
                    'error': result.get('error', 'Unknown SMS error')
                }
                
        except Exception as e:
            logger.error(f"❌ Agent: Error sending notification: {str(e)}")
            return {
                'success': False,
                'message_type': message_type,
                'error': str(e)
            }
    
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
        if self._get_download_monitor().is_radarr_configured() and tmdb_id:
            logger.info(f"🔍 PlexAgent: Checking Radarr status for {movie_data.get('title')}")
            radarr_status = self._get_download_monitor().radarr_client.get_movie_status_by_tmdb_id(tmdb_id)
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
        if not self._get_download_monitor().is_radarr_configured():
            logger.warning(f"⚠️ PlexAgent: Radarr not configured - cannot process download request for {movie_data.get('title')}")
            return False
        
        # Add download request to the monitor
        logger.info(f"📱 PlexAgent: Calling download_monitor.add_download_request for {movie_data.get('title')}")
        success = self._get_download_monitor().add_download_request(
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
        try:
            # Create movie data object for the notification function
            movie_data = {
                'title': request.movie_title,
                'release_date': f"{request.movie_year}-01-01",  # Approximate date
                'id': request.tmdb_id
            }
            
            # Use the agentic notification function
            result = self.send_notification(
                phone_number=request.phone_number,
                message_type="download_started",
                movie_data=movie_data
            )
            
            if result.get('success'):
                logger.info(f"📱 Agent: Sent download started notification to {request.phone_number}")
            else:
                logger.error(f"❌ Agent: Failed to send download started notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Agent: Error sending download started notification: {str(e)}")
    
    def _send_download_completed_notification(self, request):
        """Send SMS notification when download completes using agentic function"""
        try:
            # Create movie data object for the notification function
            movie_data = {
                'title': request.movie_title,
                'release_date': f"{request.movie_year}-01-01",  # Approximate date
                'id': request.tmdb_id
            }
            
            # Use the agentic notification function
            result = self.send_notification(
                phone_number=request.phone_number,
                message_type="download_completed",
                movie_data=movie_data
            )
            
            if result.get('success'):
                logger.info(f"📱 Agent: Sent download completed notification to {request.phone_number}")
            else:
                logger.error(f"❌ Agent: Failed to send download completed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Agent: Error sending download completed notification: {str(e)}")

# Global instance
plex_agent = PlexAgent()