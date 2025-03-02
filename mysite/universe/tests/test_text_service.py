import unittest
import os
import pytest
from ..services.text_server import TextService

class TestTextService(unittest.TestCase):
    """Test cases for the TextService class."""
    
    @pytest.mark.slow  # Mark as slow test since it loads a large model
    def test_simple_prompt_response(self):
        """Test that the service can respond to a simple prompt requesting a specific answer."""
        # Skip test if model file doesn't exist
        model_path = os.environ.get("TEST_MODEL_PATH", "mysite/universe/models/language/Qwen2.5/checkpoints/qwen2.5-0.5b-instruct-q4_0.gguf")
        if not os.path.exists(model_path):
            self.skipTest(f"Model file not found at {model_path}. Set TEST_MODEL_PATH env var to run this test.")
        
        # Initialize the service with the test model
        service = TextService(model_path=model_path)
        
        # Create a simple prompt that asks for a specific response
        prompt = "Please respond with the word 'YES' and only the word 'YES'. Do not include any other text."
        
        # Generate the response
        response = service.generate_text(prompt, temperature=0.1)  # Low temperature for more deterministic output
        
        # Check that the response contains "YES"
        self.assertIn("YES", response, f"Response should contain 'YES' but got: {response}")
        
        # Print the full response for debugging
        print(f"Full response: {response}")
        
        # Check that the response is reasonably brief (allowing for some extra tokens)
        words = response.split()
        self.assertLessEqual(len(words), 5, f"Response should be brief but contained {len(words)} words")

    @pytest.mark.slow
    def test_controller_dialogue(self):
        """Test that the service can generate appropriate controller dialogue."""
        # Skip test if model file doesn't exist
        model_path = os.environ.get("TEST_MODEL_PATH", "mysite/universe/models/language/Qwen2.5/checkpoints/qwen2.5-0.5b-instruct-q4_0.gguf")
        if not os.path.exists(model_path):
            self.skipTest(f"Model file not found at {model_path}. Set TEST_MODEL_PATH env var to run this test.")
        
        # Initialize the service
        service = TextService(model_path=model_path)
        
        # Test context
        context = 'MOONBAT PRESTON: "Ceres Control, this is MOONBAT PRESTON, requesting permission to dock."'
        
        # Generate dialogue
        response = service.generate_controller_dialogue(
            controller_name="CERES CONTROL",
            ship_name="MOONBAT PRESTON",
            context=context
        )
        
        # Check that response follows the correct format
        self.assertIn("MOONBAT PRESTON", response, "Response should address the ship")
        self.assertIn("CERES CONTROL", response, "Response should include controller callsign")
        
        print(f"Controller dialogue: {response}") 