import unittest
from catalog import Catalog


class CatalogTests(unittest.TestCase):
    def test_lookup_uses_the_same_normalization(self):
        catalog = Catalog()
        catalog.add("  Hello   World ", 7)
        self.assertEqual(7, catalog.find("hello world"))

    def test_duplicates_remain_errors(self):
        catalog = Catalog()
        catalog.add("one", 1)
        with self.assertRaises(ValueError):
            catalog.add("one", 2)
