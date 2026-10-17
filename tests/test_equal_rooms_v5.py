"""Every room is equal: independent connect, radio, queue and disconnect."""
import os
import unittest
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
        self.language = "" if name.casefold() in ("off", "any") else name.casefold()
        return self.label

    def off(self):
        self.enabled = False
        self.artist = ""

    def shutdown(self):
        self.enabled = False


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

    def test_no_primary_room_and_rooms_are_explicitly_saved(self):
        self.hub.add_room("111-1")
        self.assertEqual(self.loaded["rooms"], ["111-1"])
        self.assertNotIn("111-1", self.hub.sessions)
        self.hub.remove_room("111-1")
        self.assertEqual(self.loaded["rooms"], [])


if __name__ == "__main__":
    unittest.main()
