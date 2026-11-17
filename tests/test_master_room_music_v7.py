"""Regression tests for master-cache and isolated room playback storage."""
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from music.track_library import (
    MIN_MP3_BYTES, RoomTrackLibrary, is_valid_mp3,
)


def write_dummy_mp3(path):
    """Synthetic MP3-shaped fixture for the *storage* layer, not a decoder test."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ID3" + b"\x04\x00" + b"X" * (MIN_MP3_BYTES + 256))
    return path


class MasterRoomMusicTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.root = Path(self.work.name)
        self.library = RoomTrackLibrary(self.root)

    def tearDown(self):
        self.work.cleanup()

    def test_cache_first_and_persistent_query_index(self):
        calls = []
        def download(workspace, token):
            calls.append(token)
            return write_dummy_mp3(workspace / (token + ".mp3"))

        first, hit1 = self.library.get_or_download("video-id_001", download)
        second, hit2 = self.library.get_or_download("video-id_001", download)
        self.assertFalse(hit1)
        self.assertTrue(hit2)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)
        self.library.index_query("Youngblood", {
            "id": "video-id_001",
            "title": "Youngblood", "channel": "Artist",
            "duration": 240, "youtube_url": "https://youtube.com/watch?v=example"
        })
        recreated = RoomTrackLibrary(self.root)
        self.assertEqual(recreated.find_query("  YOUNGBLOOD  ")["id"], "video-id_001")

    def test_two_rooms_same_song_have_separate_copies(self):
        def download(workspace, token):
            return write_dummy_mp3(workspace / (token + ".mp3"))

        master, _ = self.library.get_or_download("sameSong001", download)
        first = self.library.stage_for_room("sameSong001", "111-1", "aabb1122")
        second = self.library.stage_for_room("sameSong001", "222-2", "ccdd3344")
        self.assertNotEqual(first, second)
        self.assertTrue(is_valid_mp3(first))
        self.assertTrue(is_valid_mp3(second))
        self.library.cleanup_room("111-1", "aabb1122")
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertTrue(master.exists())
        self.library.cleanup_room("222-2", "ccdd3344")
        self.assertTrue(master.exists())

    def test_concurrent_requests_download_master_once(self):
        counter = []
        lock = threading.Lock()
        def download(workspace, token):
            with lock:
                counter.append(token)
            time.sleep(0.1)
            return write_dummy_mp3(workspace / (token + ".mp3"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(
                lambda _: self.library.get_or_download("joint-video1", download),
                (1, 2)
            ))
        self.assertEqual(len(counter), 1)
        self.assertEqual([hit for _, hit in result].count(False), 1)
        self.assertEqual([hit for _, hit in result].count(True), 1)

    def test_reject_partial_files_and_deleting_master_from_room_scope(self):
        bad = self.library.master_path("brokenSong")
        bad.write_bytes(b"<html>YouTube error</html>")
        self.assertFalse(is_valid_mp3(bad))
        self.library.release_track(bad, "111-1", "abcabc")
        self.assertTrue(bad.exists())
        with self.assertRaises(ValueError):
            self.library.room_path("../../unsafe", "abcabc")

    def test_cancellation_does_not_publish_bad_master(self):
        def broken(workspace, token):
            return write_dummy_mp3(workspace / (token + ".mp3"))
        with self.assertRaises(RuntimeError):
            self.library.get_or_download(
                "cancelledSong", broken, cancel_check=lambda: True
            )
        self.assertFalse(self.library.master_path("cancelledSong").exists())

    def test_provider_prepares_two_isolated_tracks_from_one_master(self):
        from music.youtube_owned import YouTubeOwnedProvider
        from urllib.request import Request, urlopen

        with patch("music.youtube_owned.TEMP_DIR", self.root):
            provider = YouTubeOwnedProvider()
            provider.library = self.library
            try:
                def download(workspace, token):
                    return write_dummy_mp3(workspace / (token + ".mp3"))
                master, hit = self.library.get_or_download("dualTrack01", download)
                self.assertFalse(hit)
                candidate = {
                    "id": "dualTrack01",
                    "title": "Two Room Song",
                    "channel": "Test Artist",
                    "duration": 180,
                    "youtube_url": "https://youtube.com/watch?v=dualTrack01",
                }
                with patch.object(provider, "_download_mp3", return_value=master):
                    a = provider._prepare_track(
                        candidate, "Two Room Song", "Alice",
                        room_id="111-1", session_key="sessionAA"
                    )
                    b = provider._prepare_track(
                        candidate, "Two Room Song", "Bob",
                        room_id="222-2", session_key="sessionBB"
                    )
                self.assertNotEqual(a["url"], b["url"])
                self.assertNotEqual(a["temporary_file"], b["temporary_file"])
                self.assertTrue(Path(a["temporary_file"]).is_file())
                self.assertTrue(Path(b["temporary_file"]).is_file())
                provider.cleanup_room_files("111-1", "sessionAA")
                self.assertFalse(Path(a["temporary_file"]).exists())
                with urlopen(Request(b["url"], method="HEAD"), timeout=4) as response:
                    self.assertEqual(response.status, 200)
                self.assertTrue(master.exists())
            finally:
                provider.cleanup()

    def test_http_preflight_serves_full_room_relative_path(self):
        from music.youtube_owned import YouTubeOwnedProvider
        with patch("music.youtube_owned.TEMP_DIR", self.root):
            provider = YouTubeOwnedProvider()
            provider.library = self.library
            try:
                def download(workspace, token):
                    return write_dummy_mp3(workspace / (token + ".mp3"))
                self.library.get_or_download("songxyz123", download)
                song = self.library.stage_for_room(
                    "songxyz123", "111-1", "sample01"
                )
                provider._start_http_server()
                url = provider._build_local_url(song)
                self.assertIn("/rooms/111-1/sample01/", url)
                provider._verify_local_song_url(url, song)
                with self.assertRaises(RuntimeError):
                    provider._verify_local_song_url(
                        url.replace("songxyz123-", "deleted-"), song
                    )
            finally:
                provider.cleanup()


if __name__ == "__main__":
    unittest.main()
