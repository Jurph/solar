import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from mysite.universe.models.actor import Pilot, Controller, Satellite
from mysite.universe.models.base import Location
from mysite.universe.models.scale import Scale


class ActorModelTests(TestCase):
    """Test cases for the Actor model."""
    
    def test_pilot_creation(self):
        """Test that a Pilot can be created and has the correct name and prompt."""
        with patch("mysite.universe.models.actor.Pilot.generate_name", return_value="Captain Smith"):
            pilot = Pilot.create()
            self.assertIn("Captain", pilot.name)
            self.assertIn("You are a pilot named", pilot.get_identity_prompt())

    def test_controller_creation(self):
        """Test Controller name generation in various scenarios."""
        # Test with location - should inherit location's name with suffix
        station = Location.objects.create(
            name="Mars Station",
            scale=Scale.STATION
        )
        controller = Controller.create(location=station)
        self.assertIn(station.name, controller.name)
        self.assertIn("You are a space traffic controller", controller.get_identity_prompt())
        station.delete()

        # Test with no location - should use default name
        controller_no_loc = Controller.create()
        self.assertEqual(controller_no_loc.name, "Space Traffic Control")
        
        # Test with explicit name - should preserve given name
        explicit_name = "Phobos Harbormaster"
        controller_named = Controller.create(name=explicit_name)
        self.assertEqual(controller_named.name, explicit_name)

    def test_satellite_creation(self):
        """Test that a Satellite can be created with a name and appropriate prompt."""
        with patch("mysite.universe.models.actor.Satellite.generate_name", return_value="Relay Alpha 1"):
            satellite = Satellite.create()
            self.assertEqual(satellite.name, "Relay Alpha 1")
            self.assertIn("You are an automated relay satellite", satellite.get_identity_prompt())


if __name__ == '__main__':
    unittest.main() 