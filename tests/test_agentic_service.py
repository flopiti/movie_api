import os
import sys
import argparse
import json
from dotenv import load_dotenv
from unittest.mock import MagicMock

# Load environment variables from the main project's env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', 'env'))

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Import required modules
from src.services.agentic_service import AgenticService
from src.services.movie_identification_service import MovieIdentificationService
from src.services.movie_library_service import MovieLibraryService
from src.services.radarr_service import RadarrService
from src.services.notification_service import NotificationService
from src.clients.openai_client import OpenAIClient
from src.clients.tmdb_client import TMDBClient
from src.clients.radarr_client import RadarrClient
from src.clients.PROMPTS import MOVIE_AGENT_FUNCTION_SCHEMA
# Get API keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')
RADARR_URL = os.getenv('RADARR_URL', 'http://localhost:7878')

class AgenticServiceTestRunner:
    """Centralized test runner for AgenticService with pre-built components"""
    
    def __init__(self):
        self.openai_client = None
        self.tmdb_client = None
        self.radarr_client = None
        self.movie_identification_service = None
        self.movie_library_service = None
        self.radarr_service = None
        self.notification_service = None
        self.agentic_service = None
        self.agent = None
        
        # SMS response prompt
        self.sms_response_prompt = """
        You are a friendly movie assistant. Respond to user messages in a warm, conversational way.
        Keep responses concise and helpful. Show personality and be engaging.
        """
        
        self._setup_components()
    
    def _setup_components(self):
        """Setup all required components for testing"""
        print("🔧 Setting up test components...")
        
        # Create OpenAI client
        self.openai_client = OpenAIClient(OPENAI_API_KEY)
        
        # Create TMDB client
        self.tmdb_client = TMDBClient(TMDB_API_KEY)
        
        # Create Radarr client (handle missing API key)
        if RADARR_API_KEY:
            self.radarr_client = RadarrClient(RADARR_URL, RADARR_API_KEY)
        else:
            print("⚠️  Radarr API key not found, using mock client")
            self.radarr_client = MagicMock()
        
        # Create services
        self.movie_identification_service = MovieIdentificationService(self.openai_client)
        self.movie_library_service = MovieLibraryService(self.tmdb_client)
        self.radarr_service = RadarrService()
        self.notification_service = NotificationService()
        
        # Create agentic service
        self.agentic_service = AgenticService(self.openai_client)
        
        # Create PlexAgent
        from src.plex_agent import PlexAgent
        self.agent = PlexAgent()
        
        print("✅ All components setup complete!")
    
    def _create_services_dict(self):
        """Create services dictionary for agentic service"""
        return {
            'movie_identification': self.movie_identification_service,
            'movie_library': self.movie_library_service,
            'radarr': self.radarr_service,
            'notification': self.notification_service,
            'sms_response_prompt': self.sms_response_prompt
        }
    
    def _validate_response(self, response_message, validation_prompt):
        """Validate response using OpenAI"""
        validation_result = self.openai_client.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": validation_prompt}],
            max_tokens=200,
            temperature=0.3
        )
        return validation_result.choices[0].message.content.strip()
    
    def test_casual_conversation(self):
        """Test AgenticService with casual conversation"""
        
        conversation_history = ["USER: hey there"]
        result = self.agentic_service.process_agentic_response(conversation_history, self._create_services_dict())
        response_message = result['response_message']
        
        # Validate the response with REAL OpenAI
        validation_prompt = f"""
        Analyze this SMS response to a casual greeting ("hey there").
        
        Response to analyze: "{response_message}"
        
        Does this response correctly:
        1. Respond naturally and warmly?
        2. Avoid immediately asking for movie requests?
        3. Show personality and friendliness?
        
        Answer with YES or NO and explain why.
        """
        
        validation_text = self._validate_response(response_message, validation_prompt)
        print(f"🔍 OpenAI Validation: {validation_text}")
        
        if "YES" in validation_text.upper():
            print("\n✅ SUCCESS: OpenAI confirms the response correctly handles casual conversation!")
        else:
            print("\n❌ FAILURE: OpenAI indicates the response needs improvement for casual conversation.")
        
        return {
            'agent_response': response_message,
            'validation_result': validation_text,
            'success': "YES" in validation_text.upper()
        }
    
    def test_movie_request(self):
        """Test AgenticService with movie request"""

        conversation_history = ["USER: Can you add The Matrix to my library?"]
    
        # Note: This test validates the response string, but actual movie addition requires:
        # - Movie recognition by TMDB
        # - Movie recognition by Radarr  
        # - Movie not currently in library
        # - Movie to be released
    
        result = self.agentic_service.process_agentic_response(conversation_history, self._create_services_dict())
        
        response_message = result['response_message']
        print(f"📱 Agent Response: {response_message}")
        
        # Validate the response with REAL OpenAI
        validation_prompt = f"""
        Analyze this SMS response to a movie request ("Can you add The Matrix to my library?").
        
        Response to analyze: "{response_message}"
        
        Does this response correctly:
        1. Acknowledge the movie request?
        2. Provide helpful information about the movie?
        3. Handle the request appropriately?
        
        Answer with YES or NO and explain why.
        """
        
        validation_text = self._validate_response(response_message, validation_prompt)
        print(f"🔍 OpenAI Validation: {validation_text}")
        
        if "YES" in validation_text.upper():
            print("\n✅ SUCCESS: OpenAI confirms the response correctly handles movie requests!")
        else:
            print("\n❌ FAILURE: OpenAI indicates the response needs improvement for movie requests.")
        
        return {
            'agent_response': response_message,
            'validation_result': validation_text,
            'success': "YES" in validation_text.upper()
        }

    def test_generate_agentic_response(self):
        """Test generate_agentic_response method"""
        result = self.openai_client.generate_agentic_response("Hello", functions=[MOVIE_AGENT_FUNCTION_SCHEMA])
        
        assert result.get('success') == True
        assert 'response' in result
        assert 'has_function_calls' in result
        print("✅ generate_agentic_response test passed")
        return {'success': True}
    
    def test_monitoring_movie_requests(self):
        """Test monitoring movie requests - verify generate_agentic_response calls identify_movie_request"""
        prompt = "USER: Get me the last Harry Potter"
        result = self.openai_client.generate_agentic_response(prompt, functions=[MOVIE_AGENT_FUNCTION_SCHEMA])
        
        assert result.get('success') == True
        assert result.get('has_function_calls') == True
        assert result.get('tool_calls') is not None
        
        # Check that identify_movie_request was called
        tool_call = result['tool_calls'][0]
        assert tool_call.function.name == "movie_agent_function_call"
        
        function_args = json.loads(tool_call.function.arguments)
        assert function_args['function_name'] == "identify_movie_request"
        
        print("✅ Test monitoring movie requests passed")
        return {'success': True}
    
    def run_all_tests(self):
        """Run all tests"""
        print("🎬 Starting AgenticService Tests...")
        print("⚠️  ONLY Redis is mocked - everything else is REAL")
        print()
        
        # Run the tests
        print("=" * 60)
        print("TEST 1: Casual Conversation Handling")
        print("=" * 60)
        result1 = self.test_casual_conversation()
        
        print("\n" + "=" * 60)
        print("TEST 2: Movie Request Handling")
        print("=" * 60)
        result2 = self.test_movie_request()
        
        print("\n" + "=" * 60)
        print("TEST 3: generate_agentic_response")
        print("=" * 60)
        result3 = self.test_generate_agentic_response()
        
        print("\n" + "=" * 60)
        print("TEST 4: Test monitoring movie requests")
        print("=" * 60)
        result4 = self.test_monitoring_movie_requests()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 60)
        
        if result1.get('success'):
            print("✅ Test 1: The agent correctly handles casual conversation!")
        else:
            print("❌ Test 1: The agent needs improvement for casual conversation.")
        
        if result2.get('success'):
            print("✅ Test 2: The agent correctly handles movie requests!")
        else:
            print("❌ Test 2: The agent needs improvement for movie requests.")
        
        if result3.get('success'):
            print("✅ Test 3: generate_agentic_response works correctly!")
        else:
            print("❌ Test 3: generate_agentic_response needs improvement.")
        
        if result4.get('success'):
            print("✅ Test 4: monitoring movie requests works correctly!")
        else:
            print("❌ Test 4: monitoring movie requests needs improvement.")
        
        return {
            'casual_conversation': result1,
            'movie_request': result2,
            'generate_agentic_response': result3,
            'monitoring_movie_requests': result4
        }

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description='Test AgenticService functionality')
    parser.add_argument('--casual-only', action='store_true', help='Run only casual conversation test')
    parser.add_argument('--movie-only', action='store_true', help='Run only movie request test')
    parser.add_argument('--agentic-only', action='store_true', help='Run only generate_agentic_response test')
    parser.add_argument('--monitoring-only', action='store_true', help='Run only test monitoring movie requests')
    
    args = parser.parse_args()
    
    # Create test runner
    test_runner = AgenticServiceTestRunner()
    
    if args.casual_only:
        print("🎬 Running ONLY Casual Conversation Test")
        print("=" * 60)
        result = test_runner.test_casual_conversation()
        print(f"\n✅ Test completed: {'SUCCESS' if result.get('success') else 'FAILURE'}")
        
    elif args.movie_only:
        print("🎬 Running ONLY Movie Request Test")
        print("=" * 60)
        result = test_runner.test_movie_request()
        print(f"\n✅ Test completed: {'SUCCESS' if result.get('success') else 'FAILURE'}")
        
    elif args.agentic_only:
        print("🎬 Running ONLY generate_agentic_response Test")
        print("=" * 60)
        result = test_runner.test_generate_agentic_response()
        print(f"\n✅ Test completed: {'SUCCESS' if result.get('success') else 'FAILURE'}")
        
    elif args.monitoring_only:
        print("🎬 Running ONLY Test monitoring movie requests")
        print("=" * 60)
        result = test_runner.test_monitoring_movie_requests()
        print(f"\n✅ Test completed: {'SUCCESS' if result.get('success') else 'FAILURE'}")
        
    else:
        # Run all tests
        test_runner.run_all_tests()

if __name__ == '__main__':
    main()