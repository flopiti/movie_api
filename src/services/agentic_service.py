#!/usr/bin/env python3
"""
Agentic Service
Handles agentic decision making and function calling.
"""

import logging
import json
from typing import Dict, Any, List
from ..clients.openai_client import OpenAIClient
from ..clients.PROMPTS import MOVIE_AGENT_PRIMARY_PURPOSE, MOVIE_AGENT_PROCEDURES, MOVIE_AGENT_AVAILABLE_FUNCTIONS, MOVIE_AGENT_FUNCTION_SCHEMA

logger = logging.getLogger(__name__)

class AgenticService:
    """Service for agentic decision making and function calling"""
    
    def __init__(self, openai_client: OpenAIClient):
        self.openai_client = openai_client
        self.primary_purpose = MOVIE_AGENT_PRIMARY_PURPOSE
        self.procedures = MOVIE_AGENT_PROCEDURES
        self.available_functions = MOVIE_AGENT_AVAILABLE_FUNCTIONS
        self.function_schema = MOVIE_AGENT_FUNCTION_SCHEMA
        
        # Load function summary configuration
        self.function_summary_config = self._load_function_summary_config()
    
    def _load_function_summary_config(self):
        """Load function summary configuration from JSON file"""
        try:
            import os
            config_path = os.path.join(os.path.dirname(__file__), 'function_summary_config.json')
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load function summary config: {e}")
            return {}
    
    def _extract_field_value(self, result: Dict[str, Any], field_path: str) -> Any:
        """Extract field value from nested dictionary using dot notation"""
        try:
            keys = field_path.split('.')
            value = result
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
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
                field_values[field] = self._extract_field_value(result, field)
        
        # Format template with extracted values
        try:
            return template.format(**field_values)
        except KeyError as e:
            logger.warning(f"Missing field {e} for function {function_name}")
            return f"{function_name}: Success" if result.get('success', False) else f"{function_name}: Failed"
    
    def _get_concise_parameters(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate concise parameter logging using configuration"""
        config = self.function_summary_config.get(function_name, self.function_summary_config.get('default', {}))
        parameter_fields = config.get('parameter_fields', [])
        
        concise = {}
        for field_config in parameter_fields:
            if isinstance(field_config, dict):
                # Handle complex field configuration
                field_name = field_config.get('field')
                field_type = field_config.get('type', 'value')
                field_label = field_config.get('label', field_name)
                
                if field_type == 'count':
                    # Count items in list/array
                    value = parameters.get(field_name, [])
                    concise[field_label] = f"{len(value)} {field_label}"
                else:
                    # Regular value extraction
                    value = self._extract_field_value(parameters, field_name)
                    concise[field_label] = value
            else:
                # Handle simple string field names
                value = self._extract_field_value(parameters, field_config)
                concise[field_config] = value
        
        return concise
    
    def _build_agentic_prompt(self, conversation_context=""):
        """Build the complete agentic prompt by combining all prompt components"""
        return f"""{self.primary_purpose}

{self.procedures}

{self.available_functions}

CURRENT CONTEXT:
{conversation_context}

Based on the above context and available functions, analyze the user's request and determine the appropriate actions to take.

IMPORTANT: You are REQUIRED to complete the full movie workflow ONLY if a movie is identified. If no movie is identified, respond conversationally and naturally - be friendly and warm, not robotic. 

CRITICAL FUNCTION CALLING REQUIREMENTS:
- ALWAYS start with identify_movie_request to understand user intent
- When calling identify_movie_request, you MUST pass the FULL conversation history from the context above
- If NO MOVIE is identified (result: "No movie identified"), STOP calling functions and respond conversationally
- If a movie IS identified, you MUST call functions in this exact sequence:
  1. check_movie_library_status (REQUIRED after movie identification)
  2. check_radarr_status (REQUIRED after getting movie data)
  3. request_download (REQUIRED unless movie is already downloaded)
- Do NOT call additional functions if no movie was identified
- Do NOT promise to notify users unless you actually call request_download
- After each function call, you will receive the results and should continue with the next required function
- Continue calling functions until the complete workflow is finished OR no movie is identified
- NEVER stop after check_movie_library_status - you MUST always call check_radarr_status next
- NEVER stop after check_radarr_status - you MUST always call request_download next (unless movie is already downloaded)
- The workflow is NOT complete until you have called request_download OR no movie was identified

CRITICAL PARAMETER PASSING:
- When calling check_radarr_status: Pass BOTH tmdb_id AND movie_data from the previous function result
- When calling request_download: Pass BOTH movie_data AND phone_number (use the phone number from context)
- NEVER call check_radarr_status with only tmdb_id - you MUST pass movie_data too
- NEVER call request_download with only tmdb_id - you MUST pass movie_data and phone_number
- Extract ALL required parameters from previous function results - do NOT call functions with missing parameters
- If a function fails due to missing parameters, inform the user about the failure

IMPORTANT: You must either:
1. Call the appropriate functions to gather information and take actions, OR
2. Provide a direct SMS response to the user

CRITICAL: DO NOT return internal instructions, explanations, or prompts to the user. 
- DO NOT say "SMS RESPONSE:" or "Instead, send a..."
- DO NOT explain what you're going to do
- DO NOT include phrases like "there's no need to call functions"
- Just provide the actual SMS message the user should receive

CONVERSATIONAL RESPONSES:
- For casual greetings and conversation - respond naturally and warmly
- Don't immediately ask for movie requests - let the conversation flow naturally
- Show personality and be friendly, not robotic

Always provide ONLY a clean, user-friendly SMS response."""
    
    def _extract_clean_response(self, ai_response: str) -> str:
        """Extract clean SMS response from AI output - simplified for structured responses"""
        # For structured responses, we should rarely need this complex parsing
        # This is kept as a fallback for any remaining unstructured responses
        cleaned_response = ai_response.strip()
        logger.info(f"🔍 AgenticService: Fallback response extraction: '{cleaned_response}'")
        
        # Simple cleanup - remove common prefixes
        prefixes_to_remove = [
            r'^SMS RESPONSE:\s*',
            r'^Response:\s*',
            r'^Message:\s*'
        ]
        
        import re
        for prefix in prefixes_to_remove:
            cleaned_response = re.sub(prefix, '', cleaned_response, flags=re.IGNORECASE)
        
        return cleaned_response
    
    def _execute_function_call(self, function_name: str, parameters: dict, services: dict, current_message: str = ""):
        """Execute a function call based on the function name and parameters"""
        try:
            logger.info(f"🔧 AgenticService: Executing function {function_name} with parameters: {parameters}")
            
            if function_name == "identify_movie_request":
                conversation_history = parameters.get('conversation_history', [])
                return services['movie_identification'].identify_movie_request(conversation_history)
                
            elif function_name == "check_movie_library_status":
                movie_name = parameters.get('movie_name', '')
                return services['movie_library'].check_movie_library_status(movie_name)
                
            elif function_name == "check_radarr_status":
                tmdb_id = parameters.get('tmdb_id')
                movie_data = parameters.get('movie_data')
                if not movie_data:
                    logger.error(f"❌ AgenticService: check_radarr_status called without movie_data! Parameters: {parameters}")
                    return {
                        'success': False,
                        'error': 'CRITICAL ERROR: check_radarr_status requires movie_data parameter. You must extract movie_data from the previous check_movie_library_status result.'
                    }
                return services['radarr'].check_radarr_status(tmdb_id, movie_data)
                
            elif function_name == "request_download":
                movie_data = parameters.get('movie_data')
                phone_number = parameters.get('phone_number')
                if not movie_data or not phone_number:
                    logger.error(f"❌ AgenticService: request_download called with missing parameters! Parameters: {parameters}")
                    return {
                        'success': False,
                        'error': 'CRITICAL ERROR: request_download requires BOTH movie_data AND phone_number parameters. You must extract movie_data from previous results and use phone_number from context.'
                    }
                return services['radarr'].request_download(movie_data, phone_number)
                
            elif function_name == "send_notification":
                phone_number = parameters.get('phone_number')
                message_type = parameters.get('message_type')
                movie_data = parameters.get('movie_data')
                additional_context = parameters.get('additional_context', '')
                return services['notification'].send_notification(phone_number, message_type, movie_data, additional_context)
                
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
    
    def process_agentic_response(self, conversation_history, phone_number, services: dict):
        """Process agentic response with function calling support"""
        try:
            # Extract current message (the most recent USER message)
            # Conversation history is ordered with newest message FIRST
            current_message = None
            for message in conversation_history:
                if message.startswith("USER: "):
                    current_message = message.replace("USER: ", "")
                    break  # Take the FIRST USER message (which is the newest)
            
            if not current_message:
                return {
                    'response_message': "I received your message but couldn't process it properly.",
                    'success': False
                }
            
            # Build conversation context - use the full conversation history
            conversation_context = f"""
CONVERSATION HISTORY:
{chr(10).join(conversation_history)}

CURRENT USER MESSAGE: {current_message}
USER PHONE NUMBER: {phone_number}

CRITICAL: When calling request_download, you MUST pass the phone_number parameter with the value: {phone_number}
"""
            
            # Build agentic prompt
            agentic_prompt = self._build_agentic_prompt(conversation_context)
            
            # Log the data being sent to AI for debugging
            logger.info(f"🔍 AgenticService: Data being sent to AI:")
            logger.info(f"🔍 AgenticService: Current message: '{current_message}'")
            logger.info(f"🔍 AgenticService: Phone number: '{phone_number}'")
            logger.info(f"🔍 AgenticService: Full conversation: {conversation_history}")
            logger.info(f"🔍 AgenticService: Conversation context length: {len(conversation_context)} chars")
            
            # Start conversation with AI
            messages = [{"role": "user", "content": agentic_prompt}]
            function_results = []
            max_iterations = 5  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"🔄 AgenticService: Starting iteration {iteration}")
                
                # Generate agentic response with function calling
                response = self.openai_client.generate_agentic_response(
                    prompt=messages[-1]["content"],
                    functions=[self.function_schema]
                )
                
                if not response.get('success'):
                    logger.error(f"❌ AgenticService: OpenAI response failed: {response.get('error')}")
                    break
                
                # Add AI response to conversation
                messages.append({"role": "assistant", "content": response.get('response', '')})
                
                # Process function calls if any
                if response.get('has_function_calls') and response.get('tool_calls'):
                    logger.info(f"🔧 AgenticService: Processing {len(response['tool_calls'])} function calls in iteration {iteration}")
                    
                    # Execute all function calls in this iteration
                    iteration_results = []
                    for i, tool_call in enumerate(response['tool_calls'], 1):
                        try:
                            # Parse function call arguments
                            function_args = tool_call.function.arguments
                            parsed_args = json.loads(function_args)
                            
                            function_name = parsed_args.get('function_name')
                            parameters = parsed_args.get('parameters', {})
                            
                            logger.info(f"🔧 AgenticService: Function Call #{i}: {function_name}")
                            
                            # Log concise parameters instead of full data
                            concise_params = self._get_concise_parameters(function_name, parameters)
                            logger.info(f"🔧 AgenticService: Function Call #{i} Parameters: {concise_params}")
                            
                            # Execute the function
                            result = self._execute_function_call(function_name, parameters, services, current_message)
                            
                            # Log concise result info
                            if function_name == 'identify_movie_request' and result.get('success'):
                                logger.info(f"🔧 AgenticService: Function Call #{i} Result: Movie identified: {result.get('movie_name', 'Unknown')}")
                            elif function_name == 'check_movie_library_status' and result.get('success'):
                                movie_data = result.get('movie_data', {})
                                logger.info(f"🔧 AgenticService: Function Call #{i} Result: Movie found: {movie_data.get('title', 'Unknown')} ({movie_data.get('year', 'Unknown')})")
                            else:
                                logger.info(f"🔧 AgenticService: Function Call #{i} Result: {result.get('success', False)}")
                            
                            iteration_results.append({
                                'function_name': function_name,
                                'result': result
                            })
                            
                            logger.info(f"✅ AgenticService: Function Call #{i} ({function_name}) completed successfully")
                            
                        except Exception as e:
                            logger.error(f"❌ AgenticService: Function Call #{i} Error: {str(e)}")
                            iteration_results.append({
                                'function_name': 'unknown',
                                'result': {'success': False, 'error': str(e)}
                            })
                    
                    # Add function results to conversation for next iteration
                    function_summary = f"Function execution results:\n"
                    for fr in iteration_results:
                        function_name = fr['function_name']
                        result = fr['result']
                        
                        # Generate concise summary using configuration
                        summary = self._generate_function_summary(function_name, result)
                        function_summary += f"- {function_name}: {summary}\n"
                    
                    # Add available data for parameter passing using configuration
                    for fr in iteration_results:
                        function_name = fr['function_name']
                        result = fr['result']
                        config = self.function_summary_config.get(function_name, {})
                        
                        if config.get('available_data_template'):
                            logger.info(f"🔍 AgenticService: Processing {function_name} branch")
                            
                            # For functions that need data from previous results, get it from function_results
                            if function_name in ['check_radarr_status', 'request_download']:
                                movie_lib_result = next((fr['result'] for fr in function_results if fr['function_name'] == 'check_movie_library_status'), None)
                                if movie_lib_result:
                                    # Extract phone number from conversation context
                                    phone_number = None
                                    if conversation_context:
                                        # Try to extract phone number from context
                                        import re
                                        phone_match = re.search(r'USER PHONE NUMBER:\s*([+\d\s\-\(\)]+)', conversation_context, re.IGNORECASE)
                                        if phone_match:
                                            phone_number = phone_match.group(1).strip()
                                    
                                    # Only add available data if we have a phone number
                                    if phone_number:
                                        available_data = config['available_data_template'].format(
                                            tmdb_id=movie_lib_result.get('tmdb_id'),
                                            movie_data=movie_lib_result.get('movie_data'),
                                            phone_number=phone_number
                                        )
                                        function_summary += f"\nAVAILABLE DATA: {available_data}\n"
                            else:
                                # For check_movie_library_status, use its own result
                                available_data = config['available_data_template'].format(
                                    tmdb_id=result.get('tmdb_id'),
                                    movie_data=result.get('movie_data')
                                )
                                function_summary += f"\nAVAILABLE DATA: {available_data}\n"
                    
                    # Log the function summary being sent to AI
                    logger.info(f"🔍 AgenticService: Function summary being sent to AI")
                    
                    messages.append({"role": "user", "content": function_summary})
                    function_results.extend(iteration_results)
                    
                    # Continue to next iteration to let AI decide what to do next
                    continue
                else:
                    # No more function calls - AI is done
                    logger.info(f"🔍 AgenticService: No more function calls in iteration {iteration}")
                    break
            
            # Generate final response based on all function results
            if function_results:
                # Check if any critical functions failed
                has_failures = any(not fr['result'].get('success', False) for fr in function_results)
                
                # Extract movie name if identified
                movie_name = None
                for fr in function_results:
                    if fr['function_name'] == 'identify_movie_request' and fr['result'].get('movie_name') != 'No movie identified':
                        movie_name = fr['result'].get('movie_name')
                        break
                
                # Check if a notification was already sent
                notification_sent = False
                for fr in function_results:
                    if fr['function_name'] == 'send_notification' and fr['result'].get('success'):
                        notification_sent = True
                        break
                
                if notification_sent:
                    # Notification was already sent, no need for additional SMS response
                    logger.info(f"📱 AgenticService: Notification already sent, skipping final SMS response")
                    return {
                        'response_message': '',  # Empty response since notification was sent
                        'function_results': function_results,
                        'success': True
                    }
                
                final_context = f"""
                FUNCTION EXECUTION RESULTS:
                {chr(10).join([f"- {fr['function_name']}: {fr['result']}" for fr in function_results])}

                ORIGINAL USER MESSAGE: {current_message}
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
                    sms_message = final_response.get('sms_message', '')
                    return {
                        'response_message': sms_message,
                        'function_results': function_results,
                        'success': not has_failures  # Only success if no failures occurred
                    }
                else:
                    return {
                        'response_message': "I processed your request but couldn't generate a proper response.",
                        'function_results': function_results,
                        'success': False
                    }
            else:
                # No function calls were made - use structured response for clean output
                logger.info(f"🔍 AgenticService: NO FUNCTION CALLS MADE - generating structured response")
                
                # Use structured response to ensure clean SMS output
                structured_response = self.openai_client.generate_structured_sms_response(
                    prompt=f"{services['sms_response_prompt']}\n\nUser message: {current_message}"
                )
                
                if structured_response.get('success'):
                    sms_message = structured_response.get('sms_message', '')
                    logger.info(f"🔍 AgenticService: Generated structured SMS response: {sms_message}")
                    return {
                        'response_message': sms_message,
                        'function_results': [],
                        'success': True
                    }
                else:
                    # Fallback to simple response
                    return {
                        'response_message': "Hey! What's up? How can I help you today?",
                        'function_results': [],
                        'success': True
                    }
                
        except Exception as e:
            logger.error(f"❌ AgenticService: Error in agentic response processing: {str(e)}")
            return {
                'response_message': "I received your message but encountered an error processing it.",
                'success': False,
                'error': str(e)
            }
