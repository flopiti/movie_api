#!/usr/bin/env python3
"""
Agentic Service
Handles agentic decision making and function calling.
"""

import logging
import json
import tiktoken
from typing import Dict, Any, List
from ..clients.openai_client import OpenAIClient
from ..clients.PROMPTS import MOVIE_AGENT_FUNCTION_SCHEMA
# Configure logging to ensure we see debug messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AgenticService:
    """Service for agentic decision making and function calling"""
    
    def __init__(self, openai_client: OpenAIClient):
        self.openai_client = openai_client
        self.function_schema = MOVIE_AGENT_FUNCTION_SCHEMA

        
        # Initialize tokenizer for counting tokens
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
        except Exception as e:
            logger.warning(f"⚠️ AgenticService: Could not initialize tokenizer: {str(e)}")
            self.tokenizer = None
        

    
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        if self.tokenizer is None:
            # Fallback: rough estimation (4 characters per token)
            return len(text) // 4
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"⚠️ AgenticService: Error counting tokens: {str(e)}")
            return len(text) // 4  # Fallback estimation
    
    def _extract_field_value(self, result: Dict[str, Any], field_path: str) -> Any:
        """Extract field value from nested dictionary using dot notation"""
        try:
            # Handle case where result is not a dictionary
            if not isinstance(result, dict):
                logger.warning(f"Result is not a dictionary: {type(result)} - {result}")
                return 'Unknown'
            
            # Special handling for title and year fields
            if field_path in ['title', 'year'] and 'movie_data' in result:
                movie_data = result['movie_data']
                if field_path == 'title':
                    return movie_data.get('title', 'Unknown')
                elif field_path == 'year':
                    # Extract year from release_date
                    release_date = movie_data.get('release_date', '')
                    if release_date:
                        return release_date.split('-')[0] if '-' in release_date else release_date
                    return 'Unknown'
            
            keys = field_path.split('.')
            value = result
            for key in keys:
                if not isinstance(value, dict):
                    logger.warning(f"Value is not a dictionary when accessing key '{key}': {type(value)} - {value}")
                    return 'Unknown'
                value = value[key]
            return value
        except (KeyError, TypeError) as e:
            logger.warning(f"Error extracting field '{field_path}' from result: {str(e)}")
            return 'Unknown'
    
    
    def _generate_function_summary(self, function_name: str, result: Dict[str, Any]) -> str:
        """Generate concise function summary using configuration"""
        config = self.function_summary_config.get(function_name, self.function_summary_config.get('default', {}))
        
        template = config.get('summary_template', '{success_status}')
        extract_fields = config.get('extract_fields', ['success'])
        
        # Extract field values
        field_values = {}
        for field in extract_fields:
            if field == 'success_status':
                field_values[field] = 'Success' if result.get('success', False) else 'Failed'
            else:
                value = self._extract_field_value(result, field)
                field_values[field] = value
        
        # Format template with extracted values
        try:
            return template.format(**field_values)
        except KeyError as e:
            logger.warning(f"Missing field {e} for function {function_name}. Available fields: {list(field_values.keys())}")
            return f"{function_name}: Success" if result.get('success', False) else f"{function_name}: Failed"
    
    def _format_available_data_template(self, template: str, function_results: List[Dict], conversation_context: str, current_function_name: str, iteration_results: List[Dict] = None) -> str:
        """Format available data template by resolving function references"""
        try:
            # Extract phone number from conversation context
            phone_number = None
            if conversation_context:
                import re
                phone_match = re.search(r'USER PHONE NUMBER:\s*([+\d\s\-\(\)]+)', conversation_context, re.IGNORECASE)
                if phone_match:
                    phone_number = phone_match.group(1).strip()
            
            # Parse template for function references like {check_movie_library_status.movie_data.title}
            import re
            logger.info(f"🔍 TEMPLATE: Parsing template: {template}")
            function_refs = re.findall(r'\{([^.]+)\.([^}]+)\}', template)
            logger.info(f"🔍 TEMPLATE: Found function_refs: {function_refs}")
            
            format_dict = {'phone_number': phone_number or 'NOT_PROVIDED'}
            
            # Resolve function references
            for func_name, field_name in function_refs:
                logger.info(f"🔍 TEMPLATE: Looking for {func_name}.{field_name}")
                # Check both function_results and iteration_results
                func_result = next((fr['result'] for fr in function_results if fr['function_name'] == func_name), None)
                if not func_result and iteration_results:
                    func_result = next((fr['result'] for fr in iteration_results if fr['function_name'] == func_name), None)
                
                logger.info(f"🔍 TEMPLATE: Found func_result: {func_result is not None}")
                if func_result:
                    # Extract nested field like movie_data.title
                    if '.' in field_name:
                        nested_keys = field_name.split('.')
                        value = func_result
                        try:
                            for key in nested_keys:
                                value = value[key]
                            
                            # Special handling for year extraction from release_date
                            if field_name == 'release_date' and isinstance(value, str) and '-' in value:
                                year_value = value.split('-')[0]
                                format_dict[f'{func_name}.year'] = year_value
                                logger.info(f"🔍 TEMPLATE: Extracted {func_name}.year = {year_value} from release_date")
                            
                            format_dict[f'{func_name}.{field_name}'] = value
                            logger.info(f"🔍 TEMPLATE: Extracted {func_name}.{field_name} = {value}")
                        except (KeyError, TypeError) as e:
                            format_dict[f'{func_name}.{field_name}'] = 'NOT_FOUND'
                            logger.info(f"🔍 TEMPLATE: Failed to extract {func_name}.{field_name}: {e}")
                    else:
                        value = func_result.get(field_name, 'NOT_FOUND')
                        format_dict[f'{func_name}.{field_name}'] = value
                        logger.info(f"🔍 TEMPLATE: Extracted {func_name}.{field_name} = {value}")
                else:
                    format_dict[f'{func_name}.{field_name}'] = 'NOT_FOUND'
                    logger.info(f"🔍 TEMPLATE: No func_result found for {func_name}")
            
            # Also handle simple field references like {tmdb_id} and {title}
            simple_fields = re.findall(r'\{([^}]+)\}', template)
            for field in simple_fields:
                if field not in format_dict and '.' not in field:
                    # Try to get from check_movie_library_status result (check both function_results and current iteration)
                    movie_lib_result = next((fr['result'] for fr in function_results if fr['function_name'] == 'check_movie_library_status'), None)
                    if not movie_lib_result:
                        # Also check current iteration results
                        movie_lib_result = next((fr['result'] for fr in iteration_results if fr['function_name'] == 'check_movie_library_status'), None)
                    if movie_lib_result:
                        # Special handling for title and year fields
                        if field == 'title' and 'movie_data' in movie_lib_result:
                            value = movie_lib_result['movie_data'].get('title', 'NOT_FOUND')
                        elif field == 'year' and 'movie_data' in movie_lib_result:
                            release_date = movie_lib_result['movie_data'].get('release_date', '')
                            value = release_date.split('-')[0] if release_date and '-' in release_date else 'NOT_FOUND'
                        else:
                            value = movie_lib_result.get(field, 'NOT_FOUND')
                        format_dict[field] = value
                    else:
                        format_dict[field] = 'NOT_FOUND'
            
            # For templates without function references, use current function's result
            if not function_refs:
                current_result = next((fr['result'] for fr in function_results if fr['function_name'] == current_function_name), None)
                if current_result:
                    # Extract simple field names from template like {tmdb_id}
                    simple_fields = re.findall(r'\{([^}]+)\}', template)
                    for field in simple_fields:
                        if field not in format_dict:  # Don't override function references
                            format_dict[field] = current_result.get(field, 'NOT_FOUND')
            
            # Format the template
            logger.info(f"🔍 TEMPLATE: Final format_dict: {format_dict}")
            result = template.format(**format_dict)
            logger.info(f"🔍 TEMPLATE: Final result: {result}")
            return result
        except Exception as e:
            return None
    


    
    def _extract_clean_response(self, ai_response: str) -> str:
        """Extract clean SMS response from AI output - simplified for structured responses"""
        # For structured responses, we should rarely need this complex parsing
        # This is kept as a fallback for any remaining unstructured responses
        cleaned_response = ai_response.strip()
        
        # Simple cleanup - remove common prefixes
        prefixes_to_remove = [
            r'^SMS RESPONSE:\s*',
            r'^Response:\s*p',
            r'^Message:\s*'
        ]
        
        import re
        for prefix in prefixes_to_remove:
            cleaned_response = re.sub(prefix, '', cleaned_response, flags=re.IGNORECASE)
        
        return cleaned_response
    
    def _extract_metadata_from_results(self, function_results: List[Dict]) -> Dict[str, Any]:
        """Extract metadata from function results for tracking purposes"""
        metadata = {}
        
        # Extract TMDB status from check_movie_library_status results
        for fr in function_results:
            if fr['function_name'] == 'check_movie_library_status':
                result = fr['result']
                if isinstance(result, dict):
                    metadata['tmdb_status'] = result.get('tmdb_status', 'unknown')
                break
        
        # Extract Radarr status - prioritize request_download over check_radarr_status
        radarr_status_found = False
        
        # First, look for request_download results (higher priority)
        for fr in function_results:
            if fr['function_name'] == 'request_download':
                result = fr['result']
                if isinstance(result, dict):
                    radarr_status_obj = result.get('radarr_status', {})
                    if isinstance(radarr_status_obj, dict):
                        # Extract meaningful status from the object
                        action = radarr_status_obj.get('action', 'unknown')
                        if action == 'download_requested':
                            metadata['radarr_status'] = 'sent'
                        elif action == 'already_requested':
                            metadata['radarr_status'] = 'already_sent'
                        elif action == 'failed':
                            metadata['radarr_status'] = 'failed'
                        else:
                            metadata['radarr_status'] = action
                    else:
                        metadata['radarr_status'] = str(radarr_status_obj)
                    radarr_status_found = True
                    break
        
        # If no request_download found, look for check_radarr_status
        if not radarr_status_found:
            for fr in function_results:
                if fr['function_name'] == 'check_radarr_status':
                    result = fr['result']
                    if isinstance(result, dict):
                        radarr_status_obj = result.get('radarr_status', {})
                        if isinstance(radarr_status_obj, dict):
                            # For check_radarr_status, we want to know if it's downloaded
                            is_downloaded = radarr_status_obj.get('is_downloaded', False)
                            metadata['radarr_status'] = 'downloaded' if is_downloaded else 'not_downloaded'
                        else:
                            metadata['radarr_status'] = str(radarr_status_obj)
                        break
        
        return metadata
    

    def _execute_function_call(self, function_name: str, parameters: dict, services: dict):

        """Execute a function call based on the function name and parameters"""
        try:
            
            if function_name == "identify_movie_request":
                conversation_history = parameters.get('conversation_history', [])
                return services['movie_identification'].identify_movie_request(conversation_history)
                
            elif function_name == "check_movie_library_status":
                movie_name = parameters.get('movie_name', '')
                result = services['movie_library'].check_movie_library_status(movie_name)
                return result
                
            elif function_name == "check_radarr_status":
                tmdb_id = parameters.get('tmdb_id')
                movie_data =  {'title': parameters.get('movie_name')}
                
                if not movie_data:
                    logger.error(f"❌ AgenticService: check_radarr_status called without movie_data!")
                    return {
                        'success': False,
                        'error': 'CRITICAL ERROR: check_radarr_status requires movie_data parameter. You must extract movie_data from the previous check_movie_library_status result.'
                    }
                return services['radarr'].check_radarr_status(tmdb_id, movie_data)
                
            elif function_name == "request_download":
                movie_data = parameters.get('movie_data')
                phone_number = services.get('phone_number', '4384109395')  # Get from services, default for testing
                if not movie_data:
                    logger.error(f"❌ AgenticService: request_download called with missing parameters!")
                    return {
                        'success': False,
                        'error': 'CRITICAL ERROR: request_download requires BOTH movie_data AND phone_number parameters. You must extract movie_data from previous results and use phone_number from context.'
                    }
                return services['radarr'].request_download(movie_data, phone_number)
                
            elif function_name == "send_notification":
                phone_number = services.get('phone_number', '4384109395')  # Get from services, default for testing
                message_type = 'Movie Added'
                message = parameters.get('message', '')
                return services['notification'].send_notification(phone_number, message_type, message)

            else:
                logger.error(f"❌ AgenticService: Unknown function name: {function_name}")
                return {
                    'success': False,
                    'error': f'Unknown function: {function_name}'
                }
                
        except Exception as e:
            logger.error(f"❌ AgenticService: Error executing function {function_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_agentic_response(self, conversation_history, services: dict):
        """Process agentic response with function calling support"""
        try:
            
            agentic_prompt = f"""
                Yo so you're a movie agent, and you're here to help the user with their movie requests.
                You need to choose one function at the time and pass the right parameters to it.

                We will pass you the results of all previously executed functions, so you can use them to make your decisions, and follow where we are in the process.

                These are the functions you can call:
                        1. identify_movie_request
                        2. check_movie_library_status 
                        3. check_radarr_status
                        4. request_download
                        5. send_notification

                1. You need to figure out if the user is requesting a movie, and if so what movie
                2. Once you know, you need to check if the movie exists in the TMDB catalog (using check_movie_library_status)
                3. Once you know, you need to check if the movie exists in the user's Radarr library (using check_radarr_status)
                4. If the movie is not yet downloaded in radarr, you need to add it to the download queue (using request_download)
                5. If the movie is already downloaded in radarr, you need to send a notification (using send_notification) to tell the user that the movie is already downloaded (NEVER MENTION RADARR OR TMDB).

                IMPORTANT: You must use the function calling mechanism to execute these functions. Do not return JSON responses - use the provided function tools.
                IMPORTANT: Always refer to movies with the year, like "The movie (2025)".

                Here is the conversation history:
                {conversation_history}
            """          
            prompt_tokens = self._count_tokens(agentic_prompt)

            # Start conversation with AI
            try:
                messages = [{"role": "user", "content": agentic_prompt}]
                function_results = []
                max_iterations = 5  # Prevent infinite loops
                iteration = 0
            except Exception as e:
                logger.error(f"❌ AgenticService: Error setting up conversation: {str(e)}")
                logger.error(f"❌ AgenticService: Agentic prompt: {agentic_prompt}")
                raise
            
            current_state = {}
            
            
            print("conversation_history line 350")
            print(conversation_history)

            # Add conversation history to current_state
            current_state['conversation_history'] = conversation_history
            current_state['function_results'] = []

            
            while iteration < max_iterations:
                iteration += 1
                
                # Clear iteration logging
                logger.info(f"🔄 ===== STARTING ITERATION {iteration}/{max_iterations} =====")
                
                prompt = messages[-1]["content"] + f"""
                FUNCTION RESULTS: {current_state['function_results']}
                """
                message_tokens = self._count_tokens(prompt)

                logger.info(f"🔍 ITERATION {iteration} - MESSAGE TO AI:")
                # logger.info(f"🔍 Message content:\n{prompt}")
                
                # Generate agentic response with function calling
                response = self.openai_client.generate_agentic_response(
                    prompt=prompt,
                    functions=self.function_schema
                )

                print("response line 409")
                print(json.dumps(response, indent=2, sort_keys=True, default=str))
                if not response.get('success'):
                    logger.error(f"❌ AgenticService: OpenAI response failed: {response.get('error')}")
                    break
                


                try:
                    # Process function calls if any
                    if response.get('has_function_calls') and response.get('tool_calls'):
                        # Execute all function calls in this iteration
                        for i, tool_call in enumerate(response['tool_calls'], 1):
                            try:
                                # Parse function call arguments
                                function_args = tool_call.function.arguments
                                function_name = tool_call.function.name
                                
                                try:
                                    parsed_args = json.loads(function_args)
                                except Exception as parse_exc:
                                    logger.error(f"❌ AgenticService: Failed to parse function_args JSON: {function_args}")
                                    logger.error(f"❌ AgenticService: JSON parse error: {parse_exc}")
                                    raise

                                # Validate that we have the required function name and arguments
                                if not function_name:
                                    logger.error("❌ AgenticService: No function name found in tool_call")
                                    raise ValueError("No function name found in tool_call")
                                
                                if not isinstance(parsed_args, dict):
                                    logger.error(f"❌ AgenticService: Function arguments should be a dict, got: {type(parsed_args)}")
                                    raise ValueError(f"Function arguments should be a dict, got: {type(parsed_args)}")
                                # Merge function call arguments with current state
                                parameters = current_state.copy()
                                parameters.update(parsed_args)
                                
                                logger.info("response line 430\n" + json.dumps(response, indent=2, sort_keys=True, default=str))
                                logger.info(f"\n\nAbout to execute function {function_name}")
                                logger.info(f"📊 Function args: {json.dumps(parsed_args, indent=2)}")
                                logger.info(f"📊 Combined params: {json.dumps(parameters, indent=2, default=str)}")
                                # Execute the function
                                result = self._execute_function_call(function_name, parameters, services)
                                if isinstance(result, dict):
                                    current_state.update(result)
                                current_state['function_results'].append({'function_name': function_name, 'result': result})
                            except Exception as fn_exc:
                                logger.error(f"❌ AgenticService: Error executing function call: {fn_exc}")
                                current_state['function_results'].append({
                                    'function_name': function_name if 'function_name' in locals() else 'Unknown',
                                    'result': {
                                        'success': False,
                                        'error': str(fn_exc)
                                    }
                                })
                    else:
                        # No tool calls - this shouldn't happen if the AI is following instructions properly
                        logger.warning("⚠️ AgenticService: No function calls made by AI, but functions were expected")
                                
                except Exception as e:
                    logger.error(f"❌ AgenticService: Error in agentic response processing: {e}")
                    # Provide a fallback response in the current_state
                    current_state['function_results'].append({
                        'function_name': 'agentic_response_processing',
                        'result': {
                            'success': False,
                            'error': f"AgenticService: Error in agentic response processing: {e}"
                        }
                    })
            
            # Generate final response based on all function results
            if current_state['function_results']:
                # Check if any critical functions failed
                has_failures = any(not fr['result'].get('success', False) for fr in current_state['function_results'])
                
                # Extract movie name if identified
                movie_name = None
                for fr in current_state['function_results']:
                    if fr['function_name'] == 'identify_movie_request' and fr['result'].get('movie_name') != 'No movie identified':
                        movie_name = fr['result'].get('movie_name')
                        break
                
                # Check if a notification was already sent
                notification_sent = False
                for fr in current_state['function_results']:
                    if fr['function_name'] == 'send_notification' and fr['result'].get('success'):
                        notification_sent = True
                        break
                
                if notification_sent:
                    # Notification was already sent, no need for additional SMS response
                    return {
                        'response_message': '',  # Empty response since notification was sent
                        'function_results': current_state['function_results'],
                        'success': True
                    }
                
                final_context = f"""
                FUNCTION EXECUTION RESULTS:
                {chr(10).join([f"- {fr['function_name']}: {fr['result']}" for fr in current_state['function_results']])}

                MOVIE IDENTIFIED: {movie_name if movie_name else 'None'}
                
                CRITICAL RESPONSE REQUIREMENTS:
                - If a movie was identified but functions failed, acknowledge the movie and explain what went wrong
                - If no movie was identified, respond conversationally
                - NEVER give generic responses when a specific movie was requested
                - If Radarr/download functions failed, tell the user the movie couldn't be added to their library
                - Be specific about what failed and offer alternatives
                """
                
                # Use structured response for cleaner output
                final_response = self.openai_client.generate_structured_sms_response(
                    prompt=f"{services['sms_response_prompt']}\n\nContext: {final_context}"
                )
                
                if final_response.get('success'):
                    # Use the structured SMS message directly
                    print("final_response line 484")
                    print(json.dumps(final_response, indent=2, sort_keys=True, default=str))
                    sms_message = final_response.get('sms_message', '')
                    
                    # Extract metadata from function results
                    metadata = self._extract_metadata_from_results(current_state['function_results'])
                    
                    return {
                        'response_message': sms_message,
                        'function_results': current_state['function_results'],
                        'metadata': metadata,
                        'success': not has_failures  # Only success if no failures occurred
                    }
                else:
                    # Extract metadata even for failed responses
                    metadata = self._extract_metadata_from_results(current_state['function_results'])
                    return {
                        'response_message': "I processed your request but couldn't generate a proper response.",
                        'function_results': current_state['function_results'],
                        'metadata': metadata,
                        'success': False
                    }
            else:
                # No function calls were made - use structured response for clean output
                
                # Use structured response to ensure clean SMS output
                structured_response = self.openai_client.generate_structured_sms_response(
                    prompt=f"{services['sms_response_prompt']}"
                )
                print("structured_response line 505 ")
                print(structured_response)

                if structured_response.get('success'):
                    sms_message = structured_response.get('sms_message', '')
                    print("sms_message line 510")
                    print(sms_message)
                    return {
                        'response_message': sms_message,
                        'function_results': [],
                        'metadata': {},  # No function results, so empty metadata
                        'success': True
                    }
                else:
                    # Fallback to simple response
                    return {
                        'response_message': "Hey! What's up? How can I help you today?",
                        'function_results': [],
                        'metadata': {},  # No function results, so empty metadata
                        'success': True
                    }
                
        except Exception as e:
            logger.error(f"❌ AgenticService: Error in agentic response processing: {str(e)}")
            return {
                'response_message': "I received your message but encountered an error processing it.",
                'metadata': {},  # Empty metadata for error case
                'success': False,
                'error': str(e)
            }
