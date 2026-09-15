import unittest
from calculator import total


class TotalTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(0, total([]))

    def test_values(self):
        self.assertEqual(6, total([1, 2, 3]))
