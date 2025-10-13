#!/usr/bin/env python3
"""
Main entry point for the Movie Management REST API.
This file serves as the entry point when running the application from the project root.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the app
from src.app import app

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
