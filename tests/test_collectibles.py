import random
import tempfile
import unittest
from pathlib import Path
from bot.collectibles import CollectibleDrops


class CollectibleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = [100.0]
        self.db = str(Path(self.temp.name) / "items.sqlite")
        self.drops = CollectibleDrops(
            database_path=self.db, rng=random.Random(1),
            clock=lambda: self.clock[0])

    def tearDown(self):
        self.temp.cleanup()

    def test_spawn_and_claim_once(self):
        message = self.drops.spawn()
        self.assertIn("!catch", message)
        self.assertIsNone(self.drops.spawn())
        self.assertIn("caught", self.drops.catch("Alice"))
        self.assertIn("No drop", self.drops.catch("Bob"))
        self.assertIn(" x1", self.drops.collection("Alice"))

    def test_persists_after_restart(self):
        self.drops.spawn()
        self.drops.catch("Alice")
        restarted = CollectibleDrops(database_path=self.db)
        self.assertIn(" x1", restarted.collection("alice"))

    def test_expires_after_ninety_seconds(self):
        self.drops.spawn()
        self.clock[0] += 91
        self.assertIn("escaped", self.drops.catch("Alice"))
        self.assertIn("empty", self.drops.collection("Alice"))

    def test_empty_collection(self):
        self.assertIn("empty", self.drops.collection("Unknown"))


if __name__ == "__main__":
    unittest.main()
