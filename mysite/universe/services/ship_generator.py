from typing import List, Optional
import random
from mysite.universe.models.ship import Ship
from mysite.universe.models import Location
from mysite.universe.services.dictionary import DictionaryService
from mysite.universe.services.cargo_server import CargoService
from mysite.universe.services.location_generator import LocationGenerator

class ShipGenerator:
    """Service for generating ships with realistic names and properties"""
    
    NAME_TEMPLATES = [
        "{COLOR} {MATERIAL}",
        "{GIVEN} {SURNAME}'s {ANIMAL}",
        "{GIVEN}'s {MATERIAL} {ANIMAL}",
        "{CITY} {MATERIAL}",
        "{MATERIAL} {NUMBER}",
        "{ANIMAL} {NUMBER}",
        "{SURNAME} {NUMBER}",
        "{MATERIAL} {ANIMAL}",
        "The {AVATAR} of {CITY}",
        "{MATERIAL} {AVATAR}",
        "{COLOR} {AVATAR}",
        "{AVATAR} {NUMBER}"
    ]
    
    def __init__(self):
        self.dictionary = DictionaryService()
        self.cargo_service = CargoService()
        self.location_generator = LocationGenerator()
    
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
    
    def generate_ship(self, location: Optional[Location] = None) -> Ship:
        """Create a new ship at the specified location, or a random station if not provided."""
        if location is None:
            location = self.location_generator.get_random_station()
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