#!/usr/bin/env python3
"""
SMS Conversations Service
Handles SMS conversation history and message retrieval operations.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from ..clients.redis_client import RedisClient

logger = logging.getLogger(__name__)

class SmsConversations:
    """Service for managing SMS conversations and message history."""
    
    def __init__(self):
        """Initialize SMS conversations service."""
        self.redis_client = RedisClient()
    
    def get_conversation(self, phone_number: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get SMS conversation for a specific phone number, or all messages if no phone number provided.
        
        Args:
            phone_number: The phone number to get conversation for (optional - if None, gets all messages)
            limit: Maximum number of messages to retrieve (optional)
            
        Returns:
            List of message dictionaries
        """
        if not self.redis_client.is_available():
            logger.warning("Redis not available for getting conversation")
            return []
        
        try:
            # Get message SIDs from Redis sorted set (newest first, then we'll sort properly)
            message_sids = self.redis_client.zrevrange("sms_messages", 0, limit * 2 - 1)  # Get more to filter
            
            if not message_sids:
                return []
            
            message_list = []
            for message_sid in message_sids:
                redis_key = f"sms_message:{message_sid}"
                message_json = self.redis_client.get(redis_key)
                
                if message_json:
                    try:
                        message_data = json.loads(message_json)
                        # If phone_number is provided, filter messages for this conversation
                        if phone_number:
                            if (message_data.get('from') == phone_number or 
                                message_data.get('to') == phone_number):
                                
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
                                
                                # Stop when we have enough messages for this conversation
                                if len(message_list) >= limit:
                                    break
                        else:
                            # No phone number provided, get all messages
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
                            
                            # Stop when we have enough messages
                            if len(message_list) >= limit:
                                break
                                
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ SmsConversations: Failed to parse message JSON: {str(e)}")
                        continue
            
            return message_list
            
        except Exception as e:
            logger.error(f"❌ SmsConversations: Failed to get conversation: {str(e)}")
            return []
    
    def get_conversations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get SMS conversations grouped by phone number.
        
        Args:
            limit: Maximum number of messages to retrieve for grouping
            
        Returns:
            List of conversation dictionaries
        """
        try:
            if not self.redis_client.is_available():
                logger.warning("Redis not available for getting conversations")
                return []
            
            # Get all messages for grouping
            messages = self.get_conversation(limit=limit)
            
            # Group messages by conversation (phone number)
            conversations = {}
            
            for message in messages:
                # Determine the other participant in the conversation
                # If message is from our number, the other participant is the 'To' field
                # If message is to our number, the other participant is the 'From' field
                if message.get('From') == self._get_our_phone_number():
                    # Outgoing message - other participant is the recipient
                    other_participant = message.get('To')
                    is_from_us = True
                else:
                    # Incoming message - other participant is the sender
                    other_participant = message.get('From')
                    is_from_us = False
                
                if not other_participant:
                    continue
                    
                # Create conversation key
                conversation_key = other_participant
                
                if conversation_key not in conversations:
                    conversations[conversation_key] = {
                        'phone_number': other_participant,
                        'participant': other_participant,
                        'messages': [],
                        'last_message': None,
                        'last_message_time': None,
                        'unread_count': 0,
                        'message_count': 0
                    }
                
                # Add message to conversation
                conversation_message = {
                    'id': message.get('MessageSid'),
                    'body': message.get('Body'),
                    'timestamp': message.get('DateCreated') or message.get('StoredAt'),
                    'direction': message.get('Direction'),
                    'status': message.get('Status'),
                    'is_from_us': is_from_us,
                    'from': message.get('From'),
                    'to': message.get('To')
                }
                
                conversations[conversation_key]['messages'].append(conversation_message)
                conversations[conversation_key]['message_count'] += 1
                
                # Update last message info
                message_time = conversation_message['timestamp']
                current_last_time = conversations[conversation_key]['last_message_time']
                
                # Convert both times to strings for consistent comparison
                message_time_str = str(message_time) if message_time else ''
                current_last_time_str = str(current_last_time) if current_last_time else ''
                
                if not current_last_time or (message_time_str and message_time_str > current_last_time_str):
                    conversations[conversation_key]['last_message'] = conversation_message
                    conversations[conversation_key]['last_message_time'] = message_time
            
            # Sort messages within each conversation by timestamp (chronological order)
            for conversation in conversations.values():
                def sort_key(message):
                    timestamp = message.get('timestamp')
                    if not timestamp:
                        return ''
                    # Convert to comparable format
                    if isinstance(timestamp, str):
                        try:
                            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            return timestamp
                    return timestamp
                
                conversation['messages'].sort(key=sort_key, reverse=False)
            
            # Convert to list and sort by last message time
            conversation_list = list(conversations.values())
            conversation_list.sort(key=lambda x: str(x['last_message_time']) if x['last_message_time'] else '', reverse=True)
            
            return conversation_list
            
        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            return []
    
    def delete_conversation(self, phone_number: str) -> bool:
        """
        Delete all messages for a specific phone number conversation.
        
        Args:
            phone_number: The phone number to delete conversation for
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.redis_client.is_available():
            logger.warning("Redis not available for deleting conversation")
            return False
        
        try:
            success = self.redis_client.delete_conversation(phone_number)
            if success:
                logger.info(f"✅ SmsConversations: Successfully deleted conversation for {phone_number}")
            else:
                logger.error(f"❌ SmsConversations: Failed to delete conversation for {phone_number}")
            return success
            
        except Exception as e:
            logger.error(f"❌ SmsConversations: Failed to delete conversation: {str(e)}")
            return False
    
    def _get_our_phone_number(self) -> str:
        """Get our Twilio phone number from environment."""
        import os
        return os.getenv('TWILIO_PHONE_NUMBER', '')

# Global instance
sms_conversations = SmsConversations()
