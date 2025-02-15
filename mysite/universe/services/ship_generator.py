from typing import List
import random
from ..models.ship import Ship
from ..models.base import Location
from .dictionary import DictionaryService
from .cargo import CargoService

class ShipGenerator:
    """Service for generating ships with realistic names and properties"""
    
    NAME_TEMPLATES = [
        "{COLOR} {MATERIAL}",
        "{GIVEN} {SURNAME}'S {ANIMAL}",
        "{GIVEN}'S {MATERIAL} {ANIMAL}",
        "{CITY} {MATERIAL}",
        "{MATERIAL} {NUMBER}",
        "{ANIMAL} {NUMBER}",
        "{SURNAME} {NUMBER}",
        "{MATERIAL} {ANIMAL}",
        "STAR OF {CITY}",
        "{MATERIAL} STAR"
    ]
    
    def __init__(self):
        self.dictionary = DictionaryService()
        self.cargo_service = CargoService()
    
    def generate_name(self) -> str:
        """Generate a ship name using templates and wordlists"""
        template = random.choice(self.NAME_TEMPLATES)
        
        # Get words for each category in the template
        replacements = {}
        for category in self._get_template_categories(template):
            replacements[category] = self.dictionary.get_random(category)
            
        return template.format(**replacements)
    
    def _get_template_categories(self, template: str) -> List[str]:
        """Extract required categories from a template"""
        import re
        return re.findall(r'{(\w+)}', template)
    
    def generate_ship(self, location: Location) -> Ship:
        """Create a new ship at the specified location"""
        ship = Ship(
            name=self.generate_name(),
            current_location=location,
            size=random.choice(Ship.Size.choices)[0],
            status='DOCK',
            cargo=None
        )
        ship.save()
        return ship

def populate_location(self, location: Location, quantity: int) -> List[Ship]:
    """Generate multiple ships at a location"""
    return [self.generate_ship(location) for _ in range(quantity)]

def test_invalid_location_handling(self):
    """Verify ships can only be generated at valid locations"""
    # Try to create ship at non-station locations
    invalid_locations = [
        Location(name="Star", scale='SR'),
        Location(name="Planet", scale='PL'),
        Location(name="Galaxy", scale='GX')
    ]
    
    for location in invalid_locations:
        with self.assertRaises(ValueError):
            self.generator.generate_ship(location)