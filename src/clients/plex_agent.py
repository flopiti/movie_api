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

Based on the above context and available functions, analyze the user's request and determine the appropriate actions to take. Use the available functions to gather information and take actions as needed."""
    
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
                # No function calls, return direct response
                return {
                    'response_message': response.get('response', 'I received your message.'),
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
        Agentic Answer method - uses discrete functions for decision making
        """
        # Validate input
        if not conversation_history:
            logger.error(f"❌ Agent: No conversation history provided")
            return {
                'response_message': "I received your message but couldn't process it. Please try again.",
                'movie_result': None,
                'tmdb_result': None,
                'success': False
            }
        
        # Extract current message from the latest USER message
        current_message = None
        for message in reversed(conversation_history):
            if message.startswith("USER: "):
                current_message = message.replace("USER: ", "")
                break
        
        logger.info(f"🎬 Agent: Processing request from {phone_number}: {current_message}")
        
        # Step 1: Identify movie request using agentic function
        movie_identification = self.identify_movie_request(conversation_history)
        
        movie_context = ""
        movie_data = None
        tmdb_result = None
        actions_taken = []
        
        if movie_identification.get('success') and movie_identification.get('movie_name') != "No movie identified":
            movie_name = movie_identification['movie_name']
            logger.info(f"🎬 Agent: Movie identified: {movie_name}")
            
            # Step 2: Check movie library status using agentic function
            library_status = self.check_movie_library_status(movie_name)
            
            if library_status.get('success'):
                movie_data = library_status['movie_data']
                tmdb_result = library_status['tmdb_result']
                release_status = library_status['release_status']
                
                logger.info(f"🔍 Agent: Movie found in TMDB: {movie_data.get('title')}")
                
                # Step 3: Check if movie is released
                if release_status and not release_status.get('is_released', True):
                    # Movie not released yet
                    release_date = release_status.get('release_date_formatted', 'Unknown date')
                    days_until = release_status.get('days_until_release', 0)
                    if days_until:
                        movie_context = f" (Note: The movie '{movie_data.get('title')}' is not released yet. It will be available on {release_date} - {days_until} days from now)"
                    else:
                        movie_context = f" (Note: The movie '{movie_data.get('title')}' is not released yet. Release date: {release_date})"
                    logger.info(f"📅 Agent: Movie not released yet: {movie_data.get('title')}")
                else:
                    # Movie is released, check Radarr status using agentic function
                    radarr_status = self.check_radarr_status(library_status['tmdb_id'], movie_data)
                    
                    if radarr_status.get('success'):
                        if radarr_status.get('exists_in_radarr'):
                            if radarr_status.get('is_downloaded'):
                                # Movie already downloaded
                                movie_context = f" (Note: The movie '{movie_data.get('title')}' is already downloaded and available in your library)"
                                logger.info(f"✅ Agent: Movie already downloaded: {movie_data.get('title')}")
                                actions_taken.append("movie_already_available")
                                
                            elif radarr_status.get('is_downloading'):
                                # Movie currently downloading
                                movie_context = f" (Note: The movie '{movie_data.get('title')}' is already being downloaded)"
                                logger.info(f"📥 Agent: Movie already downloading: {movie_data.get('title')}")
                                
                                # Set up monitoring for already downloading movie
                                download_request = self.request_download(movie_data, phone_number)
                                if download_request.get('success'):
                                    actions_taken.append("monitoring_existing_download")
                                
                            else:
                                # Movie exists but not downloading - trigger search
                                movie_context = f" (Note: The movie '{movie_data.get('title')}' is already in your download queue - triggering search for available releases)"
                                logger.info(f"🔍 Agent: Movie in Radarr but not downloaded, triggering search: {movie_data.get('title')}")
                                
                                # Trigger search for existing movie
                                if radarr_status.get('radarr_movie_id'):
                                    self._get_download_monitor().radarr_client.search_for_movie(radarr_status['radarr_movie_id'])
                                
                                # Set up monitoring
                                download_request = self.request_download(movie_data, phone_number)
                                if download_request.get('success'):
                                    actions_taken.append("triggered_search_and_monitoring")
                        else:
                            # Movie not in Radarr - request download using agentic function
                            logger.info(f"🔍 Agent: Movie not in Radarr, requesting download for {movie_data.get('title')}")
                            download_request = self.request_download(movie_data, phone_number)
                            
                            if download_request.get('success'):
                                if download_request.get('action') == 'download_requested':
                                    movie_context = f" (Note: The movie '{movie_data.get('title')}' has been added to your download queue)"
                                    actions_taken.append("download_requested")
                                else:
                                    movie_context = f" (Note: The movie '{movie_data.get('title')}' could not be added to your download queue - it may already be requested or unavailable)"
                                    actions_taken.append("download_already_requested")
                                
                                logger.info(f"✅ Agent: Download request result: {download_request.get('action')}")
                            else:
                                movie_context = f" (Note: The movie '{movie_data.get('title')}' could not be added to your download queue - {download_request.get('error')})"
                                actions_taken.append("download_failed")
                    else:
                        # Radarr check failed
                        movie_context = f" (Note: A movie '{movie_data.get('title')}' was identified but I couldn't check your library status)"
                        actions_taken.append("radarr_check_failed")
            else:
                # Movie not found in TMDB
                movie_context = f" (Note: A movie '{movie_name}' was identified but not found in our database)"
                actions_taken.append("movie_not_found")
        else:
            # No movie identified
            movie_context = " (Note: No movie was identified in the conversation)"
            actions_taken.append("no_movie_identified")
        
        # Step 4: Generate response using agentic prompt
        if current_message and phone_number:
            # Build comprehensive conversation context
            conversation_context = f"""
CONVERSATION HISTORY:
{chr(10).join(conversation_history[-5:])}

CURRENT USER MESSAGE: {current_message}
USER PHONE NUMBER: {phone_number}
MOVIE CONTEXT: {movie_context}
ACTIONS TAKEN: {', '.join(actions_taken) if actions_taken else 'none'}
"""
            
            # Use agentic prompt for response generation
            agentic_prompt = self._build_agentic_prompt(conversation_context)
            
            chatgpt_result = self.openai_client.generate_sms_response(
                current_message, 
                phone_number, 
                agentic_prompt,
                movie_context=movie_context
            )
            
            if chatgpt_result.get('success'):
                response_message = chatgpt_result['response']
            else:
                logger.error(f"❌ Agent OpenAI Failed: {chatgpt_result.get('error', 'Unknown error')}")
                response_message = "I received your message but couldn't process it properly. Could you please specify which movie you'd like me to get?"
        else:
            logger.error(f"❌ Agent: Could not extract current message or phone number")
            response_message = "I received your message but couldn't process it properly. Could you please specify which movie you'd like me to get?"

        # Return comprehensive response data
        return {
            'response_message': response_message,
            'movie_result': movie_identification,
            'tmdb_result': tmdb_result,
            'movie_data': movie_data,
            'actions_taken': actions_taken,
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