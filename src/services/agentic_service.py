#!/usr/bin/env python3
"""
Agentic Service
Handles agentic decision making and function calling.
"""

import logging
import json
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
                            logger.info(f"🔧 AgenticService: Function Call #{i} Parameters: {parameters}")
                            
                            # Execute the function
                            result = self._execute_function_call(function_name, parameters, services, current_message)
                            
                            logger.info(f"🔧 AgenticService: Function Call #{i} Result: {result}")
                            
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
                        function_summary += f"- {fr['function_name']}: {fr['result']}\n"
                    
                    # Add explicit instructions for next steps
                    function_summary += f"\nNEXT STEPS REQUIRED:\n"
                    if any(fr['function_name'] == 'identify_movie_request' for fr in iteration_results):
                        logger.info(f"🔍 AgenticService: Processing identify_movie_request branch")
                        # Check if movie was identified
                        movie_result = next((fr['result'] for fr in iteration_results if fr['function_name'] == 'identify_movie_request'), None)
                        if movie_result and movie_result.get('movie_name') == 'No movie identified':
                            function_summary += "- NO MOVIE IDENTIFIED - STOP calling functions and respond conversationally\n"
                        else:
                            function_summary += "- You MUST call check_movie_library_status next\n"
                    elif any(fr['function_name'] == 'check_movie_library_status' for fr in iteration_results):
                        logger.info(f"🔍 AgenticService: Processing check_movie_library_status branch")
                        function_summary += "- You MUST call check_radarr_status next\n"
                        # Extract the actual data from the result
                        movie_lib_result = next((fr['result'] for fr in iteration_results if fr['function_name'] == 'check_movie_library_status'), None)
                        if movie_lib_result:
                            tmdb_id = movie_lib_result.get('tmdb_id')
                            movie_data = movie_lib_result.get('movie_data')
                            function_summary += f"- AVAILABLE DATA: tmdb_id={tmdb_id}, movie_data={movie_data}\n"
                            function_summary += f"- CRITICAL: You MUST pass BOTH tmdb_id AND movie_data to check_radarr_status\n"
                            function_summary += f"- CORRECT PARAMETERS: {{'tmdb_id': {tmdb_id}, 'movie_data': {movie_data}}}\n"
                            function_summary += f"- WRONG PARAMETERS: {{'tmdb_id': {tmdb_id}}}  <-- DO NOT DO THIS\n"
                    elif any(fr['function_name'] == 'check_radarr_status' for fr in iteration_results):
                        logger.info(f"🔍 AgenticService: Processing check_radarr_status branch")
                        function_summary += "- You MUST call request_download next\n"
                        # Extract movie_data from the check_movie_library_status result (from ALL function results)
                        movie_lib_result = next((fr['result'] for fr in function_results if fr['function_name'] == 'check_movie_library_status'), None)
                        logger.info(f"🔍 AgenticService: Looking for check_movie_library_status result in function_results")
                        logger.info(f"🔍 AgenticService: Found movie_lib_result: {movie_lib_result is not None}")
                        if movie_lib_result:
                            movie_data = movie_lib_result.get('movie_data')
                            logger.info(f"🔍 AgenticService: Extracted movie_data: {movie_data is not None}")
                            function_summary += f"- CRITICAL: You MUST pass BOTH movie_data AND phone_number to request_download\n"
                            function_summary += f"- CORRECT PARAMETERS: {{'movie_data': {movie_data}, 'phone_number': '+14384109395'}}\n"
                            function_summary += f"- WRONG PARAMETERS: {{'tmdb_id': 201088, 'phone_number': '+14384109395'}}  <-- DO NOT DO THIS\n"
                        else:
                            logger.info(f"🔍 AgenticService: No movie_lib_result found!")
                    elif any(fr['function_name'] == 'request_download' for fr in iteration_results):
                        logger.info(f"🔍 AgenticService: Processing request_download branch")
                        function_summary += "- You MUST call send_notification next\n"
                        # Extract movie_data from the check_movie_library_status result (from ALL function results)
                        movie_lib_result = next((fr['result'] for fr in function_results if fr['function_name'] == 'check_movie_library_status'), None)
                        if movie_lib_result:
                            movie_data = movie_lib_result.get('movie_data')
                            function_summary += f"- CRITICAL: You MUST pass phone_number, message_type, AND movie_data to send_notification\n"
                            function_summary += f"- CORRECT PARAMETERS: {{'phone_number': '+14384109395', 'message_type': 'download_started', 'movie_data': {movie_data}, 'additional_context': 'Download requested'}}\n"
                            function_summary += f"- WRONG PARAMETERS: {{'phone_number': '', 'message_type': 'download_started'}}  <-- DO NOT DO THIS\n"
                        else:
                            function_summary += "- Workflow complete - generate final SMS response\n"
                    
                    # Log the function summary being sent to AI
                    logger.info(f"🔍 AgenticService: Function summary being sent to AI:")
                    logger.info(f"🔍 AgenticService: {function_summary}")
                    
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
