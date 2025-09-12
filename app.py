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
import redis

# Load environment variables (fallback for local development)
load_dotenv('env')

# Import our organized modules
from app.models.config import Config
from app.models.file_discovery import FileDiscovery
from app.models.tmdb_client import TMDBClient
from app.models.filename_formatter import FilenameFormatter
from app.models.openai_client import OpenAIClient

# Import route registrars
from app.routes.movie_routes import register_movie_routes
from app.routes.file_routes import register_file_routes
from app.routes.media_routes import register_media_routes
from app.routes.download_routes import register_download_routes
from app.routes.plex_routes import register_plex_routes
from app.routes.sms_routes import register_sms_routes
from app.routes.utility_routes import register_utility_routes

# Import external clients
from plex_client import PlexClient
from twilio_client import TwilioClient

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('movie_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_FILE = os.path.expanduser("~/movie-config/config.json")
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', '172.17.0.1')  # Default to Docker bridge IP
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Initialize Redis
redis_client = None
logger.info(f"🔧 Redis connection attempt - Host: {REDIS_HOST}, Port: {REDIS_PORT}, DB: {REDIS_DB}")
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    logger.info(f"🔧 Redis client created, attempting ping to {REDIS_HOST}:{REDIS_PORT}")
    # Test connection
    redis_client.ping()
    logger.info("Redis connected successfully")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
    logger.error(f"🔧 Connection details - Host: {REDIS_HOST}, Port: {REDIS_PORT}, DB: {REDIS_DB}")
    redis_client = None

# Initialize Twilio client
logger.info("Initializing Twilio client...")
twilio_client = TwilioClient()
logger.info(f"Twilio client initialized. Configured: {twilio_client.is_configured()}")

# Initialize Plex client
logger.info("Initializing Plex client...")
plex_client = PlexClient()
logger.info(f"Plex client initialized. Configured: {plex_client.is_configured()}")

# Initialize our models
logger.info("Initializing application models...")
config = Config(use_redis=True, redis_client=redis_client)
file_discovery = FileDiscovery()
tmdb_client = TMDBClient(TMDB_API_KEY, TMDB_BASE_URL)
filename_formatter = FilenameFormatter()
openai_client = OpenAIClient(OPENAI_API_KEY)

logger.info("All models initialized successfully")

# Register all routes
logger.info("Registering API routes...")

# Movie-related routes
register_movie_routes(app, config, tmdb_client, openai_client, file_discovery, filename_formatter)

# File management routes
register_file_routes(app, config, filename_formatter)

# Media paths routes
register_media_routes(app, config)

# Download paths routes
register_download_routes(app, config)

# Plex routes
register_plex_routes(app, plex_client, config)

# SMS routes
register_sms_routes(app, twilio_client, config)

# Utility routes
register_utility_routes(app, config)

logger.info("All routes registered successfully")

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
    logger.info("Starting Movie Management API...")
    app.run(host='0.0.0.0', port=5000, debug=True)
