"""CrowBot V3 public party commands, including !tod <name>."""
import unittest
from unittest.mock import MagicMock, patch

from bot.commands import CommandHandler


class PartyCommandTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch("bot.commands.MusicResolver"),
            patch("bot.commands.get_shared_youtube_provider"),
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

    def test_artist_autoplay_and_music_language_commands(self):
        dj = MagicMock()
        dj.label = "OFF · Any language"
        dj.language = ""
        dj.enabled = False
        dj.set_artist.return_value = "ARTIST DJ: Arijit Singh · Hindi"
        dj.set_autoplay.return_value = "YOUTUBE AUTOPLAY · Hindi"
        dj.set_language.return_value = "OFF · Hindi"
        self.handler.dj_controller = dj
        self.assertIn(
            "ARTIST DJ: Arijit Singh",
            self.handler.handle("!dj Arijit Singh", "Alice"),
        )
        dj.set_artist.assert_called_once_with("Arijit Singh")
        self.handler.handle("!language Hindi", "Alice")
        dj.set_language.assert_called_once_with("Hindi")
        self.handler.handle("!autoplay on", "Alice")
        dj.set_autoplay.assert_called_with(True)
        self.handler.handle("!autoplay off", "Alice")
        dj.set_autoplay.assert_called_with(False)
        self.handler.handle("!dj off", "Alice")
        dj.off.assert_called_once()

    def test_manual_petdrop_spawns_and_has_room_cooldown(self):
        self.handler.collectibles.active = None
        self.handler.collectibles.expired.return_value = False
        self.handler.collectibles.spawn.return_value = (
            "✨ WILD CAT DROP! 🐱 Mochi [COMMON] Type !catch!"
        )
        first = self.handler.handle("!petdrop", "Alice")
        self.assertIn("WILD CAT", first)
        self.assertIn("manual pet drop", self.handler.handle("!petdrop", "Bob"))
        self.handler.collectibles.spawn.assert_called_once()

    def test_drops_status_shows_next_automatic_spawn(self):
        self.handler.collectibles.active = None
        self.handler.collectibles.expired.return_value = False
        self.handler.next_auto_drop_at = __import__("time").monotonic() + 120
        message = self.handler.handle("!drops", "Alice")
        self.assertIn("Auto pet drops are active", message)
        self.assertIn("Next drop", message)
        self.assertIn("!petdrop", message)

    def test_stop_disables_autoplay(self):
        dj = MagicMock()
        dj.enabled = True
        self.handler.dj_controller = dj
        self.handler.handle("!stop", "Alice")
        dj.set_autoplay.assert_called_with(False)
        self.handler.music_controller.stop.assert_called()

    def test_party_help_documents_new_commands(self):
        text = self.handler.handle("!h f", "Alice")
        for command in ("!tod", "!wyr", "!nhie", "!8ball"):
            self.assertIn(command, text)
        games = self.handler.handle("!h g", "Alice")
        for command in ("!riddle", "!duel", "!quiz"):
            self.assertIn(command, games)


if __name__ == "__main__":
    unittest.main()
