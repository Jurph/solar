import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from mysite.universe.models.actor import Actor, Pilot, Controller
from mysite.universe.services.dictionary import DictionaryService


class ActorModelTests(TestCase):
    """Test cases for the Actor model."""
    
    def test_traits_list_property(self):
        """Test that traits_list property correctly converts between string and list."""
        actor = Actor(name="Test Actor", role=Actor.Role.PILOT)
        
        # Test setting traits_list
        test_traits = ["cautious", "experienced", "by-the-book"]
        actor.traits_list = test_traits
        self.assertEqual(actor.traits, "cautious, experienced, by-the-book")
        
        # Test getting traits_list
        self.assertEqual(actor.traits_list, test_traits)
        
        # Test empty traits
        actor.traits = ""
        self.assertEqual(actor.traits_list, [])
    
    def test_build_prompt(self):
        """Test that build_prompt correctly constructs a prompt string."""
        # Test pilot prompt
        pilot = Actor(
            name="Captain Smith",
            role=Actor.Role.PILOT,
            traits="cautious, methodical",
            years_of_experience=15
        )
        prompt = pilot.build_prompt()
        
        self.assertIn("You are a pilot named Captain Smith", prompt)
        self.assertIn("You are cautious, methodical", prompt)
        self.assertIn("You have 15 years of experience", prompt)
        self.assertIn("You follow the rules of radio communication", prompt)
        
        # Test controller prompt
        controller = Actor(
            name="John Doe",
            role=Actor.Role.CONTROLLER,
            traits="stern, efficient",
            years_of_experience=20
        )
        prompt = controller.build_prompt()
        
        self.assertIn("You are a space traffic controller named John Doe", prompt)
        self.assertIn("You are stern, efficient", prompt)
        self.assertIn("You have 20 years of experience", prompt)
    
    @patch("mysite.universe.services.dictionary.DictionaryService")
    def test_generate_name(self, MockDictionaryService):
        """Test that generate_name correctly uses the dictionary service."""
        mock_instance = MockDictionaryService.return_value
        mock_instance.get_random.side_effect = lambda category: {
            'GIVEN': 'Jane',
            'SURNAME': 'Smith'
        }[category]
        
        # Test controller name (full name)
        name = Actor.generate_name(Actor.Role.CONTROLLER)
        self.assertEqual(name, "Jane Smith")
        
        # Test pilot name (surname only with title)
        name = Actor.generate_name(Actor.Role.PILOT)
        self.assertEqual(name, "Captain Smith")
        
        # Verify the dictionary service was called correctly
        mock_instance.get_random.assert_any_call('GIVEN')
        mock_instance.get_random.assert_any_call('SURNAME')
    
    @patch("mysite.universe.services.dictionary.DictionaryService")
    def test_generate_traits(self, MockDictionaryService):
        """Test that generate_traits correctly uses the dictionary service."""
        mock_instance = MockDictionaryService.return_value
        mock_instance.get_multiple.return_value = ["cautious", "methodical"]
        
        traits = Actor.generate_traits()
        self.assertEqual(traits, ["cautious", "methodical"])
        
        # Verify the dictionary service was called correctly
        mock_instance.get_multiple.assert_called_once_with('TRAIT', 2)
    
    def test_generate_years_experience(self):
        """Test that generate_years_experience returns a valid value."""
        with patch("random.randint", return_value=15):
            years = Actor.generate_years_experience()
        
        self.assertEqual(years, 15)
    
    @patch("mysite.universe.models.actor.Actor.generate_name")
    @patch("mysite.universe.models.actor.Actor.generate_traits")
    @patch("mysite.universe.models.actor.Actor.generate_years_experience")
    @patch("mysite.universe.models.actor.Actor.build_prompt")
    def test_create_with_defaults(self, mock_build_prompt, mock_generate_years, 
                                 mock_generate_traits, mock_generate_name):
        """Test that create correctly generates default values."""
        # Setup mocks
        mock_generate_name.return_value = "Captain Smith"
        mock_generate_traits.return_value = ["cautious", "methodical"]
        mock_generate_years.return_value = 15
        mock_build_prompt.return_value = "Test prompt"
        
        # Create actor with defaults
        with patch("mysite.universe.models.actor.Actor.save"):
            actor = Actor.create(role=Actor.Role.PILOT)
        
        # Verify defaults were used
        self.assertEqual(actor.name, "Captain Smith")
        self.assertEqual(actor.traits_list, ["cautious", "methodical"])
        self.assertEqual(actor.years_of_experience, 15)
        
        # Verify methods were called
        mock_generate_name.assert_called_once_with(Actor.Role.PILOT)
        mock_generate_traits.assert_called_once()
        mock_generate_years.assert_called_once()
        mock_build_prompt.assert_called_once()
    
    @patch("mysite.universe.models.actor.Actor.create")
    def test_pilot_create(self, mock_actor_create):
        """Test that Pilot.create correctly sets the role and ship."""
        # Setup mock
        mock_actor = MagicMock()
        mock_actor_create.return_value = mock_actor
        
        # Create a mock ship
        mock_ship = MagicMock()
        
        # Create pilot
        pilot = Pilot.create(ship=mock_ship, name="Captain Smith")
        
        # Verify Actor.create was called with the correct role
        mock_actor_create.assert_called_once_with(role=Actor.Role.PILOT, name="Captain Smith")
        
        # Verify ship was set
        self.assertEqual(pilot.ship, mock_ship)
    
    @patch("mysite.universe.models.actor.Actor.create")
    def test_controller_create(self, mock_actor_create):
        """Test that Controller.create correctly sets the role and location."""
        # Setup mock
        mock_actor = MagicMock()
        mock_actor_create.return_value = mock_actor
        
        # Create a mock location
        mock_location = MagicMock()
        
        # Create controller
        controller = Controller.create(location=mock_location, name="John Doe")
        
        # Verify Actor.create was called with the correct role
        mock_actor_create.assert_called_once_with(role=Actor.Role.CONTROLLER, name="John Doe")
        
        # Verify location was set
        self.assertEqual(controller.location, mock_location)


if __name__ == '__main__':
    unittest.main() 