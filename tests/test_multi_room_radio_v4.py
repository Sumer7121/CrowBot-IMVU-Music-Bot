"""Regression coverage for multi-room routing and radio-source isolation."""
import unittest
from unittest.mock import MagicMock, patch

from bot.room_ids import make_room_url, normalize_room_id
from radio_server.server import RadioStreamServer


class RoomIdsTests(unittest.TestCase):
    def test_accepted_formats(self):
        samples = (
            "391169385-9",
            "room-391169385-9",
            "https://www.imvu.com/next/chat/room-391169385-9/",
            "https://www.imvu.com/next/chat/room-391169385-9/?foo=bar",
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(normalize_room_id(text), "391169385-9")
        self.assertEqual(
            make_room_url("391169385-9"),
            "https://www.imvu.com/next/chat/room-391169385-9/",
        )

    def test_reject_untrusted_or_invalid_room_ids(self):
        for invalid in (
            "anything", "391169385", "abc-4", "https://evil.com/next/chat/room-1-2/",
            "https://www.imvu.com/next/chat/room-12-3/../../something",
        ):
            with self.subTest(text=invalid):
                with self.assertRaises(ValueError):
                    normalize_room_id(invalid)


class RadioIsolationTests(unittest.TestCase):
    def test_two_radio_servers_have_isolated_sources(self):
        a = RadioStreamServer(port=8765)
        b = RadioStreamServer(port=8766)
        a.set_source("https://example.org/room-1.mp3")
        b.set_source("https://example.org/room-2.mp3")
        self.assertNotEqual(a.get_source(), b.get_source())
        self.assertEqual(a.get_health()["generation"], 1)
        self.assertEqual(b.get_health()["generation"], 1)
        a.clear_sources()
        self.assertEqual(a.get_source(), "")
        self.assertEqual(b.get_source(), "https://example.org/room-2.mp3")

    def test_repeating_same_track_forces_new_ffmpeg_generation(self):
        radio = RadioStreamServer()
        radio.set_source("https://example.org/repeat.mp3")
        first = radio.get_source_state()[1]
        radio.set_source("https://example.org/repeat.mp3")
        self.assertEqual(radio.get_source_state()[1], first)
        radio.set_source("https://example.org/repeat.mp3", force_restart=True)
        self.assertEqual(radio.get_source_state()[1], first + 1)


class MusicControllerRadioTests(unittest.TestCase):
    def _create(self):
        from music.controller import MusicController
        with patch("music.controller.MusicPlayer") as player_cls:
            controller = MusicController()
            controller.player = player_cls.return_value
        radio = MagicMock()
        radio.is_running.return_value = True
        controller.attach_radio_server(radio)
        return controller, radio

    def test_pause_silences_public_radio_and_resume_restores(self):
        controller, radio = self._create()
        song = {"title": "Song A", "url": "https://example.org/a.mp3"}
        controller.add_song(song)
        radio.set_source.assert_called_with(song["url"], force_restart=True)
        controller.pause()
        radio.clear_sources.assert_called()
        controller.resume()
        self.assertEqual(radio.set_source.call_count, 2)
        radio.set_source.assert_called_with(song["url"], force_restart=True)

    def test_independent_music_controllers(self):
        a, radio_a = self._create()
        b, radio_b = self._create()
        a.add_song({"title": "Song A", "url": "https://example.org/a.mp3"})
        b.add_song({"title": "Song B", "url": "https://example.org/b.mp3"})
        self.assertEqual(a.get_current_song()["title"], "Song A")
        self.assertEqual(b.get_current_song()["title"], "Song B")
        a.stop()
        radio_a.clear_sources.assert_called()
        radio_b.clear_sources.assert_not_called()
        self.assertEqual(b.get_current_song()["title"], "Song B")


if __name__ == "__main__":
    unittest.main()
