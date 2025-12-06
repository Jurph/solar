"""Tests for LLM error handling and safety net functions."""
import json
from unittest.mock import Mock
from django.test import TestCase
from mysite.universe.schemas.dialogue_schema import DialogueMessage, Role
from mysite.universe.services.llm_service import LLMService


class LLMErrorHandlingTest(TestCase):
    """Test safety net functions for LLM response validation."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data that doesn't change between tests."""
        # Base valid DialogueMessage JSON structure for testing
        cls.base_message_json = {
            "role": "PILOT",
            "speaker_callsign": "STELLAR HORIZON",
            "recipient_callsign": "Mars Control",
            "message": "Mars Control, this is STELLAR HORIZON, requesting clearance.",
        }
    
    def setUp(self):
        """Set up for each test."""
        # Create a mock LLMService (we'll mock the chat() method)
        self.llm_service = Mock(spec=LLMService)
        self.llm_service.quiet_mode = True
        self.llm_service.temperature = 0.7
        self.llm_service.max_tokens = 512
        
        # Create a real LLMService instance for testing the actual detection logic
        # We'll use this to test the regex pattern directly
        self.real_llm = LLMService(quiet_mode=True)
    
    def _create_test_message_json(self, message_text: str) -> str:
        """Helper to create a test DialogueMessage JSON with custom message text."""
        test_json = self.base_message_json.copy()
        test_json["message"] = message_text
        return json.dumps(test_json)
    
    def _check_bad_message_detection(self, message_text: str) -> bool:
        """
        Helper to check if a message text would trigger bad message detection.
        
        Uses LLMService.is_invalid_dialogue_message() as the SINGLE SOURCE OF TRUTH.
        This ensures tests validate the exact same logic used in production code.
        """
        return LLMService.is_invalid_dialogue_message(message_text)
    
    def test_bad_message_content(self):
        """Test detection of bad message content patterns."""
        
        # Test cases: (message_text, should_trigger_detection, description)
        test_cases = [
            # Template variable patterns
            ("Mars Control, this is STELLAR HORIZON. ${current_situation.maneuver_type}", True, "Template variable with dot notation"),
            ("${ship_name}, requesting clearance", True, "Template variable at start"),
            ("Cleared for ${maneuver} maneuver", True, "Template variable in middle"),
            ("Cost is $100 per unit", False, "Dollar sign without braces (not template)"),
            
            # JSON fragment patterns
            ('Mars Control, { "role": "PILOT" }', True, "JSON fragment with role"),
            ('{ "message": "text" }', True, "JSON fragment with message"),
            ('{ "key": "value" }', True, "JSON fragment with key-value"),
            ('{hello}', False, "Braces without quote (not JSON fragment)"),
            ('{ "key": "value" }', True, "JSON fragment with whitespace"),
            
            # Error fallback patterns
            ("Mars Control, Error in communication", True, "Error fallback exact match"),
            ("error in communication", True, "Error fallback lowercase"),
            ("ERROR IN COMMUNICATION", True, "Error fallback uppercase"),
            ("Error in communications", True, "Error fallback plural"),
            ("Error in communication system", True, "Error fallback with extra words"),
            ("communication error", False, "Reversed word order (should not match)"),
            
            # Combined bad patterns
            ("${ship_name} { \"role\": \"PILOT\" }", True, "Template variable AND JSON fragment"),
            ("${maneuver} Error in communication", True, "Template variable AND error fallback"),
            
            # Good messages (should NOT trigger)
            ("Mars Control, this is STELLAR HORIZON, requesting clearance.", False, "Valid natural language"),
            ("STELLAR HORIZON, Mars Control. Cleared for maneuver.", False, "Valid controller response"),
            ("Roger, proceeding as directed.", False, "Valid acknowledgment"),
            ("", False, "Empty message"),
            ("   ", False, "Whitespace only"),
        ]
        
        for message_text, should_trigger, description in test_cases:
            with self.subTest(message=message_text, description=description):
                detected = self._check_bad_message_detection(message_text)
                self.assertEqual(
                    detected,
                    should_trigger,
                    f"Bad message detection failed for: '{message_text}' ({description}). "
                    f"Expected {'detected' if should_trigger else 'not detected'}, got {'detected' if detected else 'not detected'}."
                )
    
    def test_bad_message_detection_with_dialogue_message(self):
        """Test that bad message detection works when message is in a DialogueMessage object."""
        
        # Test that we can detect bad content in a DialogueMessage's message field
        # Use model_construct() to bypass validation for bad messages
        bad_messages = [
            ("${current_situation.maneuver_type}", "Template variable"),
            ('{ "role": "PILOT" }', "JSON fragment"),
            ("Error in communication", "Error fallback"),
        ]
        
        good_messages = [
            ("Mars Control, this is STELLAR HORIZON, requesting clearance.", "Valid request"),
            ("STELLAR HORIZON, Mars Control. Cleared for maneuver.", "Valid response"),
        ]
        
        # Test bad messages - use model_construct to bypass validation
        for message_text, description in bad_messages:
            with self.subTest(message=message_text, description=description):
                msg_obj = DialogueMessage.model_construct(
                    role=Role.PILOT,
                    speaker_callsign="STELLAR HORIZON",
                    recipient_callsign="Mars Control",
                    message=message_text
                )
                detected = self._check_bad_message_detection(msg_obj.message)
                self.assertTrue(
                    detected,
                    f"Should detect bad content in DialogueMessage: '{message_text}' ({description})"
                )
        
        # Test good messages - can use normal constructor
        for message_text, description in good_messages:
            with self.subTest(message=message_text, description=description):
                # Determine role based on message content
                is_controller = "STELLAR HORIZON, Mars Control" in message_text
                msg_obj = DialogueMessage(
                    role=Role.CONTROLLER if is_controller else Role.PILOT,
                    speaker_callsign="Mars Control" if is_controller else "STELLAR HORIZON",
                    recipient_callsign="STELLAR HORIZON" if is_controller else "Mars Control",
                    message=message_text
                )
                detected = self._check_bad_message_detection(msg_obj.message)
                self.assertFalse(
                    detected,
                    f"Should NOT detect bad content in valid DialogueMessage: '{message_text}' ({description})"
                )
    
    def test_bad_message_detection_with_json_string(self):
        """Test that bad message detection works when extracting from JSON string."""
        
        # Test cases where we parse JSON and then check the message field
        test_cases = [
            (self._create_test_message_json("${ship_name}, requesting clearance"), True, "Template variable in JSON"),
            (self._create_test_message_json('{ "role": "PILOT" }'), True, "JSON fragment in JSON"),
            (self._create_test_message_json("Error in communication"), True, "Error fallback in JSON"),
            (self._create_test_message_json("Mars Control, this is STELLAR HORIZON, requesting clearance."), False, "Valid message in JSON"),
        ]
        
        for json_str, should_trigger, description in test_cases:
            with self.subTest(description=description):
                try:
                    json_data = json.loads(json_str)
                    message_text = json_data.get("message", "")
                    detected = self._check_bad_message_detection(message_text)
                    self.assertEqual(
                        detected,
                        should_trigger,
                        f"Bad message detection failed for JSON: '{description}'. "
                        f"Expected {'detected' if should_trigger else 'not detected'}, got {'detected' if detected else 'not detected'}."
                    )
                except json.JSONDecodeError as e:
                    self.fail(f"Failed to parse test JSON for '{description}': {e}")
