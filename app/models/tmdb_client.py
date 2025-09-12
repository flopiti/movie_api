#!/usr/bin/env python3
"""
TMDB API client for movie metadata.
"""

import re
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TMDBClient:
    """TMDB API client for movie metadata."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.themoviedb.org/3"):
        self.api_key = api_key
        self.base_url = base_url
    
    def search_movie(self, query: str) -> Dict[str, Any]:
        """Search for a movie by title with aggressive year-aware filtering."""
        if not self.api_key:
            logger.error("TMDB API key not configured")
            return {"error": "TMDB API key not configured"}
        
        # Extract year from query if present
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        target_year = year_match.group(0) if year_match else None
        
        # Clean query by removing the year for base search
        base_query = re.sub(r'\b(19|20)\d{2}\b', '', query).strip()
        
        logger.info(f"Searching for: '{base_query}' with target year: {target_year}")
        
        all_results = []
        
        # Strategy 1: Search with year parameter if we have a target year
        if target_year:
            url = f"{self.base_url}/search/movie"
            year_params = {
                'api_key': self.api_key,
                'query': base_query,
                'year': target_year,
                'language': 'en-US',
                'include_adult': False
            }
            
            try:
                logger.info(f"Strategy 1: Searching with year parameter: '{base_query}' year={target_year}")
                response = requests.get(url, params=year_params)
                response.raise_for_status()
                year_result = response.json()
                
                if year_result.get('results'):
                    # These results are guaranteed to be from the target year
                    for movie in year_result['results']:
                        movie['_search_strategy'] = 'year_parameter'
                        movie['_year_match'] = True
                    all_results.extend(year_result['results'])
                    logger.info(f"Year parameter search found {len(year_result['results'])} results")
            except requests.RequestException as e:
                logger.warning(f"Year parameter search failed: {str(e)}")
        
        # Strategy 2: Search with full query (including year in text)
        url = f"{self.base_url}/search/movie"
        full_params = {
            'api_key': self.api_key,
            'query': query,
            'language': 'en-US',
            'include_adult': False
        }
        
        try:
            logger.info(f"Strategy 2: Searching with full query: '{query}'")
            response = requests.get(url, params=full_params)
            response.raise_for_status()
            full_result = response.json()
            
            if full_result.get('results'):
                for movie in full_result['results']:
                    movie['_search_strategy'] = 'full_query'
                    # Check if this movie matches our target year
                    movie_year = None
                    if movie.get('release_date'):
                        try:
                            movie_year = movie['release_date'].split('-')[0]
                        except (IndexError, ValueError):
                            pass
                    movie['_year_match'] = (movie_year == target_year) if target_year else False
                
                # Only add movies we haven't already found
                existing_ids = {m['id'] for m in all_results}
                new_movies = [m for m in full_result['results'] if m['id'] not in existing_ids]
                all_results.extend(new_movies)
                logger.info(f"Full query search found {len(new_movies)} additional results")
        except requests.RequestException as e:
            logger.error(f"Full query search failed: {str(e)}")
            return {"error": f"TMDB API error: {str(e)}"}
        
        # Strategy 3: If we still don't have enough year matches, try base query only
        if target_year and len([m for m in all_results if m.get('_year_match')]) < 3:
            base_params = {
                'api_key': self.api_key,
                'query': base_query,
                'language': 'en-US',
                'include_adult': False
            }
            
            try:
                logger.info(f"Strategy 3: Fallback search with base query: '{base_query}'")
                response = requests.get(url, params=base_params)
                response.raise_for_status()
                base_result = response.json()
                
                if base_result.get('results'):
                    for movie in base_result['results']:
                        movie['_search_strategy'] = 'base_query'
                        # Check if this movie matches our target year
                        movie_year = None
                        if movie.get('release_date'):
                            try:
                                movie_year = movie['release_date'].split('-')[0]
                            except (IndexError, ValueError):
                                pass
                        movie['_year_match'] = (movie_year == target_year) if target_year else False
                    
                    # Only add movies we haven't already found
                    existing_ids = {m['id'] for m in all_results}
                    new_movies = [m for m in base_result['results'] if m['id'] not in existing_ids]
                    all_results.extend(new_movies)
                    logger.info(f"Base query search found {len(new_movies)} additional results")
            except requests.RequestException as e:
                logger.warning(f"Base query search failed: {str(e)}")
        
        # Sort results: year matches first, then by strategy priority
        if target_year:
            year_matches = [m for m in all_results if m.get('_year_match')]
            other_movies = [m for m in all_results if not m.get('_year_match')]
            
            # Sort year matches by strategy priority
            strategy_priority = {'year_parameter': 1, 'full_query': 2, 'base_query': 3}
            year_matches.sort(key=lambda x: strategy_priority.get(x.get('_search_strategy', 'base_query'), 4))
            
            # Sort other movies by strategy priority
            other_movies.sort(key=lambda x: strategy_priority.get(x.get('_search_strategy', 'base_query'), 4))
            
            final_results = year_matches + other_movies
            logger.info(f"Final results: {len(year_matches)} year matches, {len(other_movies)} other movies")
            if year_matches:
                logger.info(f"Top year match: '{year_matches[0].get('title')}' ({year_matches[0].get('release_date')})")
        else:
            final_results = all_results
        
        # Clean up internal fields
        for movie in final_results:
            movie.pop('_search_strategy', None)
            movie.pop('_year_match', None)
        
        return {
            'results': final_results,
            'total_results': len(final_results),
            'year_matches': len([m for m in all_results if m.get('_year_match')]) if target_year else 0
        }
