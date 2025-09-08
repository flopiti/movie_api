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
        
        # No Redis needed - we'll query Twilio API directly
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
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent SMS messages directly from Twilio API.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        if not self.client:
            logger.warning("Twilio client not configured")
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
            
            logger.info(f"Retrieved {len(message_list)} messages from Twilio API")
            return message_list
            
        except Exception as e:
            logger.error(f"Failed to retrieve messages from Twilio: {str(e)}")
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
            logger.error(f"Failed to get webhook URL: {str(e)}")
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
                    
                    logger.info(f"Updated webhook URL for {self.phone_number} to {webhook_url}")
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
            logger.error(f"Failed to update webhook URL: {str(e)}")
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
