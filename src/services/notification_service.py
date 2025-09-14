#!/usr/bin/env python3
"""
Notification Service
Handles SMS notifications and outgoing message storage.
"""

import logging
from datetime import datetime
from ..clients.twilio_client import TwilioClient
from ..clients.redis_client import RedisClient

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for managing SMS notifications"""
    
    def __init__(self):
        self.twilio_client = TwilioClient()
    
    def send_notification(self, phone_number, message_type, movie_data, additional_context=""):
        """
        Agentic function: Send SMS notification to user
        Returns delivery status and message sent
        """
        try:
            if not phone_number or not message_type or not movie_data:
                logger.warning(f"⚠️ NotificationService: Missing parameters for notification")
                return {
                    'success': False,
                    'message_type': message_type,
                    'error': 'Missing required parameters'
                }
            
            # Extract movie details
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            movie_title = movie_data.get('title')
            
            # The agent should provide the message content via additional_context
            # This service just sends the message, it doesn't generate it
            if not additional_context:
                logger.error(f"❌ NotificationService: No message content provided for {message_type}")
                return {
                    'success': False,
                    'message_type': message_type,
                    'error': 'No message content provided - agent must provide message content'
                }
            
            message = additional_context
            
            # Send the SMS notification
            result = self.twilio_client.send_sms(phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 NotificationService: Sent {message_type} notification to {phone_number}: {message}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(phone_number, message, message_type)
                return {
                    'success': True,
                    'message_type': message_type,
                    'message_sent': message,
                    'phone_number': phone_number,
                    'movie_title': movie_title,
                    'year': year
                }
            else:
                logger.error(f"❌ NotificationService: Failed to send {message_type} notification: {result.get('error')}")
                return {
                    'success': False,
                    'message_type': message_type,
                    'error': result.get('error', 'Unknown SMS error')
                }
                
        except Exception as e:
            logger.error(f"❌ NotificationService: Error sending notification: {str(e)}")
            return {
                'success': False,
                'message_type': message_type,
                'error': str(e)
            }
    
    def _store_outgoing_sms(self, phone_number: str, message: str, message_type: str = "notification") -> bool:
        """Store outgoing SMS message in Redis conversation"""
        try:
            redis_client = RedisClient()
            
            if not redis_client.is_available():
                logger.warning("📱 NotificationService: Redis not available - cannot store outgoing SMS")
                return False
            
            # Prepare message data for Redis storage
            message_data = {
                'MessageSid': f"outgoing_{datetime.now().timestamp()}",
                'status': 'sent',
                'To': phone_number,
                'From': 'system',  # System-generated message
                'Body': message,
                'timestamp': datetime.now().isoformat(),
                'direction': 'outbound',
                'message_type': message_type
            }
            
            success = redis_client.store_sms_message(message_data)
            if success:
                logger.info(f"📱 NotificationService: Stored outgoing SMS in Redis conversation")
            else:
                logger.error(f"❌ NotificationService: Failed to store outgoing SMS in Redis")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ NotificationService: Error storing outgoing SMS in Redis: {str(e)}")
            return False

    def send_movie_added_notification(self, movie_data, phone_number):
        """Send SMS notification when movie is added to download queue"""
        try:
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            message = f"🎬 Adding '{movie_data.get('title')}' ({year}) to your download queue. I'll let you know when it starts downloading!"
            
            result = self.twilio_client.send_sms(phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 NotificationService: Sent movie added notification to {phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(phone_number, message, "movie_added")
            else:
                logger.error(f"❌ NotificationService: Failed to send movie added notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ NotificationService: Error sending movie added notification: {str(e)}")
    
    def send_search_triggered_notification(self, movie_data, phone_number):
        """Send SMS notification when search is triggered for existing movie"""
        try:
            release_date = movie_data.get('release_date', '')
            year = release_date.split('-')[0] if release_date else 'Unknown year'
            message = f"🔍 Searching for '{movie_data.get('title')}' ({year}) releases. I'll let you know when download starts!"
            
            result = self.twilio_client.send_sms(phone_number, message)
            
            if result.get('success'):
                logger.info(f"📱 NotificationService: Sent search triggered notification to {phone_number}")
                # Store outgoing SMS in Redis conversation
                self._store_outgoing_sms(phone_number, message, "search_triggered")
            else:
                logger.error(f"❌ NotificationService: Failed to send search triggered notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ NotificationService: Error sending search triggered notification: {str(e)}")
    
    def send_download_started_notification(self, request):
        """Send SMS notification when download starts using agentic function"""
        try:
            # Create movie data object for the notification function
            movie_data = {
                'title': request.movie_title,
                'release_date': f"{request.movie_year}-01-01",  # Approximate date
                'id': request.tmdb_id
            }
            
            # Use the agentic notification function
            result = self.send_notification(
                phone_number=request.phone_number,
                message_type="download_started",
                movie_data=movie_data
            )
            
            if result.get('success'):
                logger.info(f"📱 NotificationService: Sent download started notification to {request.phone_number}")
            else:
                logger.error(f"❌ NotificationService: Failed to send download started notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ NotificationService: Error sending download started notification: {str(e)}")
    
    def send_download_completed_notification(self, request):
        """Send SMS notification when download completes using agentic function"""
        try:
            # Create movie data object for the notification function
            movie_data = {
                'title': request.movie_title,
                'release_date': f"{request.movie_year}-01-01",  # Approximate date
                'id': request.tmdb_id
            }
            
            # Use the agentic notification function
            result = self.send_notification(
                phone_number=request.phone_number,
                message_type="download_completed",
                movie_data=movie_data
            )
            
            if result.get('success'):
                logger.info(f"📱 NotificationService: Sent download completed notification to {request.phone_number}")
            else:
                logger.error(f"❌ NotificationService: Failed to send download completed notification: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ NotificationService: Error sending download completed notification: {str(e)}")
