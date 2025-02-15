import unittest
from mysite.universe.services.dictionary import DictionaryService

class TestDictionaryService(unittest.TestCase):
    def setUp(self):
        self.dictionary = DictionaryService()
    
    def test_word_sanitization(self):
        """Verify wordlists are properly sanitized"""
        for category, words in self.dictionary.wordlists.items():
            for word in words:
                # No leading/trailing whitespace
                self.assertEqual(word, word.strip(), 
                    f"Found whitespace issues in {category}: '{word}'")
                # No empty strings
                self.assertGreater(len(word), 0, 
                    f"Found empty string in {category}")
                # No duplicates in list
                self.assertEqual(
                    words.count(word), 1,
                    f"Found duplicate '{word}' in {category}"
                )
