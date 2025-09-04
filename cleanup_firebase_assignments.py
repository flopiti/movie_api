#!/usr/bin/env python3
"""
Firebase Movie Assignments Cleanup Script

This script analyzes the Firebase database for movie assignments and removes
entries for files that no longer exist, keeping only the ~900 assignments
that have real file connections.
"""

import os
import json
import logging
import base64
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

# Load environment variables
load_dotenv('env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('firebase_cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', '')
FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL', '')

def encode_path_for_firebase(path: str) -> str:
    """Encode file path to be safe for Firebase keys."""
    return base64.urlsafe_b64encode(path.encode('utf-8')).decode('ascii')

def decode_path_from_firebase(encoded_path: str) -> str:
    """Decode Firebase key back to file path."""
    return base64.urlsafe_b64decode(encoded_path.encode('ascii')).decode('utf-8')

class FirebaseCleanup:
    def __init__(self):
        self.firebase_app = None
        self.firebase_ref = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase connection."""
        if not FIREBASE_CREDENTIALS_PATH or not FIREBASE_DATABASE_URL:
            logger.error("Firebase credentials not configured!")
            return
        
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            self.firebase_app = firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DATABASE_URL
            })
            self.firebase_ref = db.reference('movie_config')
            logger.info("✅ Firebase initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {str(e)}")
            raise
    
    def get_all_assignments(self) -> Dict[str, Dict[str, Any]]:
        """Get all movie assignments from Firebase."""
        try:
            data = self.firebase_ref.get()
            if not data:
                logger.warning("No data found in Firebase")
                return {}
            
            encoded_assignments = data.get("movie_assignments", {})
            logger.info(f"📊 Found {len(encoded_assignments)} encoded assignments in Firebase")
            
            # Decode Firebase keys back to original file paths
            decoded_assignments = {}
            for encoded_path, movie_data in encoded_assignments.items():
                try:
                    # Try to decode - if it fails, assume it's already a plain path (backward compatibility)
                    original_path = movie_data.get('original_path') or decode_path_from_firebase(encoded_path)
                    decoded_assignments[original_path] = movie_data
                except Exception as decode_e:
                    logger.warning(f"Failed to decode path {encoded_path}, using as-is: {str(decode_e)}")
                    decoded_assignments[encoded_path] = movie_data
            
            logger.info(f"📚 Successfully decoded {len(decoded_assignments)} assignments")
            return decoded_assignments
            
        except Exception as e:
            logger.error(f"❌ Failed to get assignments from Firebase: {str(e)}")
            raise
    
    def analyze_assignments(self, assignments: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze assignments and categorize them."""
        valid_assignments = []
        orphaned_assignments = []
        total_count = len(assignments)
        
        logger.info(f"🔍 Analyzing {total_count} assignments...")
        
        for file_path, movie_data in assignments.items():
            movie_title = movie_data.get('title', 'Unknown')
            movie_id = movie_data.get('id', 'Unknown')
            
            if os.path.exists(file_path):
                valid_assignments.append({
                    'file_path': file_path,
                    'movie_title': movie_title,
                    'movie_id': movie_id
                })
                logger.debug(f"✅ Valid: {file_path} -> {movie_title}")
            else:
                orphaned_assignments.append({
                    'file_path': file_path,
                    'movie_title': movie_title,
                    'movie_id': movie_id
                })
                logger.debug(f"🚨 Orphaned: {file_path} -> {movie_title}")
        
        analysis = {
            'total_assignments': total_count,
            'valid_assignments': len(valid_assignments),
            'orphaned_assignments': len(orphaned_assignments),
            'valid_assignments_list': valid_assignments,
            'orphaned_assignments_list': orphaned_assignments
        }
        
        logger.info(f"📊 Analysis complete:")
        logger.info(f"   Total assignments: {total_count}")
        logger.info(f"   Valid assignments: {len(valid_assignments)}")
        logger.info(f"   Orphaned assignments: {len(orphaned_assignments)}")
        
        return analysis
    
    def remove_orphaned_assignments(self, orphaned_assignments: List[Dict[str, Any]]) -> int:
        """Remove orphaned assignments from Firebase."""
        removed_count = 0
        
        logger.info(f"🗑️ Starting removal of {len(orphaned_assignments)} orphaned assignments...")
        
        for assignment in orphaned_assignments:
            file_path = assignment['file_path']
            movie_title = assignment['movie_title']
            
            try:
                # Encode the file path for Firebase
                encoded_path = encode_path_for_firebase(file_path)
                
                # Get current data
                data = self.firebase_ref.get()
                assignments = data.get("movie_assignments", {})
                
                if encoded_path in assignments:
                    # Remove the assignment
                    del assignments[encoded_path]
                    
                    # Save back to Firebase
                    data["movie_assignments"] = assignments
                    self.firebase_ref.set(data)
                    
                    removed_count += 1
                    logger.info(f"✅ Removed: {file_path} -> {movie_title}")
                else:
                    logger.warning(f"⚠️ Assignment not found in Firebase: {file_path}")
                    
            except Exception as e:
                logger.error(f"❌ Error removing assignment {file_path}: {str(e)}")
        
        logger.info(f"🗑️ Removal complete: {removed_count} assignments removed")
        return removed_count
    
    def save_analysis_report(self, analysis: Dict[str, Any], filename: str = "firebase_analysis_report.json"):
        """Save analysis report to file."""
        try:
            with open(filename, 'w') as f:
                json.dump(analysis, f, indent=2)
            logger.info(f"📄 Analysis report saved to {filename}")
        except Exception as e:
            logger.error(f"❌ Failed to save analysis report: {str(e)}")
    
    def cleanup(self, dry_run: bool = True) -> Dict[str, Any]:
        """Main cleanup function."""
        logger.info("🚀 Starting Firebase cleanup process...")
        
        try:
            # Get all assignments
            assignments = self.get_all_assignments()
            
            # Analyze assignments
            analysis = self.analyze_assignments(assignments)
            
            # Save analysis report
            self.save_analysis_report(analysis)
            
            if dry_run:
                logger.info("🔍 DRY RUN MODE - No changes will be made to Firebase")
                return analysis
            
            # Remove orphaned assignments
            if analysis['orphaned_assignments'] > 0:
                removed_count = self.remove_orphaned_assignments(analysis['orphaned_assignments_list'])
                analysis['removed_count'] = removed_count
                logger.info(f"🎉 Cleanup completed! Removed {removed_count} orphaned assignments")
            else:
                logger.info("🎉 No orphaned assignments found - no cleanup needed")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {str(e)}")
            raise

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup Firebase movie assignments')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Analyze without making changes (default)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually remove orphaned assignments')
    
    args = parser.parse_args()
    
    if not args.execute:
        args.dry_run = True
    
    try:
        cleanup = FirebaseCleanup()
        result = cleanup.cleanup(dry_run=args.dry_run)
        
        print("\n" + "="*50)
        print("CLEANUP SUMMARY")
        print("="*50)
        print(f"Total assignments: {result['total_assignments']}")
        print(f"Valid assignments: {result['valid_assignments']}")
        print(f"Orphaned assignments: {result['orphaned_assignments']}")
        
        if not args.dry_run and 'removed_count' in result:
            print(f"Removed assignments: {result['removed_count']}")
        
        print("="*50)
        
    except Exception as e:
        logger.error(f"❌ Script failed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
