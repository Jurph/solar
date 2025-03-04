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
            'GOODBYE': self._load_wordlist('goodbye.txt'),
            'HELLO': self._load_wordlist('hello.txt'),
            'MATERIAL': self._load_wordlist('materials.txt'),
            'NUMBER': self._load_wordlist('numbers.txt'),
            'SURNAME': self._load_wordlist('surnames.txt'),
            'TRAIT': self._load_wordlist('traits.txt')
        }
    
    def _load_wordlist(self, filename: str) -> List[str]:
        """Load a wordlist file into memory"""
        path = self.base_path / filename
        try:
            with open(path) as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Warning: Wordlist file {filename} not found at {path}")
            return []
    
    def get_random(self, category: str) -> str:
        """Get random word from a category"""
        if category not in self.wordlists or not self.wordlists[category]:
            raise ValueError(f"Category '{category}' not found or empty")
        return random.choice(self.wordlists[category])
    
    def get_multiple(self, category: str, count: int) -> List[str]:
        """Get multiple random words from a category"""
        if category not in self.wordlists or not self.wordlists[category]:
            raise ValueError(f"Category '{category}' not found or empty")
        
        available_words = self.wordlists[category]
        if count > len(available_words):
            count = len(available_words)
            
        return random.sample(available_words, count)