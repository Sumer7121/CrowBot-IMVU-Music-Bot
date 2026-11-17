"""Tests for isolated multi-room command routing."""
import unittest
from unittest.mock import patch, MagicMock


class RoomSessionTests(unittest.TestCase):
    def setUp(self):
        self.music_patch = patch("bot.room_session.MusicController")
        self.handler_patch = patch("bot.room_session.CommandHandler")
        self.mock_music = self.music_patch.start()
        self.mock_music.side_effect = lambda: MagicMock()
        self.mock_handler = self.handler_patch.start()
        self.mock_handler.side_effect = lambda *args, **kwargs: MagicMock(prefix=kwargs.get('prefix', args[2] if len(args) > 2 else '!'))
        from bot.room_session import RoomSession
        self.RoomSession = RoomSession

    def tearDown(self):
        self.handler_patch.stop()
        self.music_patch.stop()

    def test_sessions_have_distinct_handlers(self):
        a = self.RoomSession("https://imvu.com/next/chat/room-1-1/")
        b = self.RoomSession("https://imvu.com/next/chat/room-2-2/")
        self.assertIsNot(a.command_handler, b.command_handler)
        self.assertIsNot(a.music_controller, b.music_controller)
        self.assertNotEqual(a.room_url, b.room_url)

    def test_ping_responds_per_room(self):
        room = self.RoomSession("https://imvu.com/next/chat/room-1-1/")
        room.command_handler.prefix = "!"
        self.assertIn("Alice", room.process("Alice", "!ping"))

    def test_secondary_music_disabled(self):
        room = self.RoomSession("https://imvu.com/next/chat/room-1-1/")
        room.command_handler.prefix = "!"
        self.assertIn("not enabled", room.process("Alice", "!p song"))

    def test_non_music_forwarded(self):
        room = self.RoomSession("https://imvu.com/next/chat/room-1-1/")
        room.command_handler.prefix = "!"
        room.command_handler.handle.return_value = "game started"
        self.assertEqual(room.process("Alice", "!ttt"), "game started")
        room.command_handler.handle.assert_called_once_with("!ttt", "Alice")


if __name__ == "__main__":
    unittest.main()
