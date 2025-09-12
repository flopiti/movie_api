#!/usr/bin/env python3
"""
Movie Management REST API
A Flask-based REST API for managing movie file paths and discovering media files,
with TMDB API integration for movie metadata.
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables (fallback for local development)
env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'env')
load_dotenv(env_file)

app = Flask(__name__)
CORS(app)

# Configure logging - Only show our custom logs
# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'movie_api.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Disable Flask and Twilio logging noise
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('twilio').setLevel(logging.WARNING)
logging.getLogger('twilio.http').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Import route blueprints
from .routes.paths import paths_bp
from .routes.movies import movies_bp
from .routes.files import files_bp
from .routes.plex import plex_bp
from .routes.sms import sms_bp
from .routes.system import system_bp

# Import plex agent for monitoring
from .clients.plex_agent import plex_agent

# Register blueprints
app.register_blueprint(paths_bp)
app.register_blueprint(movies_bp)
app.register_blueprint(files_bp)
app.register_blueprint(plex_bp)
app.register_blueprint(sms_bp)
app.register_blueprint(system_bp)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Start the plex agent monitoring service
    try:
        plex_agent.start_monitoring()
        logging.info("📱 PlexAgent: Download monitoring service started successfully")
    except Exception as e:
        logging.error(f"❌ PlexAgent: Failed to start monitoring service: {str(e)}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
