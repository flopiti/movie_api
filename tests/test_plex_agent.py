#!/usr/bin/env python3
"""
Test script for PlexAgent - Mocked Redis Configuration
"""

import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Mock Redis module BEFORE any imports that use it
class MockRedis:
    def __init__(self, *args, **kwargs):
        self.data = {}
    
    def ping(self):
        return True
    
    def get(self, key):
        return self.data.get(key)
    
    def set(self, key, value):
        self.data[key] = value
    
    def keys(self, pattern):
        if pattern == "download_request:*":
            return [k for k in self.data.keys() if k.startswith("download_request:")]
        return []
    
    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
    
    def zadd(self, key, mapping):
        pass
    
    def zrevrange(self, key, start, end):
        return []
    
    def zrem(self, key, member):
        pass

class MockRedisModule:
    def Redis(self, *args, **kwargs):
        return MockRedis()

# Replace redis module in sys.modules
sys.modules['redis'] = MockRedisModule()

# Now you can import and test your agent without Redis connection issues
from src.clients.plex_agent import PlexAgent

if __name__ == '__main__':
    print("✅ Redis mocked successfully!")
    print("You can now import and test PlexAgent without Redis connection issues.")
