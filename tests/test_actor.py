import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from mysite.universe.models.actor import Pilot, Controller, Satellite


class ActorModelTests(TestCase):
    """Test cases for the Actor model."""
    
    def test_pilot_creation(self):
        """Test that a Pilot can be created and has the correct name and prompt."""
        with patch("mysite.universe.models.actor.Pilot.generate_name", return_value="Captain Smith"):
            pilot = Pilot.create()
            self.assertIn("Captain", pilot.name)
            self.assertIn("You are a pilot named", pilot.build_prompt())

    def test_controller_creation(self):
        """Test that a Controller can be created and has no name and the correct prompt."""
        controller = Controller.create(location=MagicMock())
        self.assertEqual(controller.name, "")
        self.assertIn("You are a space traffic controller", controller.build_prompt())

    def test_satellite_creation(self):
        """Test that a Satellite can be created with a static name and prompt."""
        with patch("mysite.universe.models.actor.Satellite.generate_name", return_value="BB8"):
            satellite = Satellite.create(location=MagicMock())
            self.assertEqual(satellite.name, "BB8")
            self.assertIn("BEEP BOOP", satellite.build_prompt())


if __name__ == '__main__':
    unittest.main() 