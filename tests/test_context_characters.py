import unittest

from core.context_characters import normalize_characters


class TestContextCharacters(unittest.TestCase):
    def test_normalize_characters_skips_invalid_items(self):
        characters = normalize_characters(
            [
                {
                    "id": "char_001",
                    "name": "Lead",
                    "role": "Lead",
                    "description": "desc",
                    "traits": ["calm"],
                },
                {"id": "char_002", "name": "Broken"},
            ]
        )

        self.assertEqual(len(characters), 1)
        self.assertEqual(characters[0]["id"], "char_001")

    def test_normalize_characters_discards_blank_traits(self):
        characters = normalize_characters(
            [
                {
                    "id": "char_001",
                    "name": "Lead",
                    "role": "Lead",
                    "description": "desc",
                    "traits": ["calm", "", None],
                }
            ]
        )

        self.assertEqual(characters[0]["traits"], ["calm"])


if __name__ == "__main__":
    unittest.main()
