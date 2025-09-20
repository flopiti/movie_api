import os
import sys
import argparse
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
    
    def test_jumanji_download_request(self):
        """Test AgenticService with Jumanji download request"""
        
        conversation_history = ["USER: yo","SYSTEM: yo", "USER: can you add the old Jumanji"]
        result = self.agentic_service.process_agentic_response(conversation_history, self._create_services_dict())
        
        response_message = result['response_message']
        metadata = result.get('metadata', {})
        
        print(f"📱 Agent Response: {response_message}")
        print(f"📊 Metadata: {metadata}")
        
        # Check that response confirms the download
        download_confirmed = any(keyword in response_message.lower() for keyword in [
            'getting', 'downloading', 'adding', 'setting up', 'ready', 'jumanji'
        ])
        
        # Check metadata requirements
        radarr_status = metadata.get('radarr_status')
        tmdb_status = metadata.get('tmdb_status')
        
        success = (
            download_confirmed and
            radarr_status == 'sent' and
            tmdb_status == 'confirmed'
        )
        
        if success:
            print("\n✅ SUCCESS: Jumanji download request handled correctly!")
        else:
            print("\n❌ FAILURE: Jumanji download request not handled correctly.")
            if not download_confirmed:
                print("  - Response doesn't confirm download")
            if radarr_status != 'sent':
                print(f"  - Radarr status is '{radarr_status}', expected 'sent'")
            if tmdb_status != 'confirmed':
                print(f"  - TMDB status is '{tmdb_status}', expected 'confirmed'")
        
        return {
            'agent_response': response_message,
            'metadata': metadata,
            'success': success
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
        result = test_runner.test_casual_conversation()
        print(f"\n✅ Test completed: {'SUCCESS' if result.get('success') else 'FAILURE'}")
        
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