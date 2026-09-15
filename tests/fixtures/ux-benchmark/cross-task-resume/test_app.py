import unittest
from app import parse_count


class CountTests(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(12, parse_count("12"))

    def test_negative_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_count("-2")
