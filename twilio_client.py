#!/usr/bin/env python3
"""
Twilio SMS Client
Handles SMS messaging functionality for the movie management system.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import redis

class TwilioClient:
    def __init__(self):
        """Initialize Twilio client with configuration from environment variables."""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
        
        # Initialize Redis for message storage
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection for message storage."""
        try:
            # Use same Redis config as main app
            redis_host = os.getenv('REDIS_HOST', '172.17.0.1')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))
            
            self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
            self.redis_client.ping()  # Test connection
        except Exception as e:
            self.redis_client = None
    
    def _store_message_in_redis(self, message_data: Dict[str, Any]) -> None:
        """Store a message in Redis."""
        if not self.redis_client:
            return
        
        try:
            # Create a unique key for the message
            message_sid = message_data.get('message_sid', f"local_{datetime.now().timestamp()}")
            redis_key = f"sms_message:{message_sid}"
            
            # Store message data as JSON
            self.redis_client.set(redis_key, json.dumps(message_data))
            
            # Add to sorted set for chronological ordering (timestamp as score)
            timestamp = datetime.now().timestamp()
            self.redis_client.zadd("sms_messages", {message_sid: timestamp})
            
        except Exception as e:
            pass
    
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
            
            
            # Prepare message data for storage
            message_data = {
                'message_sid': message_obj.sid,
                'status': message_obj.status,
                'to': to,
                'from': self.phone_number,
                'body': message,
                'date_created': message_obj.date_created.isoformat(),
                'direction': 'outbound',
                'stored_at': datetime.now().isoformat()
            }
            
            # Store message in Redis
            self._store_message_in_redis(message_data)
            
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
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent SMS messages from Redis database.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        if not self.redis_client:
            return self._get_messages_from_twilio_api(limit)
        
        try:
            # Get message SIDs from Redis sorted set (most recent first)
            message_sids = self.redis_client.zrevrange("sms_messages", 0, limit - 1)
            
            message_list = []
            for message_sid in message_sids:
                redis_key = f"sms_message:{message_sid}"
                message_json = self.redis_client.get(redis_key)
                
                if message_json:
                    try:
                        message_data = json.loads(message_json)
                        # Convert to expected format for API compatibility
                        formatted_message = {
                            'MessageSid': message_data.get('message_sid'),
                            'From': message_data.get('from'),
                            'To': message_data.get('to'),
                            'Body': message_data.get('body'),
                            'Status': message_data.get('status'),
                            'DateCreated': message_data.get('date_created'),
                            'Direction': message_data.get('direction'),
                            'StoredAt': message_data.get('stored_at')
                        }
                        message_list.append(formatted_message)
                    except json.JSONDecodeError as e:
                        continue
            
            return message_list
            
        except Exception as e:
            # Fallback to Twilio API
            return self._get_messages_from_twilio_api(limit)
    
    def _get_messages_from_twilio_api(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fallback method to get messages from Twilio API.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        if not self.client:
            return []
        
        try:
            # Get messages from Twilio API
            messages = self.client.messages.list(limit=limit)
            
            message_list = []
            for message in messages:
                message_data = {
                    'MessageSid': message.sid,
                    'From': message.from_,
                    'To': message.to,
                    'Body': message.body,
                    'Status': message.status,
                    'DateCreated': message.date_created.isoformat() if message.date_created else None,
                    'Direction': message.direction
                }
                message_list.append(message_data)
            
            return message_list
            
        except Exception as e:
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
    
    def store_incoming_message(self, message_data: Dict[str, Any]) -> None:
        """
        Store an incoming message in Redis.
        
        Args:
            message_data: Dictionary containing message information from webhook
        """
        if not self.redis_client:
            return
        
        try:
            # Create a unique key for the message
            message_sid = message_data.get('MessageSid', f"incoming_{datetime.now().timestamp()}")
            redis_key = f"sms_message:{message_sid}"
            
            # Prepare message data for storage
            stored_message = {
                'message_sid': message_sid,
                'status': 'received',
                'to': message_data.get('To'),
                'from': message_data.get('From'),
                'body': message_data.get('Body'),
                'date_created': message_data.get('timestamp', datetime.now().isoformat()),
                'direction': 'inbound',
                'stored_at': datetime.now().isoformat(),
                'num_media': message_data.get('NumMedia', '0')
            }
            
            # Store message data as JSON
            self.redis_client.set(redis_key, json.dumps(stored_message))
            
            # Add to sorted set for chronological ordering (timestamp as score)
            timestamp = datetime.now().timestamp()
            self.redis_client.zadd("sms_messages", {message_sid: timestamp})
            
        except Exception as e:
            pass
    
    def get_webhook_url(self) -> Dict[str, Any]:
        """
        Get the current webhook URL for the Twilio phone number.
        
        Returns:
            Dict with webhook URL information
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio client not configured'
            }
        
        try:
            # Get the phone number resource
            incoming_phone_numbers = self.client.incoming_phone_numbers.list()
            
            for number in incoming_phone_numbers:
                if number.phone_number == self.phone_number:
                    return {
                        'success': True,
                        'phone_number': self.phone_number,
                        'webhook_url': number.sms_url,
                        'webhook_method': number.sms_method
                    }
            
            return {
                'success': False,
                'error': f'Phone number {self.phone_number} not found'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_webhook_url(self, webhook_url: str) -> Dict[str, Any]:
        """
        Update the webhook URL for the Twilio phone number.
        
        Args:
            webhook_url: New webhook URL
            
        Returns:
            Dict with success status
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio client not configured'
            }
        
        try:
            # Get the phone number resource
            incoming_phone_numbers = self.client.incoming_phone_numbers.list()
            
            for number in incoming_phone_numbers:
                if number.phone_number == self.phone_number:
                    # Update the webhook URL
                    number.update(sms_url=webhook_url, sms_method='POST')
                    
                    return {
                        'success': True,
                        'phone_number': self.phone_number,
                        'webhook_url': webhook_url
                    }
            
            return {
                'success': False,
                'error': f'Phone number {self.phone_number} not found'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_phone_number_settings(self) -> Dict[str, Any]:
        """
        Get all phone number settings from Twilio.
        
        Returns:
            Dict with phone number settings
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio client not configured'
            }
        
        try:
            # Get the phone number resource
            incoming_phone_numbers = self.client.incoming_phone_numbers.list()
            
            for number in incoming_phone_numbers:
                if number.phone_number == self.phone_number:
                    return {
                        'success': True,
                        'phone_number': self.phone_number,
                        'sms_url': number.sms_url,
                        'sms_method': number.sms_method,
                        'voice_url': number.voice_url,
                        'voice_method': number.voice_method,
                        'status_callback': number.status_callback,
                        'status_callback_method': number.status_callback_method
                    }
            
            return {
                'success': False,
                'error': f'Phone number {self.phone_number} not found'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def update_phone_number_settings(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """
        Update phone number settings in Twilio.
        
        Args:
            settings: Dict with settings to update (sms_url, voice_url, etc.)
            
        Returns:
            Dict with success status
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio client not configured'
            }
        
        try:
            # Get the phone number resource
            incoming_phone_numbers = self.client.incoming_phone_numbers.list()
            
            for number in incoming_phone_numbers:
                if number.phone_number == self.phone_number:
                    # Update the settings
                    number.update(**settings)
                    
                    return {
                        'success': True,
                        'phone_number': self.phone_number,
                        'updated_settings': settings
                    }
            
            return {
                'success': False,
                'error': f'Phone number {self.phone_number} not found'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def is_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return self.client is not None and all([
            self.account_sid,
            self.auth_token,
            self.phone_number
        ])
