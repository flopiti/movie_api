#!/usr/bin/env python3
"""
Script to compare movie counts between the local app and Plex server
"""

import requests
import json
from plex_client import PlexClient

def get_local_movie_count():
    """Get movie count from local API"""
    try:
        response = requests.get('http://192.168.0.10:5000/all-files')
        if response.status_code == 200:
            data = response.json()
            return len(data.get('files', []))
        else:
            print(f"Error getting local files: {response.status_code}")
            return 0
    except Exception as e:
        print(f"Error connecting to local API: {e}")
        return 0

def get_plex_movie_count():
    """Get movie count from Plex"""
    try:
        plex = PlexClient()
        counts = plex.get_movie_count()
        total = sum(counts.values())
        return total, counts
    except Exception as e:
        print(f"Error getting Plex count: {e}")
        return 0, {}

def main():
    print("Comparing movie counts between local app and Plex server")
    print("=" * 60)
    
    # Get local count
    print("Getting local movie count...")
    local_count = get_local_movie_count()
    print(f"Local app movie count: {local_count}")
    
    # Get Plex count
    print("\nGetting Plex movie count...")
    plex_total, plex_counts = get_plex_movie_count()
    print(f"Plex total movie count: {plex_total}")
    
    if plex_counts:
        print("\nPlex counts by library:")
        for library, count in plex_counts.items():
            print(f"  {library}: {count} movies")
    
    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON:")
    print(f"Local app: {local_count} movies")
    print(f"Plex server: {plex_total} movies")
    
    if local_count > plex_total:
        diff = local_count - plex_total
        print(f"Local app has {diff} more movies than Plex")
    elif plex_total > local_count:
        diff = plex_total - local_count
        print(f"Plex has {diff} more movies than local app")
    else:
        print("Counts match!")
    
    # Save detailed comparison
    comparison = {
        'local_count': local_count,
        'plex_total': plex_total,
        'plex_by_library': plex_counts,
        'difference': abs(local_count - plex_total),
        'local_has_more': local_count > plex_total
    }
    
    with open('movie_count_comparison.json', 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"\nDetailed comparison saved to movie_count_comparison.json")

if __name__ == "__main__":
    main()
