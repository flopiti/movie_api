#!/usr/bin/env python3
"""
Radarr Client Test Expectations
Contains test cases and expected results for Radarr client testing.
"""

# Movie Search Test Cases
RADARR_SEARCH_TEST_CASES = [
    {
        "name": "Simple movie title",
        "query": "The Matrix",
        "expected_results": {
            "success": True,
            "total_results": "> 0",
            "first_result": {
                "title": "The Matrix",
                "year": 1999,
                "tmdbId": 603
            }
        }
    },
    {
        "name": "Movie with year in query",
        "query": "Inception 2010",
        "expected_results": {
            "success": True,
            "total_results": "> 0",
            "first_result": {
                "title": "Inception",
                "year": 2010,
                "tmdbId": 27205
            }
        }
    },
    {
        "name": "Blade Runner ambiguous search",
        "query": "Blade Runner (2017)",
        "expected_results": {
            "success": True,
            "total_results": "> 0",
            "first_result": {
                "title": "Blade Runner 2049",
                "year": 2017,
                "tmdbId": 335984
            },
            "note": "Should find Blade Runner 2049 even with ambiguous 'Blade Runner (2017)' query"
        }
    },
    {
        "name": "Blade Runner exact search",
        "query": "Blade Runner 2049",
        "expected_results": {
            "success": True,
            "total_results": "> 0",
            "first_result": {
                "title": "Blade Runner 2049",
                "year": 2017,
                "tmdbId": 335984
            }
        }
    },
    {
        "name": "Blade Runner original",
        "query": "Blade Runner",
        "expected_results": {
            "success": True,
            "total_results": "> 0",
            "first_result": {
                "title": "Blade Runner",
                "year": 1982,
                "tmdbId": 78
            }
        }
    },
    {
        "name": "Movie with article",
        "query": "The Lord of the Rings",
        "expected_results": {
            "success": True,
            "total_results": "> 0",
            "first_result": {
                "title": "The Lord of the Rings: The Fellowship of the Ring",
                "year": 2001,
                "tmdbId": 120
            }
        }
    },
    {
        "name": "Non-existent movie",
        "query": "Some Obscure Movie That Doesn't Exist 2025",
        "expected_results": {
            "success": True,
            "total_results": 0
        }
    },
    {
        "name": "Ambiguous movie title",
        "query": "Batman",
        "expected_results": {
            "success": True,
            "total_results": "> 5",  # Should return multiple Batman movies
            "first_result": {
                "title": "Batman",
                "year": 1989,
                "tmdbId": 268
            }
        }
    }
]

# Movie Status Test Cases
RADARR_STATUS_TEST_CASES = [
    {
        "name": "Check Blade Runner 2049 status",
        "tmdb_id": 335984,
        "expected_results": {
            "success": True,
            "movie_found": True,
            "status": "any"  # Could be "downloaded", "available", "monitored", etc.
        }
    },
    {
        "name": "Check The Matrix status",
        "tmdb_id": 603,
        "expected_results": {
            "success": True,
            "movie_found": True,
            "status": "any"
        }
    },
    {
        "name": "Check non-existent movie status",
        "tmdb_id": 999999999,
        "expected_results": {
            "success": True,
            "movie_found": False,
            "status": None
        }
    }
]

# Test Configuration
TEST_CONFIG = {
    "timeout": 30,
    "retry_attempts": 2,
    "verbose_output": True,
    "save_results": False,
    "results_file": "radarr_test_results.json"
}

# Validation Rules
VALIDATION_RULES = {
    "movie_search": {
        "required_fields": ["success", "total_results"],
        "success_conditions": ["success == true"],
        "total_results_conditions": [
            "total_results >= 0"
        ]
    },
    "movie_status": {
        "required_fields": ["success", "movie_found"],
        "success_conditions": ["success == true"],
        "movie_found_conditions": [
            "movie_found is boolean"
        ]
    }
}
