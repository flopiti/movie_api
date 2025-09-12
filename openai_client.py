#!/usr/bin/env python3
"""
OpenAI API client for cleaning movie filenames and generating SMS responses.
"""

import logging
from typing import Dict, Any
from openai import OpenAI

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
        initial_prompt = f"""
You are a movie filename parser. I will provide you with a movie filename, and you must extract the clean movie title.

IMPORTANT: You must ALWAYS process the filename I give you. Never ask for clarification or more information.

Your goal is to extract ONLY the core movie title for TMDB search purposes. Remove these elements from the filename:
- File extensions (.mp4, .mkv, .avi, etc.)
- Quality indicators like 1080p, 720p, 4K, BluRay, WEBRIP, HDRip, etc.
- Release group tags in brackets like [YIFY], [RARBG], [TGx], [EVO], [FUM]
- Audio/video codec info like x264, x265, AAC, AC3, etc.
- Language indicators like "Eng", "Jps", "Rus", "Ukr", "Multi", "Dual"
- Subtitle information like "Subs", "Subtitles", "Subbed"
- Audio track information like "5.1", "2.0", "DTS", "AC3"
- Content type indicators like "Anime", "Movie", "Film" (unless it's part of the actual title)
- Edition indicators like "Directors Cut", "Extended Cut", "Unrated", "Rated", "Theatrical Cut", "Final Cut"
- Version indicators like "Special Edition", "Collectors Edition", "Anniversary Edition"
- Collection/Label names like "Criterion Collection", "Arrow Video", "Shout Factory", "Kino Lorber", "StudioCanal"
- Extra periods, underscores, and dashes used as separators
- Any other technical metadata

CRITICAL: DO NOT remove or modify:
- Years (e.g., "1999", "2010", "1968") - these are CRUCIAL for finding the correct movie
- Director names (e.g., "by Christopher Nolan", "dir. Spielberg")
- Actor names that are part of the title
- Original movie titles in other languages
- Subtitle information that helps identify the movie
- Movie sequel numbers (e.g., "Cars 2", "Toy Story 3", "The Matrix 2", "Iron Man 2", "Inside Out 2", "Frozen 2", "Finding Dory", "Monsters University")
- Roman numerals in titles (e.g., "Rocky IV", "Star Wars Episode IV")
- ANY numbers that appear to be part of the movie title (e.g., "2", "3", "4", "II", "III", "IV")

Examples:
- "Akira Anime Eng Jps Rus Ukr Multi Subs" → "Akira"
- "The Matrix 1999 1080p BluRay x264" → "The Matrix 1999"
- "Cars 2 (2011) 1080p BluRay x264" → "Cars 2 2011"
- "Toy Story 3 2010 720p WEBRIP" → "Toy Story 3 2010"
- "Iron Man 2 2010 BluRay x264" → "Iron Man 2 2010"
- "Inside Out 2 2024 1080p BluRay x264" → "Inside Out 2 2024"
- "Frozen 2 2019 720p WEBRIP" → "Frozen 2 2019"
- "Finding Dory 2016 BluRay x264" → "Finding Dory 2016"
- "Monsters University 2013 1080p" → "Monsters University 2013"
- "Certified Copy Criterion Collection 1080p BluRay x264" → "Certified Copy"
- "The Seventh Seal Criterion Collection 1957" → "The Seventh Seal 1957"
- "Inception by Christopher Nolan 2010" → "Inception by Christopher Nolan 2010"
- "Alien Resurrection Directors Cut 1997" → "Alien Resurrection 1997"
- "Blade Runner Final Cut 1982" → "Blade Runner 1982"
- "The Lord of the Rings Extended Edition" → "The Lord of the Rings"
- "Signs of Life 1968" → "Signs of Life 1968"

If you cannot determine a clean movie title, return the filename as-is without the file extension.

Filename to process: {filename}

Extract the clean movie title from this filename:"""

        try:
            # Step 1: Initial cleaning
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a movie filename parser that ALWAYS processes the given filename and extracts ONLY the core movie title for TMDB search. Remove language indicators, subtitle info, edition indicators (Directors Cut, Extended Cut, etc.), and technical metadata. Preserve director names, actor names, CRITICALLY preserve movie sequel numbers (like Cars 2, Toy Story 3, Iron Man 2), and CRUCIALLY preserve YEARS (like 1999, 2010, 1968) which are essential for finding the correct movie. Never ask for clarification."},
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
                alternative_prompt = f"""
The previous cleaning of this filename still contains unwanted elements. Please provide a cleaner alternative version.

Original filename: {filename}
Previous cleaning result: {initial_cleaned_title}

Please provide a cleaner version that removes ALL of these elements:
- Any text after ~ (tilde)
- Any text in parentheses or brackets
- Any quality indicators (BluRay, x264, 1080p, etc.)
- Any release group names
- Any audio/video codec information
- Any language indicators
- Any subtitle information
- Any audio track information
- Any collection/label names (Criterion Collection, Arrow Video, Shout Factory, etc.)
- Any special characters like ~, |, \\, /, etc.

CRITICAL: Preserve movie sequel numbers, Roman numerals in titles, and YEARS (e.g., "Cars 2", "Toy Story 3", "Iron Man 2", "Inside Out 2", "Frozen 2", "Finding Dory", "Monsters University", "Rocky IV", "1999", "2010", "1968")

Focus ONLY on the core movie title. If you're unsure about a word, remove it.

Examples of what to remove:
- "Cars 2 ~Invincible" → "Cars 2"
- "Cars 2 (2011) 1080p BluRay x264" → "Cars 2 2011"
- "Toy Story 3 2010 720p WEBRIP" → "Toy Story 3 2010"
- "Inside Out 2 2024 1080p BluRay x264" → "Inside Out 2 2024"
- "Frozen 2 2019 720p WEBRIP" → "Frozen 2 2019"
- "Finding Dory 2016 BluRay x264" → "Finding Dory 2016"
- "Monsters University 2013 1080p" → "Monsters University 2013"
- "Certified Copy Criterion Collection 1080p BluRay x264" → "Certified Copy"
- "The Matrix (1999) [YIFY]" → "The Matrix 1999"
- "Inception 1080p BluRay x264" → "Inception"
- "Signs of Life 1968" → "Signs of Life 1968"

Provide ONLY the clean movie title:"""

                alternative_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a movie title cleaner. Remove ALL unwanted elements and provide ONLY the core movie title. Be aggressive in removing uncertain elements, but CRITICALLY preserve movie sequel numbers (like Cars 2, Toy Story 3, Iron Man 2), Roman numerals in titles, and YEARS (like 1999, 2010, 1968) which are crucial for finding the correct movie."},
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
    
    def generate_sms_response(self, message: str, sender: str, prompt_template: str) -> Dict[str, Any]:
        """Generate an SMS response using ChatGPT with a custom prompt."""
        if not self.client:
            return {"error": "OpenAI API key not configured", "success": False}
        
        try:
            # Replace placeholders in the prompt template
            formatted_prompt = prompt_template.replace('{message}', message)
            formatted_prompt = formatted_prompt.replace('{sender}', sender)

            logger.info(f"🤖 OpenAI SMS Request: Generating response for message '{message}' from '{sender}'")
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": formatted_prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"✅ OpenAI SMS Response: Generated response '{response_text}'")
            
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
