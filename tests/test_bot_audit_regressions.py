"""Behavior regressions found during the whole-bot review."""
import copy
import os
import unittest
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bot.commands import CommandHandler, MusicResolveWorker
from bot.room_permissions import RoomPermissions, canonical_command
from music.controller import MusicController
from radio_server.server import RadioStreamServer
from app.multi_room_hub import MultiRoomHub


class BotAuditTests(unittest.TestCase):
    def setUp(self):
        for target in ("bot.commands.MusicResolver",
                       "bot.commands.get_shared_youtube_provider",
                       "bot.commands.CollectibleDrops",
                       "bot.room_permissions.save_settings"):
            p = patch(target)
            p.start()
            self.addCleanup(p.stop)
        p = patch("bot.room_permissions.load_settings",
                  side_effect=lambda: copy.deepcopy({"room_policies": {}}))
        p.start()
        self.addCleanup(p.stop)
        self.music = MagicMock()
        self.handler = CommandHandler(self.music, MagicMock())

    def test_equivalent_commands_share_one_lock(self):
        groups = defaultdict(list)
        for command, method in self.handler.commands.items():
            groups[method.__name__].append(command)
        policy = RoomPermissions("111-1")
        for aliases in groups.values():
            if len(aliases) < 2:
                continue
            self.assertEqual(len({canonical_command(a) for a in aliases}), 1, aliases)
            policy.lock_command(aliases[0], self.handler.commands)
            for alias in aliases:
                self.assertFalse(policy.may_run(alias, "Visitor"), alias)

    def test_youtube_links_go_through_downloader(self):
        with patch.object(self.handler, "start_music_resolve") as resolve:
            for url in ("https://www.youtube.com/watch?v=abc",
                        "https://youtu.be/abc", "https://m.youtube.com/shorts/abc"):
                self.handler.handle("!play " + url, "Alice")
                resolve.assert_called_with(url, "Alice")
        self.music.add_song.assert_not_called()

    def test_direct_audio_urls_still_queue_immediately(self):
        self.handler.handle("!play https://example.com/song.mp3 My Song", "Alice")
        self.assertEqual(self.music.add_song.call_args.args[0]["title"], "My Song")

    def test_ytsearch_queues_background_work_without_blocking_chat(self):
        with patch.object(self.handler, "start_music_resolve") as resolve:
            response = self.handler.handle("!ytsearch My Song", "Alice")
            self.assertIn("Searching YouTube", response)
            resolve.assert_called_once_with("My Song", "Alice", search_only=True)
        self.handler.youtube_search.search_candidates.assert_not_called()

    def test_search_results_are_returned_to_chat_without_playing(self):
        replies = []
        self.handler.async_response.connect(lambda user, text: replies.append((user, text)))
        self.handler.music_resolve_succeeded("Alice", "My Song", {
            "search_results": [{"id": "abc", "title": "My Song", "channel": "Artist"}]
        })
        self.assertIn("1. My Song - Artist [abc]", replies[0][1])
        self.assertEqual(replies[0][0], "Alice")
        self.music.add_song.assert_not_called()

    def test_stop_discards_late_download_and_allows_new_requests(self):
        old_worker = MagicMock()
        self.handler.active_music_worker = old_worker
        self.handler.music_prepare_queue.append({"query": "old", "username": "Alice"})
        self.handler.stop([], "Owner")
        old_worker.requestInterruption.assert_called_once()
        self.assertEqual(self.handler.music_prepare_queue, [])
        self.handler.music_resolve_succeeded("Alice", "old", {
            "url": "http://local/old.mp3", "temporary_file": "old.mp3"
        })
        self.music.add_song.assert_not_called()
        self.handler.youtube_search.release_room_track.assert_called_once()
        with patch("bot.commands.MusicResolveWorker") as worker_cls:
            self.handler.start_music_resolve("new", "Alice")
            worker_cls.assert_not_called()
            self.handler.music_resolve_finished()
            worker_cls.return_value.start.assert_called_once()
            self.handler.music_resolve_succeeded("Alice", "new", {
                "url": "http://local/new.mp3"
            })
            self.music.add_song.assert_called_once()

    def test_clear_cancels_unfinished_downloads(self):
        worker = MagicMock()
        self.handler.active_music_worker = worker
        self.handler.clear([], "Owner")
        worker.requestInterruption.assert_called_once()
        self.handler.music_resolve_succeeded("Alice", "old", {"url": "old"})
        self.music.add_song.assert_not_called()
        self.music.clear_queue.assert_called_once()

    def test_worker_releases_download_completed_after_cancellation(self):
        resolver = MagicMock()
        resolver.resolve.return_value = {"temporary_file": "orphan.mp3"}
        worker = MusicResolveWorker(resolver, "song", "Alice", room_id="111-1")
        with patch.object(worker, "isInterruptionRequested", return_value=True), patch(
            "bot.commands.get_shared_youtube_provider"
        ) as provider:
            worker.run()
            provider.return_value.release_room_track.assert_called_once_with(
                "orphan.mp3", "111-1", "legacy"
            )

    def test_whoami_does_not_report_owner_for_matching_display_name(self):
        policy = RoomPermissions("111-1")
        policy.set_owner_from_dashboard("Owner123")
        self.handler.room_permissions = policy
        self.handler.actor_display_name = "Owner123"
        self.handler.actor_account_username = ""
        self.assertIn("| member", self.handler.whoami([], "Owner123"))

    def controller(self):
        with patch("music.controller.MusicPlayer"):
            controller = MusicController()
        radio = RadioStreamServer()
        radio.is_running = lambda: True
        controller.attach_radio_server(radio)
        controller.add_song({"url": "http://local/a.mp3", "title": "A"})
        controller.add_song({"url": "http://local/b.mp3", "title": "B"})
        controller.add_song({"url": "http://local/c.mp3", "title": "C"})
        return controller, radio

    def test_radio_reload_still_advances_on_public_eof(self):
        controller, radio = self.controller()
        previous = controller._radio_generation
        hub = MagicMock()
        hub.sessions = {"111-1": SimpleNamespace(
            stream_url="https://example.com/stream.mp3",
            radio_server=radio, music_controller=controller)}
        hub._epoch = {"111-1": 1}
        MultiRoomHub.reload_radio(hub, "111-1")
        self.assertNotEqual(controller._radio_generation, previous)
        self.assertTrue(controller.on_radio_track_finished(
            "http://local/a.mp3", radio.get_source_state()[1]))
        self.assertEqual(controller.get_current_song()["title"], "B")

    def test_local_and_radio_eof_cannot_skip_two_songs(self):
        controller, radio = self.controller()
        controller.on_radio_track_finished("http://local/a.mp3", controller._radio_generation)
        controller.on_song_finished()
        self.assertEqual(controller.get_current_song()["title"], "B")

    def test_local_eof_does_not_cut_public_track_short(self):
        controller, radio = self.controller()
        controller.on_song_finished()
        self.assertEqual(controller.get_current_song()["title"], "A")

    def test_local_only_playback_still_advances(self):
        controller, radio = self.controller()
        controller.radio_server = None
        controller.on_song_finished()
        self.assertEqual(controller.get_current_song()["title"], "B")

    def test_dashboard_stop_cancels_pending_manual_requests(self):
        session = MagicMock()
        hub = MagicMock()
        hub.sessions = {"111-1": session}
        MultiRoomHub.control_music(hub, "111-1", "stop")
        session.command_handler.cancel_music_requests.assert_called_once()

    def test_prefix_change_reaches_all_connected_rooms(self):
        from app.main_window import MainWindow
        window = MagicMock()
        sessions = [MagicMock(), MagicMock()]
        window.room_hub.sessions = {"111-1": sessions[0], "222-2": sessions[1]}
        with patch("app.main_window.SettingsWindow") as dialog, patch(
            "app.main_window.load_settings", return_value={"prefix": "$"}
        ):
            dialog.return_value.exec.return_value = True
            MainWindow.open_settings(window)
        for session in sessions:
            session.command_handler.set_prefix.assert_called_once_with("$")
