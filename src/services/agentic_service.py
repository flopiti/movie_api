#!/usr/bin/env python3
"""
Agentic Service
Handles agentic decision making and function calling.
"""

import logging
import json
from typing import Dict, Any, List
from ..clients.openai_client import OpenAIClient
from ..clients.PROMPTS import MOVIE_AGENT_PRIMARY_PURPOSE, MOVIE_AGENT_PROCEDURES, MOVIE_AGENT_AVAILABLE_FUNCTIONS, MOVIE_AGENT_FUNCTION_SCHEMA, MOVIE_AGENT_COMPLETE_PROMPT_TEMPLATE

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
    
    
    def _build_agentic_prompt(self, conversation_context=""):
        """Build the complete agentic prompt using the template from PROMPTS.py"""
        try:
            return MOVIE_AGENT_COMPLETE_PROMPT_TEMPLATE.format(
                primary_purpose=self.primary_purpose,
                procedures=self.procedures,
                available_functions=self.available_functions,
                conversation_context=conversation_context
            )
        except Exception as e:
            logger.error(f"❌ AgenticService: Error formatting prompt template: {str(e)}")
            logger.error(f"❌ AgenticService: Template: {MOVIE_AGENT_COMPLETE_PROMPT_TEMPLATE}")
            logger.error(f"❌ AgenticService: Primary purpose: {self.primary_purpose}")
            logger.error(f"❌ AgenticService: Procedures: {self.procedures}")
            logger.error(f"❌ AgenticService: Available functions: {self.available_functions}")
            logger.error(f"❌ AgenticService: Conversation context: {conversation_context}")
            raise
    
    def _extract_clean_response(self, ai_response: str) -> str:
        """Extract clean SMS response from AI output - simplified for structured responses"""
        # For structured responses, we should rarely need this complex parsing
        # This is kept as a fallback for any remaining unstructured responses
        cleaned_response = ai_response.strip()
        
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
            
            if function_name == "identify_movie_request":
                conversation_history = parameters.get('conversation_history', [])
                return services['movie_identification'].identify_movie_request(conversation_history)
                
            elif function_name == "check_movie_library_status":
                movie_name = parameters.get('movie_name', '')
                result = services['movie_library'].check_movie_library_status(movie_name)
                return result
                
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
                movie_title = parameters.get('movie_title', '')
                movie_year = parameters.get('movie_year', '')
                additional_context = parameters.get('additional_context', '')
                return services['notification'].send_notification(phone_number, message_type, movie_title, movie_year, additional_context)
                
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
                
                IMPORTANT: You must respond in valid JSON format with the word "json" in your response.
                """
            
            # Build agentic prompt
            try:
                agentic_prompt = self._build_agentic_prompt(conversation_context)
            except Exception as e:
                logger.error(f"❌ AgenticService: Error building agentic prompt: {str(e)}")
                logger.error(f"❌ AgenticService: Conversation context: {conversation_context}")
                raise
            
            # Log the data being sent to AI for debugging
            logger.info(f"🔍 AGENTIC PROMPT BEING SENT TO AI:")
            logger.info(f"🔍 Prompt length: {len(agentic_prompt)} characters")
            logger.info(f"🔍 Prompt content:\n{agentic_prompt}")
            
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
            
            while iteration < max_iterations:
                iteration += 1
                
                # Clear iteration logging
                logger.info(f"🔄 ===== STARTING ITERATION {iteration}/{max_iterations} =====")
                logger.info(f"🔄 AgenticService: Beginning iteration {iteration} of agentic processing")
                
                # Log the message being sent to AI
                current_message_content = messages[-1]["content"]
                logger.info(f"🔍 ITERATION {iteration} - MESSAGE TO AI:")
                logger.info(f"🔍 Message length: {len(current_message_content)} characters")
                logger.info(f"🔍 Message content:\n{current_message_content}")
                
                # Generate agentic response with function calling
                response = self.openai_client.generate_agentic_response(
                    prompt=current_message_content,
                    functions=[self.function_schema]
                )

    
                
                if not response.get('success'):
                    logger.error(f"❌ AgenticService: OpenAI response failed: {response.get('error')}")
                    break
                
                print("response line 354")
                print(response.get('response'))
                
                # Add AI response to conversation
                messages.append({"role": "assistant", "content": response.get('response', '')})
                
                # Process function calls if any
                if response.get('has_function_calls') and response.get('tool_calls'):
                    
                    # Execute all function calls in this iteration
                    iteration_results = []
                    for i, tool_call in enumerate(response['tool_calls'], 1):
                        try:
                            # Parse function call arguments
                            function_args = tool_call.function.arguments
                            parsed_args = json.loads(function_args)
                            
                            function_name = parsed_args.get('function_name')
                            parameters = parsed_args.get('parameters', {})
                            
                            
                            # Log concise parameters instead of full data
                            concise_params = self._get_concise_parameters(function_name, parameters)
                            
                            
                            # Execute the function
                            result = self._execute_function_call(function_name, parameters, services, current_message)
                            
                            
                            iteration_results.append({
                                'function_name': function_name,
                                'result': result
                            })
                            
                            
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
                        try:
                            summary = self._generate_function_summary(function_name, result)
                            function_summary += f"- {function_name}: {summary}\n"
                        except Exception as e:
                            logger.error(f"❌ AgenticService: Error generating summary for {function_name}: {str(e)}")
                            logger.error(f"❌ AgenticService: Result type: {type(result)}, Result: {result}")
                            function_summary += f"- {function_name}: Error generating summary\n"
                    
                    # Add available data for parameter passing using configuration
                    for fr in iteration_results:
                        function_name = fr['function_name']
                        result = fr['result']
                        config = self.function_summary_config.get(function_name, {})
                        
                        if config.get('available_data_template'):
                            # Parse template to extract function references and format data
                            try:
                                template = config['available_data_template']
                                available_data = self._format_available_data_template(template, function_results, conversation_context, function_name, iteration_results)
                                if available_data:
                                    function_summary += f"\nAVAILABLE DATA: {available_data}\n"
                            except Exception as e:
                                logger.error(f"❌ AgenticService: Error formatting available data for {function_name}: {str(e)}")
                                logger.error(f"❌ AgenticService: Template: {config.get('available_data_template')}")
                                logger.error(f"❌ AgenticService: Result: {result}")
                            
                    
                    # Log the function summary being sent to AI
                    logger.info(f"🔍 FUNCTION SUMMARY SENT TO AI:\n{function_summary}")
                    
                    messages.append({"role": "user", "content": function_summary})
                    function_results.extend(iteration_results)
                    
                    # Continue to next iteration to let AI decide what to do next
                    logger.info(f"🔄 ===== COMPLETED ITERATION {iteration} =====")
                    logger.info(f"🔄 AgenticService: Iteration {iteration} completed, continuing to next iteration")
                    continue
                else:
                    # No more function calls - AI is done
                    logger.info(f"🔄 ===== COMPLETED ITERATION {iteration} (FINAL) =====")
                    logger.info(f"🔄 AgenticService: Iteration {iteration} completed - no more function calls, ending agentic processing")
                    break
            
            # Log if we hit max iterations
            if iteration >= max_iterations:
                logger.warning(f"⚠️ AgenticService: Reached maximum iterations ({max_iterations}), ending agentic processing")
            
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
                    print("final_response line 484")
                    print(final_response)
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
                
                # Use structured response to ensure clean SMS output
                structured_response = self.openai_client.generate_structured_sms_response(
                    prompt=f"{services['sms_response_prompt']}\n\nUser message: {current_message}"
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
