#!/usr/bin/env python3
"""
OpenAI API client for cleaning movie filenames and generating SMS responses.
"""

import logging
from typing import Dict, Any
from openai import OpenAI
from .PROMPTS import (
    MOVIE_DETECTION_PROMPT, 
    FILENAME_CLEANING_PROMPT, 
    FILENAME_REFINEMENT_PROMPT, 
    FILENAME_ALTERNATIVE_CLEANING_PROMPT,
    FILENAME_CLEANING_SYSTEM_MESSAGE,
    FILENAME_ALTERNATIVE_CLEANING_SYSTEM_MESSAGE
)

logger = logging.getLogger(__name__)

class OpenAIClient:
    """OpenAI API client for cleaning movie filenames."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            try:
                # Initialize OpenAI client with explicit parameters to avoid proxy issues
                import httpx
                self.client = OpenAI(
                    api_key=api_key,
                    timeout=30.0,
                    max_retries=2,
                    http_client=httpx.Client()
                )
            except Exception as e:
                self.client = None
        else:
            self.client = None
    
    def clean_filename(self, filename: str) -> Dict[str, Any]:
        """Clean a movie filename using OpenAI to extract the movie title."""
        if not self.client:
            return {"error": "OpenAI API key not configured", "original_filename": filename}

        # Step 1: Initial cleaning
        initial_prompt = FILENAME_CLEANING_PROMPT.format(filename=filename)

        try:
            # Step 1: Initial cleaning
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": FILENAME_CLEANING_SYSTEM_MESSAGE},
                    {"role": "user", "content": initial_prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            initial_cleaned_title = response.choices[0].message.content.strip()
            
            # Check if OpenAI returned a generic response asking for clarification
            if any(phrase in initial_cleaned_title.lower() for phrase in [
                "please provide", "could you provide", "i'm here to help", 
                "can you provide", "need the filename", "missing", "clarification"
            ]):
                # Extract filename without extension as fallback
                import os
                initial_cleaned_title = os.path.splitext(os.path.basename(filename))[0]

            # Step 2: Check if the result needs further cleaning and ask for alternative
            # Look for patterns that suggest the title still has unwanted elements
            unwanted_patterns = [
                '~', '(', ')', '[', ']', '|', '\\', '/', ':', ';', '=', '+', '*', '?', '<', '>', '"', "'",
                'BluRay', 'x264', 'x265', '1080p', '720p', '4K', 'HDR', 'WEBRIP', 'HDRip', 'BRRip',
                'YIFY', 'RARBG', 'TGx', 'EVO', 'FUM', 'Dual', 'Multi', 'Eng', 'Jps', 'Rus', 'Ukr',
                '5.1', '2.0', 'DTS', 'AC3', 'AAC', 'Subs', 'Subbed', 'Subtitles',
                'Criterion Collection', 'Arrow Video', 'Shout Factory', 'Kino Lorber', 'StudioCanal'
            ]
            
            needs_further_cleaning = any(pattern in initial_cleaned_title for pattern in unwanted_patterns)
            
            if needs_further_cleaning:
                # Step 2: Ask for alternative cleaner version
                alternative_prompt = FILENAME_ALTERNATIVE_CLEANING_PROMPT.format(
                    filename=filename, 
                    initial_cleaned_title=initial_cleaned_title
                )

                alternative_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": FILENAME_ALTERNATIVE_CLEANING_SYSTEM_MESSAGE},
                        {"role": "user", "content": alternative_prompt}
                    ],
                    max_tokens=50,
                    temperature=0.1
                )
                
                final_cleaned_title = alternative_response.choices[0].message.content.strip()

                return {
                    "cleaned_title": final_cleaned_title,
                    "original_filename": filename,
                    "initial_cleaning": initial_cleaned_title,
                    "alternative_cleaning": final_cleaned_title,
                    "success": True
                }
            else:
                return {
                    "cleaned_title": initial_cleaned_title,
                    "original_filename": filename,
                    "success": True
                }
            
        except Exception as e:
            pass
            return {
                "error": f"OpenAI API error: {str(e)}",
                "original_filename": filename,
                "success": False
            }
    
    def generate_sms_response(self, message: str, sender: str, prompt_template: str, movie_context: str = "") -> Dict[str, Any]:
        """Generate an SMS response using ChatGPT with a custom prompt."""
        if not self.client:
            return {"error": "OpenAI API key not configured", "success": False}
        
        try:
            # Replace placeholders in the prompt template
            formatted_prompt = prompt_template.replace('{message}', message)
            formatted_prompt = formatted_prompt.replace('{sender}', sender)
            
            # Add movie context if provided
            if movie_context:
                formatted_prompt += f"\n\nContext: {movie_context}"

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": formatted_prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Ensure response is SMS-friendly (under 160 characters)
            if len(response_text) > 160:
                response_text = response_text[:157] + "..."

            return {
                "success": True,
                "response": response_text,
                "original_message": message,
                "sender": sender
            }
            
        except Exception as e:
            pass
            return {
                "error": f"OpenAI API error: {str(e)}",
                "success": False
            }
    
    def getMovieName(self, conversation: list) -> Dict[str, Any]:
        """Extract movie name with year from a conversation using OpenAI."""
        if not self.client:
            return {"error": "OpenAI API key not configured", "success": False}
        
        try:
            # Limit to last 10 messages (most recent are first)
            limited_conversation = conversation[:10]
            
            # Join conversation into a single string
            conversation_text = "\n".join(limited_conversation)
            
            # Log what we're sending to OpenAI
            logger.info(f"🎬 OpenAI getMovieName: Analyzing {len(limited_conversation)} messages for movie detection")
            
            # Use prompt from PROMPTS file
            prompt = MOVIE_DETECTION_PROMPT.format(conversation_text=conversation_text)
            
            # Log the full prompt being sent to OpenAI
            logger.info(f"🎬 OpenAI getMovieName: FULL PROMPT SENT TO OPENAI:")
            logger.info(f"🎬 OpenAI getMovieName: {prompt}")

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean up the response
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            
            logger.info(f"🎬 OpenAI getMovieName: Detected movie: '{response_text}'")
            
            return {
                "success": True,
                "movie_name": response_text,
                "conversation": limited_conversation
            }
            
        except Exception as e:
            pass
            return {
                "error": f"OpenAI API error: {str(e)}",
                "success": False
            }
