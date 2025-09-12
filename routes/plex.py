#!/usr/bin/env python3
"""
Plex Integration Routes
Routes for Plex API integration and movie comparison.
"""

import time
import os
from flask import Blueprint, request, jsonify
from plex_client import PlexClient
from config import config

# Create blueprint
plex_bp = Blueprint('plex', __name__)

# Initialize Plex client
plex_client = PlexClient()

@plex_bp.route('/plex/libraries', methods=['GET'])
def get_plex_libraries():
    """Get all Plex libraries."""
    try:
        libraries = plex_client.get_libraries()
        return jsonify({
            'libraries': libraries,
            'total_libraries': len(libraries),
            'movie_libraries': [lib for lib in libraries if lib['type'] == 'movie']
        }), 200
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get Plex libraries: {str(e)}'}), 500

@plex_bp.route('/plex/movie-count', methods=['GET'])
def get_plex_movie_count():
    """Get movie count from Plex by library."""
    try:
        counts = plex_client.get_movie_count()
        total_count = sum(counts.values())
        return jsonify({
            'counts_by_library': counts,
            'total_movies': total_count,
            'libraries_count': len(counts)
        }), 200
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get Plex movie count: {str(e)}'}), 500

@plex_bp.route('/plex/movies', methods=['GET'])
def get_plex_movies():
    """Get all movies from Plex."""
    try:
        movies = plex_client.get_all_movies()
        return jsonify({
            'movies': movies,
            'total_movies': len(movies)
        }), 200
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get Plex movies: {str(e)}'}), 500

@plex_bp.route('/plex/search', methods=['GET'])
def search_plex_movies():
    """Search movies in Plex."""
    try:
        query = request.args.get('q', '')
        library_id = request.args.get('library_id')
        
        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400
        
        movies = plex_client.search_movies(query, library_id)
        return jsonify({
            'movies': movies,
            'query': query,
            'library_id': library_id,
            'total_results': len(movies)
        }), 200
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to search Plex movies: {str(e)}'}), 500

@plex_bp.route('/compare-movies', methods=['GET'])
def compare_movies():
    """Compare Plex movies with assigned movies."""
    try:
        import time
        start_time = time.time()
        
        # Get Plex movie count first
        step_start = time.time()
        try:
            plex_counts = plex_client.get_movie_count()
            plex_total = sum(plex_counts.values())
        except Exception as e:
            pass
            return jsonify({'error': f'Failed to get Plex movie count: {str(e)}'}), 500
        step_time = time.time() - step_start

        # Get assigned movies from config
        step_start = time.time()
        assigned_movies = config.get_movie_assignments()
        step_time = time.time() - step_start

        # Process assigned movies
        step_start = time.time()
        assigned_titles = set()
        assigned_original_titles = set()
        assigned_files = []
        orphaned_assignments = []
        
        processed_count = 0
        for file_path, movie_data in assigned_movies.items():
            processed_count += 1
            if processed_count % 100 == 0:
                pass
            original_title = movie_data.get('title', '')
            title = original_title.lower().strip()
            
            if os.path.exists(file_path):  # Only include existing files
                if title:
                    assigned_titles.add(title)
                    assigned_original_titles.add(original_title)
                    assigned_files.append({
                        'title': original_title,
                        'file_path': file_path,
                        'year': movie_data.get('release_date', '').split('-')[0] if movie_data.get('release_date') else None
                    })
            else:
                # Track orphaned assignments
                orphaned_assignments.append({
                    'file_path': file_path,
                    'title': original_title
                })

        step_time = time.time() - step_start

        # Calculate difference
        step_start = time.time()
        difference = plex_total - len(assigned_files)
        step_time = time.time() - step_start

        # Get Plex movies for detailed comparison
        step_start = time.time()
        try:
            plex_movies = plex_client.get_all_movies()

            # Debug: Check for movies without titles
            movies_without_titles = [movie for movie in plex_movies if not movie.get('title')]
            if movies_without_titles:
                pass

            # Store original titles WITH YEAR for side-by-side comparison
            all_titles_with_year = []
            for movie in plex_movies:
                if movie.get('title'):
                    title = movie['title']
                    year = movie.get('year') or movie.get('release_date', '').split('-')[0] if movie.get('release_date') else ''
                    title_with_year = f"{title} ({year})" if year else title
                    all_titles_with_year.append(title_with_year)
                    # Debug: Show a few examples
                    if len(all_titles_with_year) <= 5:
                        pass

                    # Debug: Show the raw movie data for the first few movies
                    if len(all_titles_with_year) <= 3:
                        pass

            plex_original_titles = set(all_titles_with_year)
            # Store lowercase titles with year for matching
            plex_titles = {title.lower().strip() for title in all_titles_with_year}

            # Check for duplicates WITH YEAR
            if len(all_titles_with_year) != len(set(all_titles_with_year)):
                from collections import Counter
                title_counts = Counter(all_titles_with_year)
                duplicates = [title for title, count in title_counts.items() if count > 1]
            else:
                pass

            # Show the actual titles that are being used for comparison
            # Show sample titles to verify year format

        except Exception as e:
            pass
            plex_original_titles = set()
            plex_titles = set()
        step_time = time.time() - step_start

        # Normalize titles for better matching
        step_start = time.time()
        
        # Simple direct comparison - no fancy matching
        step_start = time.time()
        
        # Create a mapping of base titles to full titles with years for Plex
        plex_title_mapping = {}
        for title in plex_original_titles:
            # Extract base title and year
            base_title = title
            year = None
            if ' (' in title and title.endswith(')'):
                parts = title.rsplit(' (', 1)
                if len(parts) == 2 and parts[1].endswith(')') and parts[1][:-1].isdigit():
                    base_title = parts[0]
                    year = parts[1][:-1]  # Remove the closing parenthesis
            
            base_title_lower = base_title.lower().strip()
            if base_title_lower not in plex_title_mapping:
                plex_title_mapping[base_title_lower] = []
            plex_title_mapping[base_title_lower].append({
                'full_title': title,
                'base_title': base_title,
                'year': year
            })
        
        # Create a mapping for assigned titles (they don't have years)
        # Include both existing files and orphaned assignments
        assigned_title_mapping = {}
        
        # Add titles from existing files
        for title in assigned_original_titles:
            base_title_lower = title.lower().strip()
            if base_title_lower not in assigned_title_mapping:
                assigned_title_mapping[base_title_lower] = []
            assigned_title_mapping[base_title_lower].append({
                'full_title': title,
                'base_title': title,
                'year': None,
                'status': 'existing'
            })
        
        # Add titles from orphaned assignments
        for orphaned in orphaned_assignments:
            title = orphaned['title']
            base_title_lower = title.lower().strip()
            if base_title_lower not in assigned_title_mapping:
                assigned_title_mapping[base_title_lower] = []
            assigned_title_mapping[base_title_lower].append({
                'full_title': title,
                'base_title': title,
                'year': None,
                'status': 'orphaned'
            })
        
        # Find matches and differences with year awareness
        in_both_original = set()
        only_in_plex_original = set()
        only_in_assigned_original = set()
        
        # Get all unique base titles
        all_base_titles = set(plex_title_mapping.keys()) | set(assigned_title_mapping.keys())
        
        for base_title in all_base_titles:
            plex_versions = plex_title_mapping.get(base_title, [])
            assigned_versions = assigned_title_mapping.get(base_title, [])
            
            if plex_versions and assigned_versions:
                # We have matches - add all plex versions to "in both"
                for plex_version in plex_versions:
                    in_both_original.add(plex_version['full_title'])
                # Add only existing assigned versions to "in both"
                for assigned_version in assigned_versions:
                    if assigned_version['status'] == 'existing':
                        in_both_original.add(assigned_version['full_title'])
                    else:  # orphaned
                        only_in_assigned_original.add(assigned_version['full_title'])
            elif plex_versions:
                # Only in Plex
                for plex_version in plex_versions:
                    only_in_plex_original.add(plex_version['full_title'])
            else:
                # Only in assigned
                for assigned_version in assigned_versions:
                    only_in_assigned_original.add(assigned_version['full_title'])
        
        # Debug: Show some examples of the matching
        sample_titles = list(all_base_titles)[:5]
        for base_title in sample_titles:
            plex_versions = plex_title_mapping.get(base_title, [])
            assigned_versions = assigned_title_mapping.get(base_title, [])

        # Verify the math
        step_time = time.time() - step_start
        step_time = time.time() - step_start

        # Prepare response
        step_start = time.time()
        
        # Create sorted lists for side-by-side comparison
        # Return ONLY the differences, not all movies
        only_in_plex_list = sorted(list(only_in_plex_original))
        only_in_assigned_list = sorted(list(only_in_assigned_original))
        
        # FIX THE FUCKING MATH - Use the actual Plex count from API
        actual_plex_count = plex_total  # Use the real Plex count from API
        actual_assigned_count = len(assigned_movies)  # Count ALL assignments, not just existing files
        actual_in_both = len(in_both_original)
        actual_only_plex = len(only_in_plex_original)
        actual_only_assigned = len(only_in_assigned_original)
        
        # Debug the discrepancy
        if len(plex_original_titles) != plex_total:
            # Find the missing movies
            all_plex_titles = {movie['title'] for movie in plex_movies if movie.get('title')}
            missing_titles = all_plex_titles - plex_original_titles

        response_data = {
            'summary': {
                'plex_total': actual_plex_count,
                'assigned_total': actual_assigned_count,
                'total_assignments': len(assigned_movies),
                'orphaned_assignments': len(orphaned_assignments),
                'only_in_plex': actual_only_plex,
                'only_in_assigned': actual_only_assigned,
                'in_both': actual_in_both
            },
            'only_in_plex': sorted(list(only_in_plex_original)),
            'only_in_assigned': sorted(list(only_in_assigned_original)),
            'plex_movies': sorted(list(in_both_original)),  # Movies that are in both Plex and assigned
            'assigned_movies': sorted(list(in_both_original)),  # Movies that are in both Plex and assigned
            'side_by_side_count': actual_only_plex + actual_only_assigned,
            'orphaned_assignments': orphaned_assignments,
            'note': f'Plex has {actual_plex_count} unique movies, you have {actual_assigned_count} assigned movies. {actual_in_both} movies in both, {actual_only_plex} only in Plex, {actual_only_assigned} only in assigned. {len(orphaned_assignments)} orphaned assignments found.'
        }
        step_time = time.time() - step_start

        total_time = time.time() - start_time

        return jsonify(response_data), 200
        
    except Exception as e:
        pass
        import traceback
        return jsonify({'error': f'Failed to compare movies: {str(e)}'}), 500
