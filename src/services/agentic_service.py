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

IMPORTANT: You must either:
1. Call the appropriate functions to gather information and take actions, OR
2. Provide a direct SMS response to the user

CRITICAL: DO NOT return internal instructions, explanations, or prompts to the user. 
- DO NOT say "SMS RESPONSE:" or "Instead, send a..."
- DO NOT explain what you're going to do
- DO NOT include phrases like "there's no need to call functions"
- Just provide the actual SMS message the user should receive

Always provide ONLY a clean, user-friendly SMS response."""
    
    def _extract_clean_response(self, ai_response: str) -> str:
        """Extract clean SMS response from AI output, removing internal instructions"""
        # Look for quoted text after "SMS RESPONSE:" or similar patterns
        import re
        
        # Pattern to find text in quotes after "SMS RESPONSE:"
        sms_pattern = r'(?:SMS RESPONSE:|Response:|Message:)\s*["\']([^"\']+)["\']'
        match = re.search(sms_pattern, ai_response, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern to find text in quotes at the end
        quote_pattern = r'["\']([^"\']+)["\']\s*$'
        match = re.search(quote_pattern, ai_response)
        if match:
            return match.group(1).strip()
        
        # If no quotes found, return the original response
        return ai_response.strip()
    
    def _execute_function_call(self, function_name: str, parameters: dict, services: dict):
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
                return services['radarr'].check_radarr_status(tmdb_id, movie_data)
                
            elif function_name == "request_download":
                movie_data = parameters.get('movie_data')
                phone_number = parameters.get('phone_number')
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
                logger.error(f"❌ AgenticService: OpenAI response failed: {response.get('error')}")
                return {
                    'response_message': "I received your message but couldn't process it properly.",
                    'success': False
                }
            
            # Process function calls if any
            if response.get('has_function_calls') and response.get('tool_calls'):
                logger.info(f"🔧 AgenticService: Processing {len(response['tool_calls'])} function calls")
                
                function_results = []
                for tool_call in response['tool_calls']:
                    try:
                        # Parse function call arguments
                        function_args = tool_call.function.arguments
                        parsed_args = json.loads(function_args)
                        
                        function_name = parsed_args.get('function_name')
                        parameters = parsed_args.get('parameters', {})
                        
                        # Execute the function
                        result = self._execute_function_call(function_name, parameters, services)
                        function_results.append({
                            'function_name': function_name,
                            'result': result
                        })
                        
                        logger.info(f"✅ AgenticService: Function {function_name} executed successfully")
                        
                    except Exception as e:
                        logger.error(f"❌ AgenticService: Error processing function call: {str(e)}")
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
                    prompt_template=services['sms_response_prompt'],
                    movie_context=final_context
                )
                
                if final_response.get('success'):
                    # Extract clean response even from function call results
                    clean_response = self._extract_clean_response(final_response['response'])
                    return {
                        'response_message': clean_response,
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
                # No function calls - extract clean response from AI output
                ai_response = response.get('response', '')
                logger.info(f"🔍 AgenticService: No function calls, AI response: {ai_response}")
                clean_response = self._extract_clean_response(ai_response)
                logger.info(f"🔍 AgenticService: Extracted clean response: {clean_response}")
                
                # Check if the extracted response still contains internal instructions
                if any(phrase in clean_response.lower() for phrase in [
                    "let's use the", "we need to prompt", "internal instructions", 
                    "function calling", "available functions", "procedures for",
                    "sms response:", "there's no need to call", "instead, send a",
                    "since the user's message", "doesn't contain any specific",
                    "no need to call any functions", "send a friendly sms",
                    "doesn't contain any specific request", "at this point",
                    "initiate the conversation", "ask what movie"
                ]):
                    logger.warning(f"⚠️ AgenticService: Extracted response still contains internal instructions")
                    # Fall back to simple SMS response
                    fallback_response = self.openai_client.generate_sms_response(
                        message=current_message,
                        sender=phone_number,
                        prompt_template=services['sms_response_prompt'],
                        movie_context=""
                    )
                    
                    if fallback_response.get('success'):
                        # Extract clean response from fallback too
                        clean_fallback = self._extract_clean_response(fallback_response['response'])
                        return {
                            'response_message': clean_fallback,
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
                    # Response looks clean
                    return {
                        'response_message': clean_response,
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
