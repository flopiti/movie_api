#!/usr/bin/env python3
"""
TMDB API client for movie metadata.
"""

import requests
from typing import Dict, Any

class TMDBClient:
    """TMDB API client for movie metadata."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
    
    def search_movie(self, query: str) -> Dict[str, Any]:
        """Search for a movie by title with aggressive year-aware filtering."""
        if not self.api_key:
            return {"error": "TMDB API key not configured"}
        
        # Extract year from query if present
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        target_year = year_match.group(0) if year_match else None
        
        # Clean query by removing the year for base search
        base_query = re.sub(r'\b(19|20)\d{2}\b', '', query).strip()

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
                response = requests.get(url, params=year_params)
                response.raise_for_status()
                year_result = response.json()
                
                if year_result.get('results'):
                    # These results are guaranteed to be from the target year
                    for movie in year_result['results']:
                        movie['_search_strategy'] = 'year_parameter'
                        movie['_year_match'] = True
                    all_results.extend(year_result['results'])

            except requests.RequestException as e:
                pass

        # Strategy 2: Search with full query (including year in text)
        url = f"{self.base_url}/search/movie"
        full_params = {
            'api_key': self.api_key,
            'query': query,
            'language': 'en-US',
            'include_adult': False
        }
        
        try:
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

        except requests.RequestException as e:
            pass
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

            except requests.RequestException as e:
                pass
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

            if year_matches:
                pass
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
