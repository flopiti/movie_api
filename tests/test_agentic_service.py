import os
import sys
import argparse
from dotenv import load_dotenv
from unittest.mock import MagicMock
import json 
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
        print("result line 105")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        function_results = result.get('function_results', [])
        
        # Check: exactly 2 functions, identify_movie_request then send_notification
        success = (len(function_results) == 2 and 
                  function_results[0]['function_name'] == 'identify_movie_request' and
                  not function_results[0]['result'].get('success', True) and
                  function_results[1]['function_name'] == 'send_notification')
        
        return {
            'agent_response': result.get('response_message', ''),
            'success': success
        }
    

    def test_casual_conversation_2( self):
        """Test AgenticService with casual conversation"""
        
        conversation_history = ["USER: yoyo"]
        result = self.agentic_service.process_agentic_response(conversation_history, self._create_services_dict())
        print("result line 105")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        function_results = result.get('function_results', [])
        
        # Check: exactly 2 functions, identify_movie_request then send_notification
        success = (len(function_results) == 2 and 
                  function_results[0]['function_name'] == 'identify_movie_request' and
                  not function_results[0]['result'].get('success', True) and
                  function_results[1]['function_name'] == 'send_notification')
        
        return {
            'agent_response': result.get('response_message', ''),
            'success': success
        }
    

    def test_jumanji_download_request(self):
        """Test AgenticService with Jumanji download request"""
        
        conversation_history = ["USER: yo","SYSTEM: yo", "USER: can you add the old Jumanji"]
        result = self.agentic_service.process_agentic_response(conversation_history, self._create_services_dict())


        print("result line 124")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        # Extract function results
        function_results = result.get('function_results', [])
        
        # Expected function names
        expected_functions = [
            'identify_movie_request',
            'check_movie_library_status', 
            'check_radarr_status',
            'send_notification'
        ]
        
        # Validate function results
        success = True
        validation_errors = []
        
        # Check that all four functions are present
        function_names = [fr['function_name'] for fr in function_results]
        for expected_func in expected_functions:
            if expected_func not in function_names:
                validation_errors.append(f"Missing function: {expected_func}")
                success = False
        
        # Validate each function result
        for fr in function_results:
            func_name = fr['function_name']
            func_result = fr['result']
            
            if not func_result.get('success', False):
                validation_errors.append(f"Function {func_name} did not succeed")
                success = False
            
            # Check specific requirements for each function
            if func_name == 'identify_movie_request':
                if func_result.get('movie_name') != 'Jumanji':
                    validation_errors.append(f"identify_movie_request: wrong movie_name, got {func_result.get('movie_name')}")
                    success = False
                    
            elif func_name == 'check_movie_library_status':
                if func_result.get('movie_name') != 'Jumanji':
                    validation_errors.append(f"check_movie_library_status: wrong movie_name, got {func_result.get('movie_name')}")
                    success = False
                    
            elif func_name == 'check_radarr_status':
                if func_result.get('movie_title') != 'Jumanji':
                    validation_errors.append(f"check_radarr_status: wrong movie_title, got {func_result.get('movie_title')}")
                    success = False
                if not func_result.get('is_downloaded', False):
                    validation_errors.append(f"check_radarr_status: is_downloaded should be True")
                    success = False
                    
            elif func_name == 'send_notification':
                if func_result.get('message_type') != 'movie_already_downloaded':
                    validation_errors.append(f"send_notification: wrong message_type, got {func_result.get('message_type')}")
                    success = False
        
        # Print validation results
        if success:
            print("\n✅ SUCCESS: Jumanji download request handled correctly!")
            print("  - All four required functions executed successfully")
            print("  - Movie title correctly identified as 'Jumanji'")
            print("  - Movie is marked as downloaded")
            print("  - Notification sent with correct message type")
        else:
            print("\n❌ FAILURE: Jumanji download request not handled correctly.")
            for error in validation_errors:
                print(f"  - {error}")
        
        return {
            'agent_response': result.get('response_message', ''),
            'function_results': function_results,
            'success': success,
            'validation_errors': validation_errors
        }
    
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
        print("TEST 2: Jumanji Download Request")
        print("=" * 60)
        result2 = self.test_jumanji_download_request()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 60)
        
        if result1.get('success'):
            print("✅ Test 1: The agent correctly handles casual conversation!")
        else:
            print("❌ Test 1: The agent needs improvement for casual conversation.")
        
        if result2.get('success'):
            print("✅ Test 2: The agent correctly handles Jumanji download request!")
        else:
            print("❌ Test 2: The agent needs improvement for Jumanji download request.")
        
        return {
            'casual_conversation': result1,
            'jumanji_download': result2
        }

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description='Test AgenticService functionality')
    parser.add_argument('--casual-only', action='store_true', help='Run only casual conversation test')
    parser.add_argument('--jumanji-only', action='store_true', help='Run only Jumanji download test')
    
    args = parser.parse_args()
    
    # Create test runner
    test_runner = AgenticServiceTestRunner()
    
    if args.casual_only:
        print("🎬 Running ONLY Casual Conversation Test")
        print("=" * 60)
        result1 = test_runner.test_casual_conversation()
        result2 = test_runner.test_casual_conversation_2()


        print(f"Casual Conversation 1: {'SUCCESS' if result1.get('success') else 'FAILURE'}")        
        print(f"Casual Conversation 2: {'SUCCESS' if result2.get('success') else 'FAILURE'}")        
        
    elif args.jumanji_only:
        print("🎬 Running ONLY Jumanji Download Test")
        print("=" * 60)
        result = test_runner.test_jumanji_download_request()
        print(f"\n✅ Test completed: {'SUCCESS' if result.get('success') else 'FAILURE'}")
        
    else:
        # Run all tests
        test_runner.run_all_tests()

if __name__ == '__main__':
    main()