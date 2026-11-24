"""Tests for persistent CrowCoins and Blackjack stake settlement."""
import tempfile
import unittest
from pathlib import Path

from bot.coins import CoinWallet, STARTING_COINS, HOURLY_COINS
from bot.blackjack import Blackjack


class CoinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1000.0]
        self.path = Path(self.tmp.name) / "coins.json"
        self.wallet = CoinWallet(path=self.path, clock=lambda: self.now[0])

    def test_starter_balance_and_persistence(self):
        self.assertEqual(self.wallet.balance("ALICE"), STARTING_COINS)
        self.wallet.withdraw("Alice", 100)
        fresh = CoinWallet(path=self.path, clock=lambda: self.now[0])
        self.assertEqual(fresh.balance("alice"), STARTING_COINS - 100)

    def test_hourly_refill_catches_up_on_command(self):
        self.wallet.balance("alice")
        self.now[0] += 3599
        self.assertEqual(self.wallet.balance("alice"), STARTING_COINS)
        self.now[0] += 1
        self.assertEqual(self.wallet.balance("alice"), STARTING_COINS + HOURLY_COINS)
        self.now[0] += 7200
        self.assertEqual(self.wallet.balance("alice"), STARTING_COINS + 3 * HOURLY_COINS)
        self.assertIn("200 every hour", self.wallet.status("alice"))

    def test_insufficient_funds_and_leaderboard(self):
        self.assertFalse(self.wallet.withdraw("alice", STARTING_COINS + 1))
        self.assertTrue(self.wallet.withdraw("alice", 100))
        self.wallet.deposit("Bob", 500)
        self.assertIn("Bob", self.wallet.leaderboard().splitlines()[1])

    def test_natural_blackjack_payout(self):
        game = Blackjack(wallet=self.wallet)
        game._deck = lambda: [("3", "♣"), ("9", "♥"), ("K", "♠"), ("A", "♣")]
        self.assertIn("Natural Blackjack", game.start("Alice", bet=100))
        self.assertEqual(self.wallet.balance("Alice"), STARTING_COINS + 150)

    def test_loss_payout_and_refund_on_quit(self):
        game = Blackjack(wallet=self.wallet)
        game._deck = lambda: [("K", "♠"), ("8", "♣"), ("5", "♣"), ("6", "♣"), ("9", "♦")]
        game.start("Alice", bet=100)
        self.assertEqual(self.wallet.balance("Alice"), STARTING_COINS - 100)
        self.assertIn("Bust!", game.hit("Alice"))
        self.assertEqual(self.wallet.balance("Alice"), STARTING_COINS - 100)
        game.start("Alice", bet=50)
        self.assertIn("refunded", game.quit("Alice"))
        self.assertEqual(self.wallet.balance("Alice"), STARTING_COINS - 100)

    def test_double_requires_funds_and_wager_limit(self):
        game = Blackjack(wallet=self.wallet)
        game._deck = lambda: [
            ("3", "♣"), ("4", "♣"), ("7", "♥"), ("9", "♣"),
            ("8", "♣"), ("2", "♠")
        ]
        self.assertIn("Bet must", game.start("Alice", bet=-1))
        game.start("Alice", bet=800)
        self.assertIn("Not enough", game.double("Alice"))
        self.assertEqual(self.wallet.balance("Alice"), 200)
        self.assertEqual(len(game.games["alice"]["player"]), 2)
        self.assertIn("refunded", game.quit("Alice"))
        self.assertEqual(self.wallet.balance("Alice"), 1000)


if __name__ == "__main__":
    unittest.main()
