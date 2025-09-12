#!/usr/bin/env python3
"""
SMS/Twilio-related API routes.
"""

import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def register_sms_routes(app, twilio_client, config):
    """Register SMS/Twilio-related routes with the Flask app."""
    
    @app.route('/api/sms/webhook', methods=['POST'])
    def sms_webhook():
        """Handle incoming SMS webhook from Twilio."""
        try:
            # Get form data from Twilio
            from_number = request.form.get('From', '')
            to_number = request.form.get('To', '')
            message_body = request.form.get('Body', '')
            message_sid = request.form.get('MessageSid', '')
            
            logger.info(f"Received SMS from {from_number} to {to_number}: {message_body}")
            
            # Process the SMS message
            response = twilio_client.process_incoming_sms(
                from_number=from_number,
                to_number=to_number,
                message_body=message_body,
                message_sid=message_sid
            )
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Error processing SMS webhook: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/ayo', methods=['POST'])
    def sms_ayo():
        """Handle 'ayo' SMS command."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            from_number = data.get('from_number', '')
            to_number = data.get('to_number', '')
            message_body = data.get('message_body', '')
            
            if not from_number or not to_number:
                return jsonify({'error': 'from_number and to_number are required'}), 400
            
            logger.info(f"Processing 'ayo' command from {from_number}")
            
            # Send response
            response_message = "Ayo! What's good? 👋"
            success = twilio_client.send_sms(to_number, from_number, response_message)
            
            if success:
                return jsonify({
                    'message': 'Response sent successfully',
                    'response': response_message
                })
            else:
                return jsonify({'error': 'Failed to send response'}), 500
                
        except Exception as e:
            logger.error(f"Error processing 'ayo' command: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/send', methods=['POST'])
    def send_sms():
        """Send an SMS message."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            to = data.get('to', '')
            message = data.get('message', '')
            
            if not to or not message:
                return jsonify({'error': 'to and message are required'}), 400
            
            success = twilio_client.send_sms(to, '', message)
            
            if success:
                return jsonify({'message': 'SMS sent successfully'})
            else:
                return jsonify({'error': 'Failed to send SMS'}), 500
                
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/messages', methods=['GET'])
    def get_sms_messages():
        """Get recent SMS messages."""
        try:
            limit = int(request.args.get('limit', 20))
            messages = twilio_client.get_recent_messages(limit)
            return jsonify({'messages': messages})
        except Exception as e:
            logger.error(f"Error getting SMS messages: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/conversations', methods=['GET'])
    def get_sms_conversations():
        """Get SMS conversations grouped by phone number."""
        try:
            limit = int(request.args.get('limit', 100))
            conversations = twilio_client.get_conversations(limit)
            return jsonify({'conversations': conversations})
        except Exception as e:
            logger.error(f"Error getting SMS conversations: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/status', methods=['GET'])
    def sms_status():
        """Get SMS service status."""
        try:
            status = twilio_client.get_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting SMS status: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/webhook-url', methods=['GET'])
    def get_webhook_url():
        """Get current webhook URL from Twilio."""
        try:
            webhook_url = twilio_client.get_webhook_url()
            return jsonify({'webhook_url': webhook_url})
        except Exception as e:
            logger.error(f"Error getting webhook URL: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/webhook-url', methods=['PUT'])
    def update_webhook_url():
        """Update webhook URL in Twilio."""
        try:
            data = request.get_json()
            if not data or 'webhook_url' not in data:
                return jsonify({'error': 'webhook_url is required'}), 400
            
            webhook_url = data['webhook_url']
            success = twilio_client.update_webhook_url(webhook_url)
            
            if success:
                return jsonify({'message': 'Webhook URL updated successfully'})
            else:
                return jsonify({'error': 'Failed to update webhook URL'}), 500
                
        except Exception as e:
            logger.error(f"Error updating webhook URL: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/phone-settings', methods=['GET'])
    def get_phone_settings():
        """Get all phone number settings from Twilio."""
        try:
            settings = twilio_client.get_phone_settings()
            return jsonify({'settings': settings})
        except Exception as e:
            logger.error(f"Error getting phone settings: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/phone-settings', methods=['PUT'])
    def update_phone_settings():
        """Update phone number settings in Twilio."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            success = twilio_client.update_phone_settings(data)
            
            if success:
                return jsonify({'message': 'Phone settings updated successfully'})
            else:
                return jsonify({'error': 'Failed to update phone settings'}), 500
                
        except Exception as e:
            logger.error(f"Error updating phone settings: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/reply-templates', methods=['GET'])
    def get_reply_templates():
        """Get all reply templates."""
        try:
            templates = config.get_sms_reply_templates()
            return jsonify({'templates': templates})
        except Exception as e:
            logger.error(f"Error getting reply templates: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/reply-templates', methods=['POST'])
    def create_reply_template():
        """Create a new reply template."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            required_fields = ['name', 'template']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'{field} is required'}), 400
            
            success = config.add_sms_reply_template(data)
            
            if success:
                return jsonify({'message': 'Reply template created successfully'})
            else:
                return jsonify({'error': 'Failed to create reply template'}), 500
                
        except Exception as e:
            logger.error(f"Error creating reply template: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/reply-templates/<template_id>', methods=['PUT'])
    def update_reply_template(template_id):
        """Update an existing reply template."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            success = config.update_sms_reply_template(template_id, data)
            
            if success:
                return jsonify({'message': 'Reply template updated successfully'})
            else:
                return jsonify({'error': 'Template not found'}), 404
                
        except Exception as e:
            logger.error(f"Error updating reply template: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/reply-templates/<template_id>', methods=['DELETE'])
    def delete_reply_template(template_id):
        """Delete a reply template."""
        try:
            success = config.delete_sms_reply_template(template_id)
            
            if success:
                return jsonify({'message': 'Reply template deleted successfully'})
            else:
                return jsonify({'error': 'Template not found'}), 404
                
        except Exception as e:
            logger.error(f"Error deleting reply template: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/reply-settings', methods=['GET'])
    def get_reply_settings():
        """Get reply settings."""
        try:
            settings = config.get_sms_reply_settings()
            return jsonify({'settings': settings})
        except Exception as e:
            logger.error(f"Error getting reply settings: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sms/reply-settings', methods=['PUT'])
    def update_reply_settings():
        """Update reply settings."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            success = config.update_sms_reply_settings(data)
            
            if success:
                return jsonify({'message': 'Reply settings updated successfully'})
            else:
                return jsonify({'error': 'Failed to update reply settings'}), 500
                
        except Exception as e:
            logger.error(f"Error updating reply settings: {str(e)}")
            return jsonify({'error': str(e)}), 500
