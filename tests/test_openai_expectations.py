#!/usr/bin/env python3
"""
OpenAI Client Test Expectations
Contains test cases and expected results for OpenAI client testing.
"""

import re
import sys
import os

# Add the src directory to the path so we can import from it
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from clients.PROMPTS import AGENTIC_MOVIE_AGENT_PROMPT

def normalize_movie_title(title):
    """
    Normalize movie title for flexible comparison.
    Handles case-insensitive matching and minor formatting differences.
    """
    if not title:
        return ""
    
    # Convert to lowercase
    normalized = title.lower()
    
    # Remove extra spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove common punctuation differences
    normalized = normalized.replace("'", "").replace("'", "")
    
    return normalized

# Movie Detection Test Cases
MOVIE_DETECTION_TEST_CASES = [
    {
        "name": "Simple movie request",
        "conversation": [
            "USER: Can you get me The Matrix?"
        ],
        "expected_movie": "The Matrix (1999)"
    },
    {
        "name": "Movie with year",
        "conversation": [
            "USER: I want to watch Inception from 2010"
        ],
        "expected_movie": "Inception (2010)"
    },
    {
        "name": "Multiple messages conversation",
        "conversation": [
            "USER: Hi",
            "SYSTEM: Hello! How can I help you?",
            "USER: Can you download Avatar for me?"
        ],
        "expected_movie": "Avatar (2009)"
    },
    {
        "name": "No movie mentioned",
        "conversation": [
            "USER: How are you doing today?",
            "SYSTEM: I'm doing well, thanks for asking!"
        ],
        "expected_movie": None
    },
    # {
    #     "name": "Ambiguous movie reference",
    #     "conversation": [
    #         "USER: I want to see that new superhero movie",
    #         "SYSTEM: Which superhero movie are you referring to?",
    #         "USER: The one with Spider-Man"
    #     ],
    #     "expected_movie": "Spider-Man (2002)"
    # },
    {
        "name": "Movie with specific year mentioned",
        "conversation": [
            "USER: Can you get me the 2017 version of Blade Runner?"
        ],
        "expected_movie": "Blade Runner (2017)"
    },
    {
        "name": "Movie with article",
        "conversation": [
            "USER: Can you download The Lord of the Rings?"
        ],
        "expected_movie": "The Lord of the Rings (2001)"
    },
    {
        "name": "Planet of the Apes conversation ending with Titane request",
        "conversation": [
            "USER: Actually, can you get me Titane? I heard it's really good",
            "SYSTEM: That sounds interesting! Tell me more.",
            "USER: The CGI and motion capture in those newer ones was incredible",
            "SYSTEM: That sounds interesting! Tell me more.",
            "USER: I also really liked the reboot trilogy with Andy Serkis",
            "SYSTEM: That sounds interesting! Tell me more.",
            "USER: The original 1968 version with Charlton Heston was amazing",
            "SYSTEM: That sounds interesting! Tell me more.",
            "USER: Hey! I was thinking about Planet of the Apes movies today"
        ],
        "expected_movie": "Titane (2021)"
    },
    {
        "name": "Devil Wears Prada 2 request",
        "conversation": [
            "USER: yoo do you know about devil wears prada 2?"
        ],
        "expected_movie": "The Devil Wears Prada 2"  # Should detect sequel reference
    },
    {
        "name": "Breakfast at Tiffany's priority over Devil Wears Prada 2",
        "conversation": [
            "USER: can you add breakfast at tiffany?",
            "SYSTEM: Sure, I'll add Devil Wears Prada 2",
            "USER: add devils wears prada 2",
        ],
        "expected_movie": "Breakfast At Tiffany's (1961)"  # Should prioritize first USER message
    },
    {
        "name": "Casual greeting conversation",
        "conversation": [
            "USER: yoo"
        ],
        "expected_movie": None  # Should detect as casual greeting, no movie
    },
    {
        "name": "Conversational movie reference",
        "conversation": [
            "USER: do you know about blackhat"
        ],
        "expected_movie": "Blackhat (2015)"  # Should detect conversational movie reference
    },
    {
        "name": "Blackhat detection failure - current bug",
        "conversation": [
            "USER: do you know about Blackhat",
            "SYSTEM: Yo! How's it going? Need help with a movie or just want to chat?",
            "USER: yo"
        ],
        "expected_movie": "Blackhat (2015)",  # Currently failing - should detect but returns "No movie identified"
        "currently_failing": True
    },
    {
        "name": "Black or White movie request - full conversation",
        "conversation": [
            "USER: and do you know black or white",
            "SYSTEM: 🎬 Great! I'm getting Blackhat (2015) ready for you. I'll text you when I have updates",
            "USER: do you know about blackhat?",
            "SYSTEM: Hey! What's up? Need help with a movie or just chilling?",
            "USER: yo"
        ],
        "expected_movie": "Black or White (2014)"  # Should detect movie title with "or" in it from first message
    },
    {
        "name": "Snow White request with casual follow-up",
        "conversation": [
            "USER: Can you the new snow white?",
            "SYSTEM: Yo! How's it going? Anything on your mind today?",
            "USER: yo"
        ],
        "expected_movie": "Snow White"  # Should detect Snow White from first message (newest first)
    }
]

# SMS Response Test Cases
SMS_RESPONSE_TEST_CASES = [
    {
        "name": "Movie request response",
        "message": "Can you get me The Matrix?",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'The Matrix (1999)' was identified and found in our database)",
        "expected_keywords": ["Matrix", "getting", "ready"]
    },
    {
        "name": "General greeting",
        "message": "Hello, how are you?",
        "sender": "+1234567890",
        "movie_context": " (Note: No movie was identified in the conversation)",
        "expected_keywords": ["help", "movie"]
    },
    {
        "name": "Movie not found",
        "message": "Can you get me Some Obscure Movie That Doesn't Exist?",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'Some Obscure Movie That Doesn't Exist' was identified but not found in our database)",
        "expected_keywords": ["couldn't find", "let you know"]
    },
    {
        "name": "Thank you message",
        "message": "Thanks for the movie!",
        "sender": "+1234567890",
        "movie_context": " (Note: No movie was identified in the conversation)",
        "expected_keywords": ["welcome", "let me know"]
    },
    {
        "name": "Movie with year request",
        "message": "Can you get me the 2010 version of Inception?",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'Inception (2010)' was identified and found in our database)",
        "expected_keywords": ["Inception", "getting", "ready"]
    },
    {
        "name": "Titane request after Planet of the Apes discussion",
        "message": "Actually, can you get me Titane? I heard it's really good",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'Titane (2021)' was identified and found in our database)",
        "expected_keywords": ["Titane", "getting", "ready"]
    },
    {
        "name": "Devil Wears Prada 2 request with detection failure",
        "message": "yoo do you know about devil wears prada 2?",
        "sender": "+14384109395",
        "movie_context": " (Note: A movie 'No movie identified.' was identified but not found in our database)",
        "expected_keywords": ["haven't found", "Devil Wears Prada", "let you know"]
    }
]

# Filename Cleaning Test Cases
FILENAME_CLEANING_TEST_CASES = [
    {
        "filename": "The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv",
        "expected_title": "The Matrix 1999"
    },
    {
        "filename": "Inception.2010.720p.HDTV.x264-SOME-GROUP.avi",
        "expected_title": "Inception 2010"
    },
    {
        "filename": "Avatar.2009.1080p.BluRay.DTS.x264-GROUP.mkv",
        "expected_title": "Avatar 2009"
    },
    {
        "filename": "Some.Movie.With.Lots.Of.Periods.And.Numbers.2023.1080p.mkv",
        "expected_title": "Some Movie With Lots Of Periods And Numbers 2023"
    },
    {
        "filename": "The.Lord.of.the.Rings.The.Fellowship.of.the.Ring.2001.1080p.BluRay.x264-GROUP.mkv",
        "expected_title": "The Lord of the Rings The Fellowship of the Ring 2001"
    },
    {
        "filename": "Spider-Man.Into.the.Spider-Verse.2018.1080p.BluRay.x264-GROUP.mkv",
        "expected_title": "Spider-Man: Into the Spider-Verse 2018"
    },
    {
        "filename": "Blade.Runner.2049.2017.1080p.BluRay.x264-GROUP.mkv",
        "expected_title": "Blade Runner 2049 2017"
    }
]

# Expected Response Patterns
EXPECTED_RESPONSE_PATTERNS = {
    "movie_found": {
        "keywords": ["found", "download", "enjoy", "watching"],
        "tone": "positive",
        "should_include": ["movie title", "action confirmation"]
    },
    "movie_not_found": {
        "keywords": ["couldn't find", "not found", "details", "another"],
        "tone": "helpful",
        "should_include": ["apology", "suggestion"]
    },
    "no_movie": {
        "keywords": ["help", "movie", "recommendations", "questions"],
        "tone": "friendly",
        "should_include": ["assistance offer"]
    },
    "greeting": {
        "keywords": ["hello", "help", "movie", "recommendations"],
        "tone": "friendly",
        "should_include": ["assistance offer"]
    }
}

# Test Configuration
TEST_CONFIG = {
    "timeout": 30,
    "retry_attempts": 2,
    "verbose_output": True,
    "save_results": False,
    "results_file": "test_results.json"
}

# Agentic Response Test Cases
AGENTIC_RESPONSE_TEST_CASES = [

        {
            "name": "Casual greeting 'hey there' - should respond conversationally",
            "prompt": AGENTIC_MOVIE_AGENT_PROMPT + 
            "\n\nHere is the conversation history:\n['USER: hey there']\n\nFUNCTION RESULTS: []\n",
            "expected_success": True,
            "expected_has_function_calls": True,
            "expected_function_name": "identify_movie_request"
        }
        ,
        {
            "name": "Casual greeting 'hey there' - already identified No movie, should call send_notification",
            "prompt": AGENTIC_MOVIE_AGENT_PROMPT + 
            (
                "\n\nHere is the conversation history:\n['USER: hey there']\n\n"
                "FUNCTION RESULTS: ["
                "{'function_name': 'identify_movie_request', 'result': {'success': False, 'movie_name': 'No movie identified', 'confidence': 'none'}}, "
                "]\n"
            ),
            "expected_success": True,
            "expected_has_function_calls": True,
            "expected_function_name": "send_notification",
        }
        ]

# Validation Rules
VALIDATION_RULES = {
    "movie_detection": {
        "required_fields": ["success", "movie_name", "conversation"],
        "success_conditions": ["success == true"],
        "movie_name_conditions": [
            "movie_name != 'No movie identified' OR expected_movie is None"
        ],
        "flexible_matching": True,  # Enable case-insensitive and flexible matching
        "normalize_function": "normalize_movie_title"  # Function to normalize movie titles for comparison
    },
    "sms_response": {
        "required_fields": ["success", "response", "original_message", "sender"],
        "success_conditions": ["success == true"],
        "response_conditions": [
            "len(response) > 10",
            "response is not None"
        ]
    },
    "filename_cleaning": {
        "required_fields": ["success", "cleaned_title", "original_filename"],
        "success_conditions": ["success == true"],
        "cleaned_title_conditions": [
            "len(cleaned_title) > 0",
            "cleaned_title != original_filename"
        ]
    },
    "agentic_response": {
        "required_fields": ["success", "response", "has_function_calls"],
        "success_conditions": ["success == true"],
        "response_conditions": [
            "len(response) > 0",
            "response is not None"
        ],
        "function_call_conditions": [
            "has_function_calls matches expected_has_function_calls",
            "if has_function_calls: tool_calls is not None",
            "if has_function_calls: function_name matches expected_function_name"
        ]
    }
}
