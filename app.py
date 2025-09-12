#!/usr/bin/env python3
"""
Movie Management REST API
A Flask-based REST API for managing movie file paths and discovering media files,
with TMDB API integration for movie metadata.
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables (fallback for local development)
load_dotenv('env')

app = Flask(__name__)
CORS(app)

# Import route blueprints
from routes.paths import paths_bp
from routes.movies import movies_bp
from routes.files import files_bp
from routes.plex import plex_bp
from routes.sms import sms_bp
from routes.system import system_bp

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
    app.run(debug=True, host='0.0.0.0', port=5000)
