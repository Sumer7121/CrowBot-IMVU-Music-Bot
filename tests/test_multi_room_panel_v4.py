"""Offscreen Qt regression checks for the visible CrowBot room manager."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from app.multi_room_panel import MultiRoomPanel


class MultiRoomPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = MultiRoomPanel()
        self.rooms = [
            {
                "room_id": "111-1", "type": "Primary", "port": 8765,
                "status": "Playing · broadcasting", "playing": "First song",
                "source": "Music", "clients": 1,
                "stream_url": "https://example.com/one/stream.mp3",
                "queue": [{"title": "Later A", "requested_by": "Alice"}],
            },
            {
                "room_id": "222-2", "type": "Secondary", "port": 8766,
                "status": "Ready · idle", "playing": "Second song",
                "source": "Idle", "clients": 1,
                "stream_url": "https://example.com/two/stream.mp3",
                "queue": [{"title": "Later B", "requested_by": "Bob"}],
            },
        ]
        self.panel.set_rooms(self.rooms)

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()

    def test_both_rooms_visible_with_correct_isolated_song_data(self):
        self.assertEqual(self.panel.room_table.rowCount(), 2)
        self.assertEqual(self.panel.room_table.item(0, 4).text(), "First song")
        self.assertEqual(self.panel.room_table.item(1, 4).text(), "Second song")
        self.panel.room_table.selectRow(1)
        self.assertEqual(self.panel.selected_room(), "222-2")
        self.assertIn("Later B", self.panel.queue_list.item(0).text())
        self.assertNotIn("Later A", self.panel.queue_list.item(0).text())
        self.assertIn("/two/", self.panel.stream_url_input.text())

    def test_room_specific_logs_and_selection(self):
        self.panel.add_log("111-1", "Primary station ready")
        self.panel.add_log("222-2", "Secondary FFmpeg running")
        self.panel.room_table.selectRow(1)
        self.assertIn("Secondary FFmpeg", self.panel.log_view.toPlainText())
        self.assertNotIn("Primary station ready", self.panel.log_view.toPlainText())

    def test_add_reload_skip_stop_and_remove_emit_selected_room(self):
        requests = []
        self.panel.add_requested.connect(lambda value: requests.append(("add", value)))
        self.panel.reload_requested.connect(lambda value: requests.append(("reload", value)))
        self.panel.skip_requested.connect(lambda value: requests.append(("skip", value)))
        self.panel.stop_requested.connect(lambda value: requests.append(("stop", value)))
        self.panel.remove_requested.connect(lambda value: requests.append(("remove", value)))
        self.panel.song_requested.connect(
            lambda room, query: requests.append(("song", room, query))
        )
        self.panel.room_id_input.setText("333-3")
        self.panel.join_button.click()
        self.panel.room_table.selectRow(1)
        self.panel.reload_button.click()
        self.panel.song_input.setText("Song for second room")
        self.panel.song_button.click()
        self.panel.skip_button.click()
        self.panel.stop_button.click()
        self.panel.remove_button.click()
        self.assertEqual(requests, [
            ("add", "333-3"), ("reload", "222-2"),
            ("song", "222-2", "Song for second room"), ("skip", "222-2"),
            ("stop", "222-2"), ("remove", "222-2"),
        ])

    def test_primary_cannot_be_removed(self):
        self.panel.room_table.selectRow(0)
        self.assertFalse(self.panel.remove_button.isEnabled())
        self.assertTrue(self.panel.reload_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
