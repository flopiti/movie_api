#!/usr/bin/env python3
"""
Twilio SMS Client
Handles SMS messaging functionality for the movie management system.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import redis

logger = logging.getLogger(__name__)

class TwilioClient:
    def __init__(self):
        """Initialize Twilio client with configuration from environment variables."""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            logger.warning("Twilio credentials not fully configured. SMS functionality will be limited.")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
            logger.info("Twilio client initialized successfully")
        
        # Redis configuration for message storage
        self.redis_host = os.getenv('REDIS_HOST', '192.168.0.10')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis connection established for message storage")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None
    
    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """
        Send an SMS message.
        
        Args:
            to: Recipient phone number
            message: Message content
            
        Returns:
            Dict with success status and message details
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio client not configured'
            }
        
        try:
            message_obj = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=to
            )
            
            logger.info(f"SMS sent successfully to {to}: {message_obj.sid}")
            return {
                'success': True,
                'message_sid': message_obj.sid,
                'status': message_obj.status,
                'to': to,
                'from': self.phone_number,
                'body': message,
                'date_created': message_obj.date_created.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to send SMS to {to}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def store_received_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Store a received message in Redis.
        
        Args:
            message_data: Message data from Twilio webhook
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis not available for message storage")
            return False
        
        try:
            # Create a unique key for the message
            message_id = message_data.get('MessageSid', f"msg_{datetime.now().timestamp()}")
            message_key = f"sms_message:{message_id}"
            
            # Add timestamp if not present
            if 'timestamp' not in message_data:
                message_data['timestamp'] = datetime.now().isoformat()
            
            # Store the message
            self.redis_client.hset(message_key, mapping=message_data)
            
            # Add to a list of recent messages (keep last 100)
            self.redis_client.lpush("sms_messages:recent", message_id)
            self.redis_client.ltrim("sms_messages:recent", 0, 99)
            
            logger.info(f"Stored received message: {message_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store message: {str(e)}")
            return False
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve recent messages from storage.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        if not self.redis_client:
            logger.warning("Redis not available for message retrieval")
            return []
        
        try:
            # Get recent message IDs
            message_ids = self.redis_client.lrange("sms_messages:recent", 0, limit - 1)
            
            messages = []
            for message_id in message_ids:
                message_key = f"sms_message:{message_id}"
                message_data = self.redis_client.hgetall(message_key)
                if message_data:
                    messages.append(message_data)
            
            # Sort by timestamp (most recent first)
            messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            logger.info(f"Retrieved {len(messages)} recent messages")
            return messages
        except Exception as e:
            logger.error(f"Failed to retrieve messages: {str(e)}")
            return []
    
    def create_webhook_response(self, message: str = None) -> str:
        """
        Create a TwiML response for webhook.
        
        Args:
            message: Optional response message to send back
            
        Returns:
            TwiML response string
        """
        response = MessagingResponse()
        if message:
            response.message(message)
        return str(response)
    
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return self.client is not None and all([
            self.account_sid,
            self.auth_token,
            self.phone_number
        ])
