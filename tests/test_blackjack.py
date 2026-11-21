"""Offline regression tests: python -m unittest discover -s tests -v"""
import unittest

from bot.blackjack import Blackjack, hand_value


class BlackjackTests(unittest.TestCase):
    def setUp(self):
        self.game = Blackjack()

    def test_ace_scoring(self):
        self.assertEqual(hand_value([("A", "♠"), ("9", "♣")]), 20)
        self.assertEqual(hand_value([("A", "♠"), ("A", "♥"), ("9", "♣")]), 21)
        self.assertEqual(hand_value([("A", "♠"), ("A", "♥"), ("K", "♣")]), 12)

    def test_start_and_player_isolation(self):
        self.game._deck = lambda: [
            ("2", "♠"), ("4", "♠"), ("5", "♠"), ("6", "♠")
        ]
        self.assertIn("Type !hit", self.game.start("Alice"))
        self.assertIn("Type !hit", self.game.start("Bob"))
        self.assertEqual(len(self.game.games), 2)
        self.assertIn("active", self.game.start("ALICE"))
        self.assertIn("Your hand", self.game.hand("Alice"))
        self.assertIn("No active", self.game.hand("Charlie"))

    def test_natural_blackjack(self):
        # pop order: player first two, dealer next two
        self.game._deck = lambda: [
            ("3", "♣"), ("9", "♥"), ("K", "♠"), ("A", "♣")
        ]
        result = self.game.start("Alice")
        self.assertIn("Natural Blackjack", result)
        self.assertNotIn("alice", self.game.games)
        self.assertEqual(self.game.stats["alice"]["wins"], 1)

    def test_dealer_draws_and_stands(self):
        self.game._deck = lambda: [
            ("2", "♣"), ("6", "♣"), ("9", "♦"), ("K", "♥"),
            ("Q", "♠")
        ]
        self.game.start("Alice")
        result = self.game.stand("Alice")
        self.assertIn("Dealer:", result)
        self.assertIn("You win!", result)
        self.assertEqual(self.game.stats["alice"]["wins"], 1)

    def test_hit_bust(self):
        self.game._deck = lambda: [
            ("K", "♠"), ("8", "♣"), ("5", "♣"), ("6", "♣"),
            ("9", "♦")
        ]
        self.game.start("Alice")
        self.assertIn("Bust!", self.game.hit("Alice"))
        self.assertEqual(self.game.stats["alice"]["losses"], 1)

    def test_double_and_quit(self):
        self.game._deck = lambda: [
            ("3", "♣"), ("4", "♣"), ("7", "♥"), ("9", "♣"),
            ("8", "♣"), ("2", "♠")
        ]
        self.game.start("Alice")
        self.assertIn("Dealer:", self.game.double("Alice"))
        self.assertEqual(self.game.quit("Alice"), "No active Blackjack game. Type !blackjack to start.")
        self.game.start("Bob")
        self.assertIn("closed", self.game.quit("Bob"))
        self.assertEqual(sum(self.game.stats.get("bob", {}).values()), 0)

    def test_stats_and_leaderboard(self):
        self.game._record("alice", "wins")
        self.game._record("bob", "losses")
        self.assertIn("1 wins", self.game.player_stats("Alice"))
        self.assertIn("alice: 1 wins", self.game.leaderboard())


if __name__ == "__main__":
    unittest.main()
