"""Unit tests for per-room artist DJ, autoplay discovery, and language mode."""
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, QCoreApplication, Signal
from music.auto_dj import (
    LANGUAGES, AutoDJ, candidate_allowed, detect_song_language,
    normalize_language, search_queries,
)


class FakeMusic(QObject):
    now_playing_changed = Signal(object)
    queue_changed = Signal()

    def __init__(self):
        super().__init__()
        self.current = None
        self.songs = []

    def get_current_song(self):
        return self.current

    def get_queue(self):
        return list(self.songs)

    def add_song(self, song):
        self.songs.append(song)
        self.queue_changed.emit()
        return True


class DJPolicyTests(unittest.TestCase):
    def test_language_names_and_codes(self):
        for name, code in LANGUAGES.items():
            self.assertEqual(normalize_language(name), name)
            self.assertEqual(normalize_language(code), name)
        self.assertEqual(normalize_language("off"), "")
        self.assertEqual(normalize_language("Any"), "")
        with self.assertRaises(ValueError):
            normalize_language("Martian")

    def test_search_artist_and_language(self):
        queries = search_queries("Arijit Singh", "Hindi", round_index=0)
        self.assertEqual(len(queries), 2)
        self.assertTrue(all("Arijit Singh" in q for q in queries))
        self.assertTrue(all("hindi" in q for q in queries))
        self.assertNotEqual(queries[0], queries[1])

    def test_match_current_song_uses_language_metadata_or_script(self):
        self.assertEqual(detect_song_language({
            "title": "Summer Song", "language": "te"
        }), "telugu")
        self.assertEqual(detect_song_language({
            "title": "తెలుగు పాట", "language": ""
        }), "telugu")
        self.assertEqual(detect_song_language({
            "title": "New Hindi Song 2026", "language": ""
        }), "hindi")
        self.assertEqual(detect_song_language({
            "title": "Unidentified Song", "language": ""
        }), "")

    def test_youtube_autoplay_seeds_with_current_music(self):
        queries = search_queries(
            artist="", language="Telugu", current_title="Song A", round_index=0
        )
        self.assertIn("Song A", queries[0])
        self.assertIn("telugu", queries[0])

    def test_candidate_filter_rejects_wrong_artist_and_declared_language(self):
        track = {
            "title": "Arijit Singh - Test Track (Official Audio)",
            "channel": "Music Label", "duration": 210,
            "language": "hi",
        }
        self.assertTrue(candidate_allowed(track, "Arijit Singh", "Hindi"))
        self.assertFalse(candidate_allowed(track, "Atif Aslam", "Hindi"))
        self.assertFalse(candidate_allowed(track, "Arijit Singh", "English"))
        self.assertFalse(candidate_allowed({**track, "duration": 9000}))
        self.assertFalse(candidate_allowed({**track, "title": "Reaction to song"}))


class AutoDJControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.music = FakeMusic()
        self.dj = AutoDJ(self.music)

    def tearDown(self):
        # No real worker was started in these unit tests.
        self.dj.shutdown()

    def test_autoplay_does_not_fetch_before_room_radio_ready(self):
        with patch("music.auto_dj.DJFetchWorker") as worker:
            self.dj.set_autoplay(True)
            worker.assert_not_called()

    def test_dj_prefetches_just_one_song(self):
        with patch("music.auto_dj.DJFetchWorker") as worker:
            fake = worker.return_value
            self.dj.set_ready(True)
            self.dj.set_artist("Arijit Singh")
            self.assertTrue(self.dj.enabled)
            self.assertEqual(fake.start.call_count, 1)
            self.dj._maybe_fill()
            self.assertEqual(fake.start.call_count, 1)
            song = {"id": "video123", "title": "Song", "url": "http://localhost/song.mp3"}
            self.dj._on_prepared(self.dj._generation, song)
            self.assertEqual(self.music.get_queue(), [song])
            self.assertEqual(self.dj._seen, ["video123"])

    def test_match_current_language_is_per_room(self):
        with patch("music.auto_dj.DJFetchWorker"):
            self.music.current = {
                "title": "తెలుగు పాట", "language": "te",
                "url": "http://localhost/track.mp3",
            }
            self.dj.set_language("Match Current")
            self.assertTrue(self.dj.match_current_language)
            self.assertEqual(self.dj._detected_language, "telugu")
            other = AutoDJ(FakeMusic())
            try:
                self.assertFalse(other.match_current_language)
                self.assertEqual(other._detected_language, "")
            finally:
                other.shutdown()

    def test_off_invalidates_pending_song(self):
        with patch("music.auto_dj.DJFetchWorker"):
            self.dj.set_ready(True)
            self.dj.set_autoplay(True)
            old_generation = self.dj._generation
            self.dj.off()
            self.dj._on_prepared(old_generation, {
                "id": "stale", "title": "Do not queue", "url": "http://local/music.mp3",
            })
            self.assertEqual(self.music.songs, [])

    def test_language_change_clears_recent_history_not_other_rooms(self):
        first = self.dj
        second = AutoDJ(FakeMusic())
        try:
            first._seen = ["one"]
            second._seen = ["two"]
            first.set_language("Hindi")
            self.assertEqual(first.language, "hindi")
            self.assertEqual(first._seen, [])
            self.assertEqual(second._seen, ["two"])
            self.assertEqual(second.language, "")
        finally:
            second.shutdown()


if __name__ == "__main__":
    unittest.main()
