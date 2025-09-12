#!/usr/bin/env python3
"""
SMS/Twilio Routes
Routes for SMS functionality, webhooks, and Twilio integration.
"""

import os
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from ..clients.twilio_client import TwilioClient
from ..clients.openai_client import OpenAIClient
from ..clients.tmdb_client import TMDBClient
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))
from config.config import config, OPENAI_API_KEY, TMDB_API_KEY
from PROMPTS import SMS_RESPONSE_PROMPT
from download_monitor import download_monitor

logger = logging.getLogger(__name__)

def get_conversation_history(phone_number: str, limit: int = 5) -> list:
    """Get conversation history for a phone number from Redis."""
    try:
        # Get recent messages to focus on latest conversation
        messages = twilio_client.get_recent_messages(limit * 2)  # Get enough to filter by phone
        
        # Filter messages for this conversation (both directions)
        conversation_messages = []
        for message in messages:
            if (message.get('From') == phone_number or 
                message.get('To') == phone_number or
                message.get('from') == phone_number or 
                message.get('to') == phone_number):
                
                # Determine who sent the message
                sender = message.get('From', message.get('from', ''))
                if sender == phone_number:
                    speaker = "USER"
                else:
                    speaker = "SYSTEM"
                
                # Format: "SPEAKER: message content"
                formatted_message = f"{speaker}: {message.get('Body', message.get('body', ''))}"
                conversation_messages.append(formatted_message)
        
        # Return only the formatted messages, limited to recent messages
        return conversation_messages[:limit]
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return []

# Create blueprint
sms_bp = Blueprint('sms', __name__)

# Initialize clients
twilio_client = TwilioClient()
openai_client = OpenAIClient(OPENAI_API_KEY)
tmdb_client = TMDBClient(TMDB_API_KEY)

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
        twilio_client.store_incoming_message(message_data)
        
        # Get conversation history for movie detection
        conversation_history = get_conversation_history(message_data['From'])
        
        # Try to detect movie in conversation
        movie_result = None
        response_message = None  # Initialize response message
        if conversation_history:
            logger.info(f"🎬 SMS Webhook: Analyzing conversation for movie detection...")
            logger.info(f"🎬 SMS Webhook: Conversation history ({len(conversation_history)} messages): {conversation_history}")
            movie_result = openai_client.getMovieName(conversation_history)
            logger.info(f"🎬 SMS Webhook: Movie detection result: {movie_result}")
        else:
            # Fallback: analyze just the current message
            logger.info(f"🎬 SMS Webhook: No conversation history, analyzing current message...")
            logger.info(f"🎬 SMS Webhook: Current message: {[message_data['Body']]}")
            movie_result = openai_client.getMovieName([message_data['Body']])
            logger.info(f"🎬 SMS Webhook: Movie detection result: {movie_result}")
        
        if movie_result and movie_result.get('success') and movie_result.get('movie_name') and movie_result.get('movie_name') != "No movie identified":
            logger.info(f"🎬 SMS Webhook: Movie detected: {movie_result['movie_name']}")
            
            # Search TMDB for the movie
            tmdb_result = tmdb_client.search_movie(movie_result['movie_name'])
            if tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
                movie_data = tmdb_result['results'][0]  # Get first result
                
                # Extract year from release_date (format: YYYY-MM-DD)
                release_date = movie_data.get('release_date', '')
                year = release_date.split('-')[0] if release_date else 'Unknown year'
                
                logger.info(f"🎬 SMS Webhook: TMDB found movie: {movie_data.get('title')} ({year})")
                
                # Add download request to the monitor
                tmdb_id = movie_data.get('id')
                if tmdb_id:
                    logger.info(f"📱 SMS Webhook: Adding download request for {movie_data.get('title')} ({year}) from {message_data['From']}")
                    
                    # Check if Radarr is configured first
                    if not download_monitor.is_radarr_configured():
                        response_message = f"🎬 I found '{movie_data.get('title')} ({year})' but Radarr is not configured yet. Please set up your Radarr API key to enable downloads!"
                        logger.warning(f"⚠️ SMS Webhook: Radarr not configured - cannot process download request for {movie_data.get('title')}")
                    else:
                        success = download_monitor.add_download_request(
                            tmdb_id=tmdb_id,
                            movie_title=movie_data.get('title'),
                            movie_year=year,
                            phone_number=message_data['From']
                        )
                        
                        if success:
                            response_message = f"🎬 Great! I found '{movie_data.get('title')} ({year})' and added it to your download queue. I'll send you updates as the download progresses!"
                            logger.info(f"✅ SMS Webhook: Download request added successfully for {movie_data.get('title')}")
                        else:
                            response_message = f"🎬 I found '{movie_data.get('title')} ({year})' but it's already in your download queue. I'll keep you updated on the progress!"
                            logger.info(f"ℹ️ SMS Webhook: Download request already exists for {movie_data.get('title')}")
                
                # Don't set response_message - let it fall through to ChatGPT with movie context
            else:
                logger.info(f"🎬 SMS Webhook: Movie not found in TMDB: {movie_result['movie_name']}")
                # Don't set response_message - let it fall through to ChatGPT with movie context
        else:
            logger.info(f"🎬 SMS Webhook: No movie identified in conversation")
            # Don't set response_message - let it fall through to ChatGPT
        
        # Get reply settings and templates
        reply_settings = config.get_sms_reply_settings()
        reply_templates = config.get_sms_reply_templates()
        
        # Always try ChatGPT first if no movie-specific response was generated
        if not response_message:
            logger.info(f"🤖 SMS Webhook: No movie response, calling ChatGPT...")
            # Use ChatGPT to generate response
            chatgpt_prompt = reply_settings.get('chatgpt_prompt', SMS_RESPONSE_PROMPT)
            
            # Add context about movie detection result
            movie_context = ""
            if movie_result and movie_result.get('success') and movie_result.get('movie_name') and movie_result.get('movie_name') != "No movie identified":
                # Check if movie was found in TMDB
                if tmdb_result and tmdb_result.get('results') and len(tmdb_result.get('results', [])) > 0:
                    movie_data = tmdb_result['results'][0]
                    release_date = movie_data.get('release_date', '')
                    year = release_date.split('-')[0] if release_date else 'Unknown year'
                    movie_context = f" (Note: A movie '{movie_data.get('title')} ({year})' was identified and found in our database)"
                else:
                    movie_context = f" (Note: A movie '{movie_result['movie_name']}' was identified but not found in our database)"
            else:
                movie_context = " (Note: No movie was identified in the conversation)"
            
            logger.info(f"🤖 OpenAI SMS Request: Generating response for message '{message_data['Body']}' from '{message_data['From']}'{movie_context}")
            chatgpt_result = openai_client.generate_sms_response(
                message_data['Body'], 
                message_data['From'], 
                chatgpt_prompt,
                movie_context=movie_context
            )
            
            logger.info(f"🤖 OpenAI SMS Result: {chatgpt_result}")
            
            if chatgpt_result.get('success'):
                response_message = chatgpt_result['response']
                logger.info(f"✅ OpenAI SMS Response: Generated response '{response_message}'")
            else:
                logger.error(f"❌ OpenAI SMS Failed: {chatgpt_result.get('error', 'Unknown error')}")
                # Fallback to template system if ChatGPT fails
                response_message = None
            
            # If ChatGPT is not enabled or failed, use template system
            if not response_message:
                # Find matching template based on keywords or use default
                matching_template = None
                
                # First, try to find a template with matching keywords
                for template in reply_templates:
                    if template.get('enabled', True) and template.get('keywords'):
                        keywords = template['keywords']
                        message_body = message_data['Body'].lower()
                        
                        # Check if any keyword matches
                        if any(keyword.lower() in message_body for keyword in keywords):
                            matching_template = template
                            break
                
                # If no keyword match, use the default template
                if not matching_template:
                    default_template = next((t for t in reply_templates if t.get('name') == 'default'), None)
                    if default_template and default_template.get('enabled', True):
                        matching_template = default_template
                
                # Generate response message
                if matching_template:
                    template_text = matching_template['template']
                    
                    # Replace placeholders in template
                    response_message = template_text.replace('{sender}', message_data['From'])
                    response_message = response_message.replace('{message}', message_data['Body'])
                    response_message = response_message.replace('{timestamp}', message_data['timestamp'])
                    response_message = response_message.replace('{phone_number}', twilio_client.phone_number or 'Unknown')

                else:
                    # Fallback to simple acknowledgment
                    fallback_template = reply_settings.get('fallback_message', f"Message received: '{message_data['Body']}'")
                    
                    # Replace placeholders in fallback message
                    response_message = fallback_template.replace('{sender}', message_data['From'])
                    response_message = response_message.replace('{message}', message_data['Body'])
                    response_message = response_message.replace('{timestamp}', message_data['timestamp'])
                    response_message = response_message.replace('{phone_number}', twilio_client.phone_number or 'Unknown')
        
        # If no auto-reply is configured, use ChatGPT to generate a response
        if not response_message:
            logger.info(f"🤖 SMS Webhook: No response generated, calling ChatGPT as fallback...")
            chatgpt_result = openai_client.generate_sms_response(
                message_data['Body'], 
                message_data['From'], 
                SMS_RESPONSE_PROMPT,
                movie_context=" (Note: No movie was identified in the conversation)"
            )
            
            logger.info(f"🤖 OpenAI Fallback Result: {chatgpt_result}")
            
            if chatgpt_result.get('success'):
                response_message = chatgpt_result['response']
                logger.info(f"✅ OpenAI Fallback Response: Generated response '{response_message}'")
            else:
                logger.error(f"❌ OpenAI Fallback Failed: {chatgpt_result.get('error', 'Unknown error')}")
                response_message = "I received your message but couldn't identify a movie. Could you please specify which movie you'd like me to get?"

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
        twilio_client._store_message_in_redis(outgoing_message_data)
        
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
        messages = twilio_client.get_recent_messages(limit)
        
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
        messages = twilio_client.get_recent_messages(limit)
        
        # Group messages by conversation (phone number)
        conversations = {}
        
        for message in messages:
            # Determine the other participant in the conversation
            # If message is from our number, the other participant is the 'To' field
            # If message is to our number, the other participant is the 'From' field
            if message.get('From') == twilio_client.phone_number:
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
            if not conversations[conversation_key]['last_message_time'] or message_time > conversations[conversation_key]['last_message_time']:
                conversations[conversation_key]['last_message'] = conversation_message
                conversations[conversation_key]['last_message_time'] = message_time
        
        # Sort messages within each conversation by timestamp
        for conversation in conversations.values():
            conversation['messages'].sort(key=lambda x: x['timestamp'] or '')
        
        # Convert to list and sort by last message time
        conversation_list = list(conversations.values())
        conversation_list.sort(key=lambda x: x['last_message_time'] or '', reverse=True)
        
        return jsonify({
            'conversations': conversation_list,
            'count': len(conversation_list),
            'total_messages': sum(len(conv['messages']) for conv in conversation_list)
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to retrieve conversations: {str(e)}'}), 500

@sms_bp.route('/api/sms/status', methods=['GET'])
def sms_status():
    """Get SMS service status and configuration."""
    try:
        webhook_info = twilio_client.get_webhook_url()
        
        return jsonify({
            'configured': twilio_client.is_configured(),
            'phone_number': twilio_client.phone_number if twilio_client.is_configured() else None,
            'redis_available': twilio_client.redis_client is not None,
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

# SMS Reply Management Endpoints
@sms_bp.route('/api/sms/reply-templates', methods=['GET'])
def get_reply_templates():
    """Get all SMS reply templates."""
    try:
        templates = config.get_sms_reply_templates()
        return jsonify({
            'templates': templates,
            'count': len(templates)
        }), 200
        
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to get reply templates: {str(e)}'}), 500

@sms_bp.route('/api/sms/reply-templates', methods=['POST'])
def create_reply_template():
    """Create a new SMS reply template."""
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'template' not in data:
            return jsonify({'error': 'Missing required fields: name, template'}), 400
        
        template_data = {
            'name': data['name'],
            'template': data['template'],
            'enabled': data.get('enabled', True),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Add optional fields
        if 'description' in data:
            template_data['description'] = data['description']
        if 'keywords' in data:
            template_data['keywords'] = data['keywords']
        
        success = config.add_sms_reply_template(template_data)
        
        if success:
            return jsonify({
                'message': 'Reply template created successfully',
                'template': template_data
            }), 201
        else:
            return jsonify({'error': 'Failed to create reply template'}), 500
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to create reply template: {str(e)}'}), 500

@sms_bp.route('/api/sms/reply-templates/<template_id>', methods=['PUT'])
def update_reply_template(template_id):
    """Update an existing SMS reply template."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get existing template
        templates = config.get_sms_reply_templates()
        template = next((t for t in templates if t['id'] == template_id), None)
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Update template with new data
        updated_template = template.copy()
        updated_template['updated_at'] = datetime.now().isoformat()
        
        if 'name' in data:
            updated_template['name'] = data['name']
        if 'template' in data:
            updated_template['template'] = data['template']
        if 'enabled' in data:
            updated_template['enabled'] = data['enabled']
        if 'description' in data:
            updated_template['description'] = data['description']
        if 'keywords' in data:
            updated_template['keywords'] = data['keywords']
        
        success = config.update_sms_reply_template(template_id, updated_template)
        
        if success:
            return jsonify({
                'message': 'Reply template updated successfully',
                'template': updated_template
            }), 200
        else:
            return jsonify({'error': 'Failed to update reply template'}), 500
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to update reply template: {str(e)}'}), 500

@sms_bp.route('/api/sms/reply-templates/<template_id>', methods=['DELETE'])
def delete_reply_template(template_id):
    """Delete an SMS reply template."""
    try:
        success = config.delete_sms_reply_template(template_id)
        
        if success:
            return jsonify({'message': 'Reply template deleted successfully'}), 200
        else:
            return jsonify({'error': 'Template not found or failed to delete'}), 404
            
    except Exception as e:
        pass
        return jsonify({'error': f'Failed to delete reply template: {str(e)}'}), 500

@sms_bp.route('/api/sms/reply-settings', methods=['GET'])
def get_reply_settings():
    """Get SMS reply settings."""
    try:
        settings = config.get_sms_reply_settings()
        return jsonify(settings), 200
        
    except Exception as e:
        pass
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
        pass
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
            'redis_available': download_monitor.redis_client is not None,
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
