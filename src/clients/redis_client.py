#!/usr/bin/env python3
"""
Redis Client
Handles Redis operations for the movie management system.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import redis

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis client for storing and retrieving application data."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one Redis connection."""
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._init_redis()
        return cls._instance
    
    def __init__(self):
        """Initialize Redis client with configuration from environment variables."""
        # Only initialize if not already done
        if self._client is None:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            redis_host = os.getenv('REDIS_HOST', '172.17.0.1')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))
            
            self._client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
            self._client.ping()  # Test connection
            logger.info("✅ Redis Client: Connection established")
        except Exception as e:
            self._client = None
            logger.error(f"❌ Redis Client: Connection failed: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._client is not None
    
    @property
    def client(self):
        """Get the Redis client instance."""
        return self._client
    
    def set(self, key: str, value: str) -> bool:
        """Set a key-value pair in Redis."""
        if not self.client:
            return False
        
        try:
            self.client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to set key '{key}': {str(e)}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get a value by key from Redis."""
        if not self.client:
            return None
        
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to get key '{key}': {str(e)}")
            return None
    
    def zadd(self, key: str, mapping: Dict[str, float]) -> bool:
        """Add members to a sorted set."""
        if not self.client:
            return False
        
        try:
            self.client.zadd(key, mapping)
            return True
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to zadd to '{key}': {str(e)}")
            return False
    
    def zrange(self, key: str, start: int, end: int) -> List[str]:
        """Get members from a sorted set in order."""
        if not self.client:
            return []
        
        try:
            return self.client.zrange(key, start, end)
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to zrange '{key}': {str(e)}")
            return []
    
    def zrevrange(self, key: str, start: int, end: int) -> List[str]:
        """Get members from a sorted set in reverse order (newest first)."""
        if not self.client:
            return []
        
        try:
            return self.client.zrevrange(key, start, end)
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to zrevrange '{key}': {str(e)}")
            return []
    
    def keys(self, pattern: str) -> List[str]:
        """Get keys matching a pattern."""
        if not self.client:
            return []
        
        try:
            return self.client.keys(pattern)
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to get keys with pattern '{pattern}': {str(e)}")
            return []
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        if not self.client:
            return 0
        
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to delete keys {keys}: {str(e)}")
            return 0
    
    def store_sms_message(self, message_data: Dict[str, Any]) -> bool:
        """Store an SMS message in Redis."""
        if not self.client:
            return False
        
        try:
            # Create a unique key for the message
            message_sid = message_data.get('MessageSid', f"message_{datetime.now().timestamp()}")
            redis_key = f"sms_message:{message_sid}"
            
            # Prepare message data for storage
            stored_message = {
                'message_sid': message_sid,
                'status': message_data.get('status', 'received'),
                'to': message_data.get('To'),
                'from': message_data.get('From'),
                'body': message_data.get('Body'),
                'date_created': message_data.get('timestamp', datetime.now().isoformat()),
                'direction': message_data.get('direction', 'inbound'),
                'stored_at': datetime.now().isoformat(),
                'num_media': message_data.get('NumMedia', '0')
            }
            
            # Store message data as JSON
            self.client.set(redis_key, json.dumps(stored_message))
            
            # Add to sorted set for chronological ordering (timestamp as score)
            timestamp = message_data.get('timestamp', datetime.now().timestamp())
            if isinstance(timestamp, str):
                # Convert ISO format to timestamp if needed
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
            self.client.zadd("sms_messages", {message_sid: timestamp})
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to store SMS message: {str(e)}")
            return False
    
    def delete_conversation(self, phone_number: str) -> bool:
        """Delete all messages for a specific phone number conversation."""
        if not self.client:
            return False
        
        try:
            # Get all message SIDs from Redis sorted set
            message_sids = self.client.zrevrange("sms_messages", 0, -1)
            deleted_count = 0
            
            for message_sid in message_sids:
                redis_key = f"sms_message:{message_sid}"
                message_json = self.client.get(redis_key)
                
                if message_json:
                    try:
                        message_data = json.loads(message_json)
                        
                        # Check if this message belongs to the conversation
                        if (message_data.get('from') == phone_number or 
                            message_data.get('to') == phone_number):
                            
                            # Delete the message data
                            self.client.delete(redis_key)
                            
                            # Remove from sorted set
                            self.client.zrem("sms_messages", message_sid)
                            
                            deleted_count += 1
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Redis Client: Failed to parse message JSON for deletion: {str(e)}")
                        continue
            
            logger.info(f"✅ Redis Client: Deleted {deleted_count} messages for conversation {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis Client: Failed to delete conversation: {str(e)}")
            return False
    
