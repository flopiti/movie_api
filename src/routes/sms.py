#!/usr/bin/env python3
"""
SMS/Twilio Routes
Routes for SMS functionality, webhooks, and Twilio integration.
"""

import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from ..clients.twilio_client import TwilioClient
from ..clients.openai_client import OpenAIClient
from ..clients.tmdb_client import TMDBClient
from ..clients.plex_agent import PlexAgent
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))
from config.config import config, OPENAI_API_KEY, TMDB_API_KEY, redis_client
from ..clients.PROMPTS import SMS_RESPONSE_PROMPT
from ..services.download_monitor import download_monitor
from ..services.sms_conversations import sms_conversations

logger = logging.getLogger(__name__)


# Create blueprint
sms_bp = Blueprint('sms', __name__)

# Initialize clients
twilio_client = TwilioClient()
openai_client = OpenAIClient(OPENAI_API_KEY)
tmdb_client = TMDBClient(TMDB_API_KEY)
plex_agent = PlexAgent()

@sms_bp.route('/api/sms/webhook', methods=['POST'])
def sms_webhook():
    """Webhook endpoint to receive SMS messages from Twilio."""
    try:
        # Get message data from Twilio webhook
        message_data = {
            'MessageSid': request.form.get('MessageSid'),
            'From': request.form.get('From'),
            'To': request.form.get('To'),
            'Body': request.form.get('Body'),
            'NumMedia': request.form.get('NumMedia', '0'),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"📱 SMS Webhook: Received message from {message_data['From']}: '{message_data['Body']}'")

        # Store incoming message in Redis
        if redis_client.is_available():
            success = redis_client.store_sms_message(message_data)
            if not success:
                logger.error(f"❌ Failed to store incoming message in Redis")
        
        # Get conversation history for movie detection
        messages = sms_conversations.get_conversation(message_data['From'], 10)
        conversation_history = []
        for message in messages:
            # Determine who sent the message
            sender = message.get('From', message.get('from', ''))
            if sender == message_data['From']:
                speaker = "USER"
            else:
                speaker = "SYSTEM"
            
            # Format: "SPEAKER: message content"
            formatted_message = f"{speaker}: {message.get('Body', message.get('body', ''))}"
            conversation_history.append(formatted_message)
        
        # Use PlexAgent to process the message and generate response
        logger.info(f"🎬 SMS Webhook: Processing message with PlexAgent...")
        agent_result = plex_agent.Answer(message_data, conversation_history)
        response_message = agent_result['response_message']

        # Store the outgoing reply message in Redis
        outgoing_message_data = {
            'message_sid': f"webhook_reply_{datetime.now().timestamp()}",
            'status': 'sent',
            'to': message_data['From'],  # Reply goes to the sender
            'from': message_data['To'],  # From our Twilio number
            'body': response_message,
            'date_created': datetime.now().isoformat(),
            'direction': 'outbound',
            'stored_at': datetime.now().isoformat(),
            'num_media': '0'
        }
        
        # Store the outgoing message
        if redis_client.is_available():
            success = redis_client.store_sms_message(outgoing_message_data)
            if not success:
                logger.error(f"❌ Failed to store outgoing message in Redis")
        
        logger.info(f"📱 SMS Webhook: Sending response to {message_data['From']}: '{response_message}'")
        
        # Create TwiML response
        twiml_response = twilio_client.create_webhook_response(response_message)
        logger.info(f"📱 SMS Webhook: TwiML Response: {twiml_response}")
        
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"❌ SMS Webhook Error: {str(e)}")
        logger.error(f"❌ SMS Webhook Error Details: {type(e).__name__}")
        import traceback
        logger.error(f"❌ SMS Webhook Traceback: {traceback.format_exc()}")
        return twilio_client.create_webhook_response("Error processing message"), 500, {'Content-Type': 'text/xml'}

# For testing, sending SMS messages directly
@sms_bp.route('/api/sms/send', methods=['POST'])
def send_sms():
    """Send an SMS message."""
    try:
        data = request.get_json()
        if not data or 'to' not in data or 'message' not in data:
            return jsonify({'error': 'Missing required fields: to, message'}), 400
        
        to = data['to']
        message = data['message']
        
        if not twilio_client.is_configured():
            return jsonify({'error': 'Twilio not configured'}), 500
        
        result = twilio_client.send_sms(to, message)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to send SMS: {str(e)}'}), 500

@sms_bp.route('/api/sms/messages', methods=['GET'])
def get_sms_messages():
    """Get recent SMS messages from Twilio API."""
    try:
        limit = request.args.get('limit', 20, type=int)
        messages = sms_conversations.get_conversation(limit=limit)
        
        return jsonify({
            'messages': messages,
            'count': len(messages)
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to retrieve messages: {str(e)}'}), 500

@sms_bp.route('/api/sms/conversations', methods=['GET'])
def get_sms_conversations():
    """Get SMS conversations grouped by phone number."""
    try:
        limit = request.args.get('limit', 100, type=int)
        conversations = sms_conversations.get_conversations(limit)
        
        return jsonify({
            'conversations': conversations,
            'count': len(conversations),
            'total_messages': sum(len(conv['messages']) for conv in conversations)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to retrieve conversations: {str(e)}")
        return jsonify({'error': f'Failed to retrieve conversations: {str(e)}'}), 500

@sms_bp.route('/api/sms/conversations/<phone_number>', methods=['DELETE'])
def delete_sms_conversation(phone_number):
    """Delete all messages for a specific phone number conversation."""
    try:
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
        
        success = sms_conversations.delete_conversation(phone_number)
        
        if success:
            return jsonify({
                'message': f'Conversation for {phone_number} deleted successfully',
                'phone_number': phone_number
            }), 200
        else:
            return jsonify({'error': f'Failed to delete conversation for {phone_number}'}), 500
            
    except Exception as e:
        logger.error(f"❌ SMS Delete Conversation Error: {str(e)}")
        return jsonify({'error': f'Failed to delete conversation: {str(e)}'}), 500

@sms_bp.route('/api/sms/status', methods=['GET'])
def sms_status():
    """Get SMS service status and configuration."""
    try:
        webhook_info = twilio_client.get_webhook_url()
        
        return jsonify({
            'configured': twilio_client.is_configured(),
            'phone_number': twilio_client.phone_number if twilio_client.is_configured() else None,
            'redis_available': redis_client.is_available(),
            'account_sid_set': bool(os.getenv('TWILIO_ACCOUNT_SID')),
            'auth_token_set': bool(os.getenv('TWILIO_AUTH_TOKEN')),
            'phone_number_set': bool(os.getenv('TWILIO_PHONE_NUMBER')),
            'webhook_url': f"{request.host_url}api/sms/webhook",
            'current_webhook': webhook_info.get('webhook_url') if webhook_info.get('success') else None,
            'webhook_method': webhook_info.get('webhook_method') if webhook_info.get('success') else None
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get status: {str(e)}'}), 500

@sms_bp.route('/api/sms/webhook-url', methods=['GET'])
def get_webhook_url():
    """Get current webhook URL from Twilio."""
    try:
        result = twilio_client.get_webhook_url()
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get webhook URL: {str(e)}'}), 500

@sms_bp.route('/api/sms/webhook-url', methods=['PUT'])
def update_webhook_url():
    """Update webhook URL in Twilio."""
    try:
        data = request.get_json()
        if not data or 'webhook_url' not in data:
            return jsonify({'error': 'Missing webhook_url field'}), 400
        
        webhook_url = data['webhook_url']
        result = twilio_client.update_webhook_url(webhook_url)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to update webhook URL: {str(e)}'}), 500

@sms_bp.route('/api/sms/phone-settings', methods=['GET'])
def get_phone_settings():
    """Get all phone number settings from Twilio."""
    try:
        result = twilio_client.get_phone_number_settings()
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get phone settings: {str(e)}'}), 500

@sms_bp.route('/api/sms/phone-settings', methods=['PUT'])
def update_phone_settings():
    """Update phone number settings in Twilio."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No settings provided'}), 400
        
        result = twilio_client.update_phone_number_settings(data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to update phone settings: {str(e)}'}), 500

@sms_bp.route('/api/sms/reply-settings', methods=['GET'])
def get_reply_settings():
    """Get SMS reply settings."""
    try:
        settings = config.get_sms_reply_settings()
        return jsonify(settings), 200
        
    except Exception as e:
        logger.error(f"Failed to get reply settings: {str(e)}")
        return jsonify({'error': f'Failed to get reply settings: {str(e)}'}), 500

@sms_bp.route('/api/sms/reply-settings', methods=['PUT'])
def update_reply_settings():
    """Update SMS reply settings."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        success = config.update_sms_reply_settings(data)
        
        if success:
            return jsonify({
                'message': 'Reply settings updated successfully',
                'settings': data
            }), 200
        else:
            return jsonify({'error': 'Failed to update reply settings'}), 500
            
    except Exception as e:
        logger.error(f"Failed to update reply settings: {str(e)}")
        return jsonify({'error': f'Failed to update reply settings: {str(e)}'}), 500

# Download Management Endpoints
@sms_bp.route('/api/sms/downloads', methods=['GET'])
def get_download_requests():
    """Get all download requests."""
    try:
        requests = download_monitor.get_download_requests()
        return jsonify({
            'download_requests': requests,
            'count': len(requests)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ SMS Downloads Error: {str(e)}")
        return jsonify({'error': f'Failed to get download requests: {str(e)}'}), 500

@sms_bp.route('/api/sms/downloads/<int:tmdb_id>', methods=['GET'])
def get_download_request(tmdb_id):
    """Get a specific download request."""
    try:
        request = download_monitor.get_download_request(tmdb_id)
        if request:
            return jsonify(request), 200
        else:
            return jsonify({'error': 'Download request not found'}), 404
            
    except Exception as e:
        logger.error(f"❌ SMS Download Request Error: {str(e)}")
        return jsonify({'error': f'Failed to get download request: {str(e)}'}), 500

@sms_bp.route('/api/sms/downloads', methods=['POST'])
def create_download_request():
    """Create a new download request."""
    try:
        data = request.get_json()
        if not data or 'tmdb_id' not in data or 'movie_title' not in data or 'movie_year' not in data or 'phone_number' not in data:
            return jsonify({'error': 'Missing required fields: tmdb_id, movie_title, movie_year, phone_number'}), 400
        
        success = download_monitor.add_download_request(
            tmdb_id=data['tmdb_id'],
            movie_title=data['movie_title'],
            movie_year=data['movie_year'],
            phone_number=data['phone_number']
        )
        
        if success:
            return jsonify({
                'message': 'Download request created successfully',
                'tmdb_id': data['tmdb_id'],
                'movie_title': data['movie_title'],
                'movie_year': data['movie_year'],
                'phone_number': data['phone_number']
            }), 201
        else:
            return jsonify({'error': 'Download request already exists or failed to create'}), 400
            
    except Exception as e:
        logger.error(f"❌ SMS Create Download Request Error: {str(e)}")
        return jsonify({'error': f'Failed to create download request: {str(e)}'}), 500

@sms_bp.route('/api/sms/download-monitor/start', methods=['POST'])
def start_download_monitor():
    """Start the download monitoring service."""
    try:
        download_monitor.start_monitoring()
        return jsonify({'message': 'Download monitoring service started'}), 200
        
    except Exception as e:
        logger.error(f"❌ SMS Start Monitor Error: {str(e)}")
        return jsonify({'error': f'Failed to start download monitor: {str(e)}'}), 500

@sms_bp.route('/api/sms/download-monitor/stop', methods=['POST'])
def stop_download_monitor():
    """Stop the download monitoring service."""
    try:
        download_monitor.stop_monitoring()
        return jsonify({'message': 'Download monitoring service stopped'}), 200
        
    except Exception as e:
        logger.error(f"❌ SMS Stop Monitor Error: {str(e)}")
        return jsonify({'error': f'Failed to stop download monitor: {str(e)}'}), 500

@sms_bp.route('/api/sms/downloads/clear', methods=['POST'])
def clear_all_download_requests():
    """Clear all download requests from memory."""
    try:
        download_monitor.clear_all_requests()
        return jsonify({'message': 'All download requests cleared successfully'}), 200
        
    except Exception as e:
        logger.error(f"❌ SMS Clear Requests Error: {str(e)}")
        return jsonify({'error': f'Failed to clear download requests: {str(e)}'}), 500

@sms_bp.route('/api/sms/downloads/<int:tmdb_id>', methods=['DELETE'])
def cancel_download_request(tmdb_id):
    """Cancel a specific download request."""
    try:
        success = download_monitor.cancel_download_request(tmdb_id)
        if success:
            return jsonify({'message': f'Download request for TMDB ID {tmdb_id} cancelled successfully'}), 200
        else:
            return jsonify({'error': 'Download request not found or failed to cancel'}), 404
            
    except Exception as e:
        logger.error(f"❌ SMS Cancel Download Request Error: {str(e)}")
        return jsonify({'error': f'Failed to cancel download request: {str(e)}'}), 500

@sms_bp.route('/api/sms/download-monitor/status', methods=['GET'])
def get_download_monitor_status():
    """Get download monitoring service status."""
    try:
        radarr_status = download_monitor.get_radarr_config_status()
        
        return jsonify({
            'running': download_monitor.running,
            'radarr_available': download_monitor.radarr_client is not None,
            'twilio_available': download_monitor.twilio_client.is_configured(),
            'redis_available': download_monitor.redis_client.is_available(),
            'active_requests': len(download_monitor.download_requests),
            'radarr_config': radarr_status
        }), 200
        
    except Exception as e:
        logger.error(f"❌ SMS Monitor Status Error: {str(e)}")
        return jsonify({'error': f'Failed to get monitor status: {str(e)}'}), 500

@sms_bp.route('/api/sms/radarr-config', methods=['GET'])
def get_radarr_config():
    """Get Radarr configuration status."""
    try:
        radarr_status = download_monitor.get_radarr_config_status()
        return jsonify(radarr_status), 200
        
    except Exception as e:
        logger.error(f"❌ SMS Radarr Config Error: {str(e)}")
        return jsonify({'error': f'Failed to get Radarr config: {str(e)}'}), 500
