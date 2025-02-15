from typing import List, Dict
from pathlib import Path
import random

class DictionaryService:
    """Central service for accessing wordlists used in procedural generation"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent.parent / 'wordlists'
        self.wordlists: Dict[str, List[str]] = {
            'ANIMAL': self._load_wordlist('animals.txt'),
            'AVATAR': self._load_wordlist('avatars.txt'),
            'CITY': self._load_wordlist('cities.txt'),
            'COLOR': self._load_wordlist('colors.txt'),
            'ELEMENT': self._load_wordlist('elements.txt'),
            'GIVEN': self._load_wordlist('givennames.txt'),
            'MATERIAL': self._load_wordlist('materials.txt'),
            'NUMBER': self._load_wordlist('numbers.txt'),
            'SURNAME': self._load_wordlist('surnames.txt')
        }
    
    def _load_wordlist(self, filename: str) -> List[str]:
        """Load a wordlist file into memory"""
        path = self.base_path / filename
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]
    
    def get_random(self, category: str) -> str:
        """Get random word from a category"""
        return random.choice(self.wordlists[category])
    
    def get_multiple(self, category: str, count: int) -> List[str]:
        """Get multiple random words from a category"""
        return random.sample(self.wordlists[category], count)