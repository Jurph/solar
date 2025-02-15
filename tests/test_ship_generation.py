import unittest
from mysite.universe.services.ship_generator import ShipGenerator
from mysite.universe.services.dictionary import DictionaryService
from mysite.universe.models import Ship, Location

class TestShipGeneration(unittest.TestCase):
    def setUp(self):
        self.generator = ShipGenerator()
        self.dictionary = DictionaryService()
        
    def test_name_uniqueness(self):
        """Verify we don't generate duplicate names in a reasonable sample"""
        station = Location(name="Test Station", scale='SS')
        names = set()
        for _ in range(100):
            ship = self.generator.generate_ship(station)
            names.add(ship.name)
        # Should have close to 100 unique names
        self.assertGreater(len(names), 90, "Generated too many duplicate names")
    
    def test_name_sanitization(self):
        """Verify generated names don't contain problematic characters"""
        station = Location(name="Test Station", scale='SS')
        for _ in range(50):
            ship = self.generator.generate_ship(station)
            self.assertNotIn('{', ship.name, "Template markers found in final name")
            self.assertNotIn('}', ship.name, "Template markers found in final name")
            self.assertNotIn('  ', ship.name, "Double spaces in name")
            self.assertLess(len(ship.name), 100, "Name exceeds model field length")