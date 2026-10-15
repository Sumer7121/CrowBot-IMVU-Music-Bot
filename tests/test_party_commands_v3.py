"""CrowBot V3 public party commands, including !tod <name>."""
import unittest
from unittest.mock import MagicMock, patch

from bot.commands import CommandHandler


class PartyCommandTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch("bot.commands.MusicResolver"),
            patch("bot.commands.YouTubeOwnedProvider"),
            patch("bot.commands.CollectibleDrops"),
        ]
        for p in self.patches:
            p.start()
        self.handler = CommandHandler(MagicMock(), MagicMock())

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_tod_targets_unseen_username_as_truth(self):
        with patch("bot.commands.random.choice", return_value=True):
            response = self.handler.handle("!tod @NewVisitor", "Host")
        self.assertIn("TRUTH", response)
        self.assertIn("👤 NewVisitor", response)

    def test_tod_targets_multiple_word_name_as_dare(self):
        with patch("bot.commands.random.choice", return_value=False):
            response = self.handler.handle("!tod Mary Jane", "Host")
        self.assertIn("DARE", response)
        self.assertIn("👤 Mary Jane", response)

    def test_tod_with_no_name_targets_sender(self):
        response = self.handler.handle("!tod", "Host")
        self.assertIn("👤 Host", response)

    def test_truth_and_dare_allow_direct_names(self):
        self.assertIn("👤 NewVisitor", self.handler.handle("!truth NewVisitor", "Host"))
        self.assertIn("👤 NewVisitor", self.handler.handle("!dare NewVisitor", "Host"))

    def test_new_game_commands(self):
        commands = (
            ("!wyr", "WOULD YOU RATHER"),
            ("!nhie", "NEVER HAVE I EVER"),
            ("!8ball will it rain", "CrowBot says"),
            ("!riddle", "RIDDLE"),
            ("!duel Bob", "DUEL"),
        )
        for command, expected in commands:
            with self.subTest(command=command):
                self.assertIn(expected, self.handler.handle(command, "Alice"))

    def test_riddle_answer_via_ra(self):
        self.handler.party_games.riddle = {"question": "Test?", "answer": "clock"}
        self.assertIn("solved it", self.handler.handle("!ra clock", "Alice"))

    def test_party_help_documents_new_commands(self):
        text = self.handler.handle("!h f", "Alice")
        for command in ("!tod", "!wyr", "!nhie", "!8ball"):
            self.assertIn(command, text)
        games = self.handler.handle("!h g", "Alice")
        for command in ("!riddle", "!duel", "!quiz"):
            self.assertIn(command, games)


if __name__ == "__main__":
    unittest.main()
