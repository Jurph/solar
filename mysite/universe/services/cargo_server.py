from typing import Optional
import random
from ..models.ship import Ship
from ..models.base import Location
from .dictionary import DictionaryService

class CargoService:
    """Service for determining appropriate cargo types"""
    
    def __init__(self):
        self.dictionary = DictionaryService()
    
    CARGO_TYPES = {
        Ship.Size.SMALL: [
            'Luxury Goods',
            'Medical Supplies',
            'Diplomatic Mail',
            'Passengers',
            'VIP Transport',
            'Scientific Equipment',
            'High-Value Data',
        ],
        Ship.Size.MEDIUM: [
            'Mixed Cargo',
            'Bulk Food',
            'Industrial Parts',
            'Raw Materials',
            'Processed Goods',
            'Construction Materials',
            'Bulk {ELEMENT}',  # Will be formatted with random element
        ],
        Ship.Size.LARGE: [
            'Ore',
            'Fuel',
            'Water Ice',
            'Heavy Equipment',
            'Colony Supplies',
            'Bulk {ELEMENT}',
        ]
    }
    
    def generate_cargo(self, ship: Ship, departure: Optional[Location] = None) -> str:
        """Generate appropriate cargo based on ship size and optionally location"""
        cargo_type = random.choice(self.CARGO_TYPES[ship.size])
        
        # Handle template strings that need formatting
        if '{ELEMENT}' in cargo_type:
            element = self.dictionary.get_random('ELEMENT')
            return cargo_type.format(ELEMENT = element)
            
        return cargo_type