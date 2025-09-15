#!/usr/bin/env python3
"""
Movie Identification Service
Handles movie detection and identification from SMS conversations.
"""

import logging
from ..clients.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class MovieIdentificationService:
    """Service for identifying movies from SMS conversations"""
    
    def __init__(self, openai_client: OpenAIClient):
        self.openai_client = openai_client
    
    def identify_movie_request(self, conversation_history):

        print("conversation_history line 20")
        print(conversation_history)
        """
        Agentic function: Extract movie title and year from SMS conversation
        Returns movie name with year or "No movie identified"
        """
        try:
            # Send last 10 messages (both USER and SYSTEM) for context
            last_10_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            
            movie_result = self.openai_client.getMovieName(last_10_messages)
            
            if movie_result and movie_result.get('success') and movie_result.get('movie_name'):
                logger.info(f"🎬 MovieIdentification: Movie identified: {movie_result['movie_name']}")
                return {
                    'success': True,
                    'movie_name': movie_result['movie_name'],
                    'confidence': movie_result.get('confidence', 'medium')
                }
            else:
                logger.info(f"🎬 MovieIdentification: No movie identified in conversation")
                return {
                    'success': False,
                    'movie_name': "No movie identified",
                    'confidence': 'none'
                }
                
        except Exception as e:
            logger.error(f"❌ MovieIdentification: Error identifying movie request: {str(e)}")
            return {
                'success': False,
                'movie_name': "No movie identified",
                'confidence': 'none',
                'error': str(e)
            }
