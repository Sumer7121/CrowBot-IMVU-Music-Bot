"""Every room is equal: independent connect, radio, queue and disconnect."""
import os
import unittest
import threading
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

from app.multi_room_panel import MultiRoomPanel
from app.multi_room_hub import MultiRoomHub


class FakeOpen(QObject):
    opened = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.room_url = url
        self.running = False

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def wait(self, timeout):
        self.running = False
        return True


class FakeMonitor(FakeOpen):
    ready = Signal(str)
    failed = Signal(str, str)
    message_received = Signal(str, str, str)

    def stop(self):
        self.running = False
        self.finished.emit()


class FakeRadio(FakeOpen):
    succeeded = Signal(str, str)

    def __init__(self, url, parent=None, room_url=None):
        super().__init__(url, parent)
        self.room_url = room_url


class FakeTunnel(QObject):
    tunnel_started = Signal(str)
    tunnel_error = Signal(str)
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.url = ""

    def get_stream_url(self):
        return self.url


class FakeMusic(QObject):
    now_playing_changed = Signal(object)
    queue_changed = Signal()
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.songs = []
        self.current = None
        self.stop_count = 0

    def get_current_song(self):
        return self.current

    def get_queue(self):
        return self.songs[:]

    def stop(self):
        self.stop_count += 1
        self.current = None
        self.songs.clear()
        self.queue_changed.emit()

    def skip(self):
        self.songs.pop(0) if self.songs else None
        self.queue_changed.emit()


class FakeCommands(QObject):
    async_response = Signal(str, str)

    def __init__(self, music):
        super().__init__()
        self.music = music
        self.prefix = "!"
        self.collectibles = FakeCollectibles()
        self.next_auto_drop_at = None

    def handle(self, text, username):
        if text.startswith("!p "):
            title = text[3:]
            song = {"title": title, "requested_by": username}
            self.music.current = song
            self.music.songs.append(song)
            self.music.now_playing_changed.emit(song)
            self.music.queue_changed.emit()
        return "OK"


class FakeDJ(QObject):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.enabled = False
        self.artist = ""
        self.language = ""
        self.match_current_language = False
        self.radio_ready = False

    @property
    def label(self):
        return "ARTIST DJ: " + self.artist if self.artist and self.enabled else (
            "YOUTUBE AUTOPLAY" if self.enabled else "DJ OFF"
        )

    def set_ready(self, value):
        self.radio_ready = value

    def set_artist(self, name):
        self.artist = name
        self.enabled = True
        self.status_changed.emit("Artist DJ: " + name)
        return self.label

    def set_autoplay(self, enabled):
        self.enabled = bool(enabled)
        return self.label

    def set_language(self, name):
        self.match_current_language = name.casefold() in ("auto", "match current", "match")
        self.language = (
            "" if name.casefold() in ("off", "any") or self.match_current_language
            else name.casefold()
        )
        return self.label

    def off(self):
        self.enabled = False
        self.artist = ""

    def shutdown(self):
        self.enabled = False


class FakeCollectibles:
    def __init__(self):
        self.active = None
        self.spawn_count = 0

    def expired(self):
        return False

    def spawn(self):
        if self.active is not None:
            return None
        self.spawn_count += 1
        self.active = True
        return "✨ WILD CAT DROP! 🐱 Mochi [COMMON] Type !catch!"


class FakeSession:
    def __init__(self, room_url, prefix="!", user_manager=None, radio_port=None):
        self.room_url = room_url.rstrip("/")
        self.radio_port = radio_port
        self.stream_url = ""
        self.music_controller = FakeMusic()
        self.command_handler = FakeCommands(self.music_controller)
        self.dj = FakeDJ()
        self.command_handler.dj_controller = self.dj
        self.radio_server = MagicMock()
        self.radio_server.get_health.return_value = {
            "running": True, "source_set": False,
            "source_age": 0, "audio_recent": False, "last_error": "",
            "clients": 1,
        }
        self.radio_server.get_source.return_value = ""
        self.tunnel = FakeTunnel()
        self.started = False
        self.stopped = False

    def start_radio(self):
        self.started = True

    def stop_radio(self):
        self.stopped = True

    def process(self, user, message):
        return self.command_handler.handle(message, user)


class EqualRoomsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QWidget()
        self.window.logs = []
        self.window.settings = {"username": "freska2", "prefix": "!", "rooms": []}
        self.window.user_manager = MagicMock()
        self.window.room_panel = MultiRoomPanel(self.window)
        self.window._ensure_dedicated_bot_chrome = MagicMock()
        self.window.send_bot_response_to_imvu = MagicMock()
        self.patcher = patch("app.multi_room_hub.RoomSession", FakeSession)
        self.patcher.start()
        self.loaded = {"rooms": []}
        self.load_patch = patch(
            "app.multi_room_hub.load_settings",
            side_effect=lambda: dict(self.loaded),
        )
        self.save_patch = patch(
            "app.multi_room_hub.save_settings",
            side_effect=lambda values: self.loaded.update(values),
        )
        self.load_patch.start()
        self.save_patch.start()
        self.hub = MultiRoomHub(self.window, FakeOpen, FakeMonitor, FakeRadio)

    def tearDown(self):
        self.hub.shutdown()
        self.patcher.stop()
        self.load_patch.stop()
        self.save_patch.stop()
        self.window.close()

    def _connect(self, room_id):
        self.hub.connect_room(room_id)
        url = "https://www.imvu.com/next/chat/room-" + room_id + "/"
        self.hub.open_workers[room_id].opened.emit(url)
        self.hub.chat_workers[room_id].ready.emit(url)
        self.assertTrue(self.hub.sessions[room_id].started)
        stream = "https://" + room_id.replace("-", "") + ".trycloudflare.com/stream.mp3"
        self.hub.sessions[room_id].tunnel.url = stream
        self.hub.sessions[room_id].tunnel.tunnel_started.emit(stream)
        self.hub.radio_workers[room_id].succeeded.emit(stream, "")
        self.assertEqual(self.hub.sessions[room_id].stream_url, stream)

    def test_add_two_connect_separately_keep_own_cloud_links(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self.assertEqual(self.hub.room_ids, ["111-1", "222-2"])
        self.assertEqual(self.window.room_panel.room_table.rowCount(), 2)
        self._connect("111-1")
        self._connect("222-2")
        self.assertNotEqual(
            self.hub.sessions["111-1"].radio_port,
            self.hub.sessions["222-2"].radio_port
        )
        self.assertNotEqual(
            self.hub.sessions["111-1"].stream_url,
            self.hub.sessions["222-2"].stream_url
        )
        self.assertEqual(self.hub.states["111-1"], "Connected")
        self.assertEqual(self.hub.states["222-2"], "Connected")
        self.assertEqual(self.window._ensure_dedicated_bot_chrome.call_count, 2)

    def test_disconnecting_room_one_does_not_stop_room_two(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        second = self.hub.sessions["222-2"]
        self.hub.request_song("111-1", "Song A")
        self.hub.request_song("222-2", "Song B")
        self.assertEqual(second.music_controller.current["title"], "Song B")
        self.hub.disconnect_room("111-1")
        self.assertTrue("111-1" not in self.hub.sessions)
        self.assertIs(self.hub.sessions["222-2"], second)
        self.assertFalse(second.stopped)
        self.assertEqual(second.music_controller.current["title"], "Song B")

    def test_each_room_gets_filtered_song_and_chat_logs(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        self.hub.request_song("111-1", "Orange")
        self.hub.request_song("222-2", "Blue")
        self.hub._chat("111-1", self.hub._epoch["111-1"], "Alice", "Hello")
        self.window.send_bot_response_to_imvu.assert_any_call(
            "OK", room_url="https://www.imvu.com/next/chat/room-111-1/"
        )
        self.window.send_bot_response_to_imvu.assert_any_call(
            "OK", room_url="https://www.imvu.com/next/chat/room-222-2/"
        )
        self.assertIn("Alice: Hello", "\n".join(self.window.room_panel._logs["111-1"]))
        self.assertNotIn("Alice: Hello", "\n".join(self.window.room_panel._logs["222-2"]))
        self.assertEqual(
            self.hub.sessions["111-1"].music_controller.current["title"], "Orange"
        )
        self.assertEqual(
            self.hub.sessions["222-2"].music_controller.current["title"], "Blue"
        )

    def test_join_creates_independent_automatic_drop_timers(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        self.assertTrue(self.hub.drop_timers["111-1"].isActive())
        self.assertTrue(self.hub.drop_timers["222-2"].isActive())
        first = self.hub.sessions["111-1"]
        second = self.hub.sessions["222-2"]
        self.assertIsNot(first.command_handler.collectibles,
                         second.command_handler.collectibles)
        self.assertGreater(first.command_handler.next_auto_drop_at, 0)
        self.assertGreater(second.command_handler.next_auto_drop_at, 0)

    def test_automatic_pet_drop_announced_only_in_target_room(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        self.window.send_bot_response_to_imvu.reset_mock()
        self.hub._spawn_room_drop("111-1", self.hub._epoch["111-1"])
        self.window.send_bot_response_to_imvu.assert_called_once_with(
            "✨ WILD CAT DROP! 🐱 Mochi [COMMON] Type !catch!",
            room_url="https://www.imvu.com/next/chat/room-111-1/",
        )
        self.assertEqual(
            self.hub.sessions["222-2"].command_handler.collectibles.spawn_count, 0
        )
        # A second attempted tick must not duplicate the still-active pet.
        self.hub._spawn_room_drop("111-1", self.hub._epoch["111-1"])
        self.assertEqual(
            self.hub.sessions["111-1"].command_handler.collectibles.spawn_count, 1
        )

    def test_disconnect_stops_only_that_rooms_drop_timer(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        self.hub.disconnect_room("111-1")
        self.assertNotIn("111-1", self.hub.drop_timers)
        self.assertTrue(self.hub.drop_timers["222-2"].isActive())
        self.assertIsNotNone(
            self.hub.sessions["222-2"].command_handler.next_auto_drop_at
        )

    def test_dj_now_playing_is_announced_once_in_correct_imvu_room(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        self.window.send_bot_response_to_imvu.reset_mock()
        song = {
            "id": "vid-song-101",
            "url": "http://local/test-song.mp3",
            "title": "A Test Artist - My Song",
            "dj_auto": True,
            "dj_artist": "Test Artist",
        }
        self.hub._song_changed("111-1", self.hub._epoch["111-1"], song)
        self.hub._song_changed("111-1", self.hub._epoch["111-1"], song)
        self.window.send_bot_response_to_imvu.assert_called_once_with(
            "🎧 DJ NOW PLAYING: A Test Artist - My Song | Artist: Test Artist",
            room_url="https://www.imvu.com/next/chat/room-111-1/",
        )
        self.hub._song_changed("222-2", self.hub._epoch["222-2"], {
            "title": "Room B Song", "url": "http://local/b.mp3"
        })
        self.window.send_bot_response_to_imvu.assert_any_call(
            "🎵 NOW PLAYING: Room B Song",
            room_url="https://www.imvu.com/next/chat/room-222-2/",
        )

    def test_artist_and_language_settings_are_isolated_by_room(self):
        self.hub.add_room("111-1")
        self.hub.add_room("222-2")
        self._connect("111-1")
        self._connect("222-2")
        self.hub.set_language("111-1", "Hindi")
        self.hub.artist_dj("111-1", "Arijit Singh")
        self.hub.set_autoplay("222-2", True)
        a = self.hub.sessions["111-1"].dj
        b = self.hub.sessions["222-2"].dj
        self.assertTrue(a.radio_ready)
        self.assertTrue(b.radio_ready)
        self.assertEqual(a.artist, "Arijit Singh")
        self.assertEqual(a.language, "hindi")
        self.assertEqual(b.artist, "")
        self.assertEqual(b.language, "")
        self.assertTrue(b.enabled)
        self.hub.stop_dj("111-1")
        self.assertFalse(a.enabled)
        self.assertTrue(b.enabled)

    def test_cloudflare_thread_handoff_creates_radio_worker_on_ui_thread(self):
        """Simulate Cloudflare Python validator signalling from a non-GUI thread."""
        main_thread = threading.get_ident()
        observed_threads = []

        class ThreadCheckedRadio(FakeRadio):
            def __init__(self, *args, **kwargs):
                observed_threads.append(threading.get_ident())
                super().__init__(*args, **kwargs)

        self.hub.radio_worker_class = ThreadCheckedRadio
        self.hub.add_room("111-1")
        self.hub.connect_room("111-1")
        url = "https://www.imvu.com/next/chat/room-111-1/"
        self.hub.open_workers["111-1"].opened.emit(url)
        self.hub.chat_workers["111-1"].ready.emit(url)

        tunnel = self.hub.sessions["111-1"].tunnel
        stream = "https://test-one.trycloudflare.com/stream.mp3"
        tunnel.url = stream
        background = threading.Thread(
            target=lambda: tunnel.tunnel_started.emit(stream), daemon=True
        )
        background.start()
        background.join(timeout=2)

        deadline = time.monotonic() + 3
        while not observed_threads and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)

        self.assertEqual(observed_threads, [main_thread])
        self.assertEqual(self.hub.states["111-1"], "Loading IMVU radio")
        self.assertIn(
            "RADIO LOAD: Worker started",
            "\n".join(self.window.room_panel._logs["111-1"])
        )

    def test_radio_success_emitted_from_worker_thread_updates_right_room(self):
        self.hub.add_room("111-1")
        self.hub.connect_room("111-1")
        room = "https://www.imvu.com/next/chat/room-111-1/"
        self.hub.open_workers["111-1"].opened.emit(room)
        self.hub.chat_workers["111-1"].ready.emit(room)
        stream = "https://radio-111.trycloudflare.com/stream.mp3"
        self.hub.sessions["111-1"].tunnel.url = stream
        self.hub.sessions["111-1"].tunnel.tunnel_started.emit(stream)
        radio = self.hub.radio_workers["111-1"]
        background = threading.Thread(
            target=lambda: radio.succeeded.emit(stream, ""),
            daemon=True,
        )
        background.start()
        background.join(timeout=2)
        deadline = time.monotonic() + 3
        while self.hub.states.get("111-1") != "Connected" and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertEqual(self.hub.states["111-1"], "Connected")
        self.assertEqual(self.hub.sessions["111-1"].stream_url, stream)

    def test_imvu_radio_startup_error_is_scoped_to_selected_room(self):
        class FailingRadio:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("Radio worker intentionally failed")
        self.hub.radio_worker_class = FailingRadio
        self.hub.add_room("111-1")
        self.hub.connect_room("111-1")
        room = "https://www.imvu.com/next/chat/room-111-1/"
        self.hub.open_workers["111-1"].opened.emit(room)
        self.hub.chat_workers["111-1"].ready.emit(room)
        stream = "https://test-two.trycloudflare.com/stream.mp3"
        self.hub.sessions["111-1"].tunnel.tunnel_started.emit(stream)
        self.assertEqual(self.hub.states["111-1"], "Error")
        self.assertIn(
            "RADIO LOAD FAILED TO START",
            "\n".join(self.window.room_panel._logs["111-1"])
        )

    def test_no_primary_room_and_rooms_are_explicitly_saved(self):
        self.hub.add_room("111-1")
        self.assertEqual(self.loaded["rooms"], ["111-1"])
        self.assertNotIn("111-1", self.hub.sessions)
        self.hub.remove_room("111-1")
        self.assertEqual(self.loaded["rooms"], [])


if __name__ == "__main__":
    unittest.main()
