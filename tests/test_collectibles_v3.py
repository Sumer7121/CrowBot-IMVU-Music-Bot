"""CrowBot V3 pets-only rarity and persistence checks."""
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from bot.collectibles import CATALOG, CATALOG_BY_NAME, RARITY_WEIGHT, CollectibleDrops


class PetCatalogTests(unittest.TestCase):
    def test_catalog_contains_100_plus_unique_cats_and_dogs(self):
        self.assertGreaterEqual(len(CATALOG), 100)
        self.assertEqual(len(CATALOG_BY_NAME), len(CATALOG))
        self.assertEqual({item[0] for item in CATALOG}, {"cat", "dog"})
        self.assertEqual({item[3] for item in CATALOG}, set(RARITY_WEIGHT))
        self.assertEqual(sum(RARITY_WEIGHT.values()), 100)

    def test_rarity_visible_in_collection_and_legacy_anime_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "pets.sqlite")
            drops = CollectibleDrops(database_path=db, rng=random.Random(1))
            with sqlite3.connect(db) as conn:
                conn.executemany(
                    "INSERT INTO collections (player, item, quantity) VALUES (?, ?, ?)",
                    [
                        ("alice", "Stardust", 1),
                        ("alice", "Thunderpaw", 2),
                        ("alice", "Kira the Blade", 5),
                    ],
                )
            response = drops.collection("Alice")
            self.assertIn("Stardust [EPIC] x1", response)
            self.assertIn("Thunderpaw [EPIC] x2", response)
            self.assertNotIn("Kira", response)

    def test_drop_species_is_never_anime(self):
        with tempfile.TemporaryDirectory() as tmp:
            drops = CollectibleDrops(
                database_path=str(Path(tmp) / "pets.sqlite"),
                rng=random.Random(7),
            )
            for _ in range(20):
                drops.spawn()
                self.assertIn(drops.active[0][0], ("cat", "dog"))
                drops.catch("Alice")


if __name__ == "__main__":
    unittest.main()
