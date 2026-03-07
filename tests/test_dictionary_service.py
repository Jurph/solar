import unittest
from pathlib import Path
from unittest.mock import patch

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

    # ------------------------------------------------------------------
    # get_random
    # ------------------------------------------------------------------

    def test_get_random_returns_string_from_category(self):
        """get_random returns a non-empty string from a valid category."""
        word = self.dictionary.get_random("ANIMAL")
        self.assertIsInstance(word, str)
        self.assertGreater(len(word), 0)
        self.assertIn(word, self.dictionary.wordlists["ANIMAL"])

    def test_get_random_unknown_category_raises(self):
        """get_random raises ValueError for an unknown category name."""
        with self.assertRaises(ValueError):
            self.dictionary.get_random("NONEXISTENT_CATEGORY")

    def test_get_random_empty_wordlist_raises(self):
        """get_random raises ValueError when the category's list is empty."""
        d = DictionaryService()
        d.wordlists["ANIMAL"] = []  # Force empty
        with self.assertRaises(ValueError):
            d.get_random("ANIMAL")

    # ------------------------------------------------------------------
    # get_multiple
    # ------------------------------------------------------------------

    def test_get_multiple_returns_requested_count(self):
        """get_multiple returns exactly `count` unique words when possible."""
        words = self.dictionary.get_multiple("COLOR", 3)
        self.assertEqual(len(words), 3)
        # All should be distinct (random.sample guarantees this)
        self.assertEqual(len(set(words)), 3)

    def test_get_multiple_clips_to_available_words(self):
        """get_multiple silently clips count to the size of the wordlist."""
        d = DictionaryService()
        d.wordlists["TINY"] = ["alpha", "beta"]
        # Requesting 10 from a 2-word list should return 2
        result = d.get_multiple("TINY", 10)
        self.assertEqual(len(result), 2)

    def test_get_multiple_unknown_category_raises(self):
        """get_multiple raises ValueError for an unknown category."""
        with self.assertRaises(ValueError):
            self.dictionary.get_multiple("DOES_NOT_EXIST", 3)

    def test_get_multiple_empty_wordlist_raises(self):
        """get_multiple raises ValueError when the category's list is empty."""
        d = DictionaryService()
        d.wordlists["COLOR"] = []
        with self.assertRaises(ValueError):
            d.get_multiple("COLOR", 1)

    # ------------------------------------------------------------------
    # _load_wordlist (FileNotFoundError path)
    # ------------------------------------------------------------------

    def test_load_wordlist_missing_file_returns_empty_list(self):
        """_load_wordlist returns [] and prints a warning when file is missing."""
        d = DictionaryService.__new__(DictionaryService)
        d.base_path = Path("/nonexistent/path")
        result = d._load_wordlist("no_such_file.txt")
        self.assertEqual(result, [])
