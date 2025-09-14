#!/usr/bin/env python3
"""
OpenAI Client Test Expectations
Contains test cases and expected results for OpenAI client testing.
"""

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
        "expected_movie": "Blade Runner 2049 (2017)"
    },
    {
        "name": "Multiple movies mentioned",
        "conversation": [
            "USER: I want to watch either The Dark Knight or Inception"
        ],
        "expected_movie": "The Dark Knight (2008)"  # Should pick the first one
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
            "USER: add devils wears prada 2",
            "USER: yoo do you know about devil wears prada 2?"
        ],
        "expected_movie": "Breakfast at Tiffany's (1961)"  # Should prioritize first USER message
    }
]

# SMS Response Test Cases
SMS_RESPONSE_TEST_CASES = [
    {
        "name": "Movie request response",
        "message": "Can you get me The Matrix?",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'The Matrix (1999)' was identified and found in our database)",
        "expected_keywords": ["Matrix", "download", "found"]
    },
    {
        "name": "General greeting",
        "message": "Hello, how are you?",
        "sender": "+1234567890",
        "movie_context": " (Note: No movie was identified in the conversation)",
        "expected_keywords": ["help", "movie", "recommendations"]
    },
    {
        "name": "Movie not found",
        "message": "Can you get me Some Obscure Movie That Doesn't Exist?",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'Some Obscure Movie That Doesn't Exist' was identified but not found in our database)",
        "expected_keywords": ["couldn't find", "details", "another movie"]
    },
    {
        "name": "Thank you message",
        "message": "Thanks for the movie!",
        "sender": "+1234567890",
        "movie_context": " (Note: No movie was identified in the conversation)",
        "expected_keywords": ["welcome", "enjoy", "help"]
    },
    {
        "name": "Movie with year request",
        "message": "Can you get me the 2010 version of Inception?",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'Inception (2010)' was identified and found in our database)",
        "expected_keywords": ["Inception", "download", "found"]
    },
    {
        "name": "Titane request after Planet of the Apes discussion",
        "message": "Actually, can you get me Titane? I heard it's really good",
        "sender": "+1234567890",
        "movie_context": " (Note: A movie 'Titane (2021)' was identified and found in our database)",
        "expected_keywords": ["Titane", "download", "found"]
    },
    {
        "name": "Devil Wears Prada 2 request with detection failure",
        "message": "yoo do you know about devil wears prada 2?",
        "sender": "+14384109395",
        "movie_context": " (Note: A movie 'No movie identified.' was identified but not found in our database)",
        "expected_keywords": ["couldn't find", "Devil Wears Prada", "details", "another"]
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
        "expected_title": "Spider-Man Into the Spider-Verse 2018"
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

# Validation Rules
VALIDATION_RULES = {
    "movie_detection": {
        "required_fields": ["success", "movie_name", "conversation"],
        "success_conditions": ["success == true"],
        "movie_name_conditions": [
            "movie_name != 'No movie identified' OR expected_movie is None"
        ]
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
    }
}
