"""Room-first runtime: every IMVU room owns an independent music station.

There is deliberately no primary room. Rooms are connected/disconnected
individually, while all Playwright workers share one dedicated Chrome profile.
"""
import socket

from PySide6.QtCore import QObject, Signal

from bot.room_ids import make_room_url, normalize_room_id
from bot.room_session import RoomSession
from config.settings import load_settings, save_settings


class MultiRoomHub(QObject):
    radio_event = Signal(str, str)

    def __init__(self, window, open_worker, monitor_worker, radio_worker):
        super().__init__(window)
        self.window = window
        self.open_worker_class = open_worker
        self.monitor_worker_class = monitor_worker
        self.radio_worker_class = radio_worker
        self.room_ids = []
        self.sessions = {}
        self.states = {}
        self.open_workers = {}
        self.chat_workers = {}
        self.radio_workers = {}
        self.retired_workers = []
        self._epoch = {}
        self.radio_event.connect(self._on_radio_event)
        self.restore_rooms()

    def restore_rooms(self):
        settings = load_settings()
        stored = settings.get("rooms", [])
        if not isinstance(stored, list):
            stored = []
        # Rooms are explicitly added in the dashboard. Never silently
        # resurrect or auto-connect the old single-room setting.
        for raw in stored:
            try:
                room_id = normalize_room_id(raw)
            except ValueError:
                continue
            if room_id not in self.room_ids:
                self.room_ids.append(room_id)
        self.refresh_ui()

    def _save_rooms(self):
        settings = load_settings()
        settings["rooms"] = self.room_ids[:]
        save_settings(settings)
        self.window.settings["rooms"] = self.room_ids[:]

    def _log(self, room_id, message):
        line = str(message)
        if room_id:
            line = f"[ROOM {room_id}] {line}"
        print(line)
        self.window.logs.append(line)
        if hasattr(self.window, "room_panel"):
            self.window.room_panel.add_log(room_id or "ALL", line)

    def add_room(self, raw):
        try:
            room_id = normalize_room_id(raw)
        except ValueError as error:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.window, "Invalid IMVU Room", str(error))
            return
        if room_id not in self.room_ids:
            self.room_ids.append(room_id)
            self._save_rooms()
            self._log(room_id, "Added. Click CONNECT to join this room.")
        else:
            self._log(room_id, "Room is already in the dashboard.")
        self.window.room_panel.room_id_input.clear()
        self.refresh_ui()

    def _next_epoch(self, room_id):
        self._epoch[room_id] = self._epoch.get(room_id, 0) + 1
        return self._epoch[room_id]

    def _current(self, room_id, epoch):
        return self._epoch.get(room_id) == epoch and room_id in self.sessions

    def _allocate_port(self):
        reserved = {session.radio_port for session in self.sessions.values()}
        for port in range(8765, 9300):
            if port in reserved:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check:
                try:
                    check.bind(("127.0.0.1", port))
                except OSError:
                    continue
            return port
        raise RuntimeError("No available radio port between 8765 and 9299.")

    def connect_room(self, room_id):
        try:
            room_id = normalize_room_id(room_id)
        except ValueError:
            return
        if room_id not in self.room_ids:
            self.add_room(room_id)
        if room_id in self.sessions:
            self._log(room_id, "Connection is already active or starting.")
            return
        try:
            # One Chrome instance, independently managed room tabs.
            self.window._ensure_dedicated_bot_chrome()
            port = self._allocate_port()
            session = RoomSession(
                make_room_url(room_id),
                prefix=self.window.settings.get("prefix", "!"),
                user_manager=self.window.user_manager,
                radio_port=port,
            )
        except Exception as error:
            self.states[room_id] = "Error"
            self._log(room_id, f"Cannot start room: {error}")
            self.refresh_ui()
            return

        epoch = self._next_epoch(room_id)
        self.sessions[room_id] = session
        self.states[room_id] = "Opening tab"
        session.radio_server.event_callback = (
            lambda msg, rid=room_id: self.radio_event.emit(rid, msg)
        )
        session.music_controller.now_playing_changed.connect(
            lambda song, rid=room_id, e=epoch: self._song_changed(rid, e, song)
        )
        session.music_controller.queue_changed.connect(self.refresh_ui)
        session.music_controller.status_changed.connect(
            lambda status, rid=room_id, e=epoch: self._session_event(rid, e, status)
        )
        session.music_controller.error_occurred.connect(
            lambda err, rid=room_id, e=epoch: self._session_event(rid, e, "MUSIC ERROR: " + err)
        )
        session.command_handler.async_response.connect(
            lambda user, text, rid=room_id, e=epoch: self._async_response(rid, e, text)
        )
        session.tunnel.tunnel_started.connect(
            lambda url, rid=room_id, e=epoch: self._tunnel_ready(rid, e, url)
        )
        session.tunnel.tunnel_error.connect(
            lambda err, rid=room_id, e=epoch: self._fail(rid, e, "TUNNEL ERROR: " + err)
        )
        session.tunnel.tunnel_stopped.connect(
            lambda rid=room_id, e=epoch: self._tunnel_stopped(rid, e)
        )
        session.tunnel.status_changed.connect(
            lambda text, rid=room_id, e=epoch: self._session_event(rid, e, "Tunnel: " + text)
        )
        self._log(room_id, f"Connecting with private radio port {port}...")
        worker = self.open_worker_class(session.room_url + "/", self.window)
        self.open_workers[room_id] = worker
        worker.opened.connect(
            lambda url, rid=room_id, e=epoch: self._room_opened(rid, e)
        )
        worker.failed.connect(
            lambda err, rid=room_id, e=epoch: self._fail(rid, e, "Open failed: " + err)
        )
        worker.finished.connect(lambda w=worker, rid=room_id: self._worker_finished(self.open_workers, rid, w))
        worker.start()
        self.refresh_ui()

    def _worker_finished(self, registry, room_id, worker):
        if registry.get(room_id) is worker:
            registry.pop(room_id, None)
        if worker in self.retired_workers:
            self.retired_workers.remove(worker)
        worker.deleteLater()

    def _room_opened(self, room_id, epoch):
        if not self._current(room_id, epoch):
            return
        self.states[room_id] = "Joining room"
        session = self.sessions[room_id]
        worker = self.monitor_worker_class(session.room_url + "/", self.window)
        self.chat_workers[room_id] = worker
        worker.ready.connect(
            lambda url, rid=room_id, e=epoch: self._room_joined(rid, e)
        )
        worker.failed.connect(
            lambda url, err, rid=room_id, e=epoch: self._fail(rid, e, "JOIN/LISTENER: " + err)
        )
        worker.message_received.connect(
            lambda url, user, text, rid=room_id, e=epoch: self._chat(rid, e, user, text)
        )
        worker.finished.connect(
            lambda w=worker, rid=room_id, e=epoch: self._chat_finished(rid, e, w)
        )
        worker.start()
        self._log(room_id, "Room tab open. Waiting for IMVU JOIN...")
        self.refresh_ui()

    def _chat_finished(self, room_id, epoch, worker):
        self._worker_finished(self.chat_workers, room_id, worker)
        if self._current(room_id, epoch) and self.states.get(room_id) != "Error":
            self.states[room_id] = "Chat disconnected"
            self._log(room_id, "Chat listener ended. Disconnect and reconnect this room.")
            self.refresh_ui()

    def _room_joined(self, room_id, epoch):
        if not self._current(room_id, epoch):
            return
        session = self.sessions[room_id]
        self.states[room_id] = "Starting private station"
        self._log(room_id, f"JOIN confirmed. Starting radio {session.radio_port} and own tunnel.")
        try:
            session.start_radio()
        except Exception as error:
            self._fail(room_id, epoch, "RADIO: " + str(error))
        self.refresh_ui()

    def _tunnel_stopped(self, room_id, epoch):
        if not self._current(room_id, epoch):
            return
        session = self.sessions[room_id]
        session.stream_url = ""
        self.states[room_id] = "Tunnel disconnected"
        self._log(room_id, "Cloudflare tunnel stopped; radio URL is no longer usable.")
        self.refresh_ui()

    def _tunnel_ready(self, room_id, epoch, url):
        if not self._current(room_id, epoch):
            return
        for other_id, other in self.sessions.items():
            if other_id != room_id and (
                other.stream_url == url or (
                    other.tunnel and other.tunnel.get_stream_url() == url
                )
            ):
                self._fail(
                    room_id, epoch,
                    f"Duplicate Cloudflare radio URL detected with room {other_id}; "
                    "refusing to attach another room to that same stream."
                )
                return
        self._log(room_id, f"Private Cloudflare stream validated: {url}")
        self._load_radio(room_id, epoch, url)

    def _load_radio(self, room_id, epoch, url):
        if not self._current(room_id, epoch):
            return
        current = self.radio_workers.get(room_id)
        if current is not None and current.isRunning():
            self._log(room_id, "Radio LOAD already in progress; please wait.")
            return
        self.states[room_id] = "Loading IMVU radio"
        session = self.sessions[room_id]
        worker = self.radio_worker_class(url, self.window, room_url=session.room_url + "/")
        self.radio_workers[room_id] = worker
        worker.succeeded.connect(
            lambda stream, prev, rid=room_id, e=epoch: self._radio_loaded(rid, e, stream)
        )
        worker.failed.connect(
            lambda err, rid=room_id, e=epoch: self._fail(rid, e, "IMVU RADIO LOAD: " + err)
        )
        worker.finished.connect(
            lambda w=worker, rid=room_id: self._worker_finished(self.radio_workers, rid, w)
        )
        worker.start()
        self.refresh_ui()

    def _radio_loaded(self, room_id, epoch, url):
        if not self._current(room_id, epoch):
            return
        self.sessions[room_id].stream_url = url
        self.states[room_id] = "Connected"
        self._log(room_id, "Own radio link loaded in IMVU. Confirm audio by checking listeners.")
        self.refresh_ui()

    def _fail(self, room_id, epoch, text):
        if not self._current(room_id, epoch):
            return
        self.states[room_id] = "Error"
        self._log(room_id, text)
        self.refresh_ui()

    def _session_event(self, room_id, epoch, status):
        if self._current(room_id, epoch):
            self._log(room_id, status)
            self.refresh_ui()

    def _song_changed(self, room_id, epoch, song):
        if self._current(room_id, epoch):
            self._log(room_id, "Now playing: " + (song or {}).get("title", "Nothing"))
            self.refresh_ui()

    def _on_radio_event(self, room_id, message):
        if room_id in self.sessions:
            self._log(room_id, "RADIO: " + message)
            self.refresh_ui()

    def _async_response(self, room_id, epoch, text):
        if self._current(room_id, epoch):
            self.window.send_bot_response_to_imvu(
                str(text), room_url=make_room_url(room_id)
            )

    def _chat(self, room_id, epoch, username, message):
        if not self._current(room_id, epoch) or not username or not message:
            return
        session = self.sessions[room_id]
        self._log(room_id, f"{username}: {message}")
        try:
            result = session.process(username, message)
        except Exception as error:
            self._log(room_id, f"Command error: {error}")
            return
        if result:
            self.window.send_bot_response_to_imvu(
                result, room_url=make_room_url(room_id)
            )

    def request_song(self, room_id, text):
        session = self.sessions.get(room_id)
        if not session or not session.stream_url:
            self._log(room_id, "Connect this room and wait for radio READY first.")
            return
        query = str(text or "").strip()
        prefix = session.command_handler.prefix
        for lead in (prefix + "p ", prefix + "play "):
            if query.lower().startswith(lead.lower()):
                query = query[len(lead):].strip()
                break
        if not query:
            return
        requester = self.window.settings.get("username") or "CrowBot-Dashboard"
        try:
            result = session.command_handler.handle(prefix + "p " + query, requester)
        except Exception as error:
            self._log(room_id, f"Song request failed: {error}")
            return
        self._log(room_id, "Requested: " + query)
        if result:
            self.window.send_bot_response_to_imvu(
                result, room_url=make_room_url(room_id)
            )
        self.refresh_ui()

    def control_music(self, room_id, action):
        session = self.sessions.get(room_id)
        if not session:
            self._log(room_id, "Room isn't connected.")
            return
        if action == "skip":
            session.music_controller.skip()
        elif action == "stop":
            session.music_controller.stop()
        self._log(room_id, "Selected-room action: " + action)
        self.refresh_ui()

    def reload_radio(self, room_id):
        session = self.sessions.get(room_id)
        if not session:
            self._log(room_id, "Connect the room before reloading radio.")
            return
        url = session.stream_url or (session.tunnel.get_stream_url() if session.tunnel else "")
        if not url:
            self._log(room_id, "Tunnel isn't ready yet; try reconnecting.")
            return
        source = session.radio_server.get_source()
        if source:
            session.radio_server.set_source(source, force_restart=True)
        self._log(room_id, "Reloading this room's own Cloudflare radio URL...")
        self._load_radio(room_id, self._epoch[room_id], url)

    def _retire(self, room_id, registry, timeout=1500):
        worker = registry.pop(room_id, None)
        if worker is None:
            return
        if hasattr(worker, "stop"):
            worker.stop()
        if worker.isRunning():
            worker.wait(timeout)
        # finished() is responsible for deleteLater(). Keep the worker
        # referenced until the queued finished signal is delivered, even
        # when wait() has already returned; don't delete a QThread twice.
        if worker not in self.retired_workers:
            self.retired_workers.append(worker)

    def disconnect_room(self, room_id):
        if room_id not in self.sessions:
            self.states[room_id] = "Offline"
            self.refresh_ui()
            return
        self._next_epoch(room_id)
        self._log(room_id, "Disconnecting only this room...")
        # Clear pending chat messages for this room, not the other rooms.
        target = make_room_url(room_id).rstrip("/")
        self.window._outgoing_chat_queue = [
            (url, message) for url, message in self.window._outgoing_chat_queue
            if str(url or "").rstrip("/") != target
        ]
        self._retire(room_id, self.chat_workers, timeout=2500)
        self._retire(room_id, self.open_workers, timeout=500)
        self._retire(room_id, self.radio_workers, timeout=500)
        session = self.sessions.pop(room_id)
        try:
            session.music_controller.stop()
            session.stop_radio()
        except Exception as error:
            self._log(room_id, f"Shutdown warning: {error}")
        self.states[room_id] = "Offline"
        self._log(room_id, "Disconnected. Other rooms remain active.")
        self.refresh_ui()

    def remove_room(self, room_id):
        self.disconnect_room(room_id)
        if room_id in self.room_ids:
            self.room_ids.remove(room_id)
            self.states.pop(room_id, None)
            self._save_rooms()
            self._log(room_id, "Removed from saved rooms.")
        self.refresh_ui()

    def refresh_ui(self):
        if not hasattr(self.window, "room_panel"):
            return
        records = []
        for room_id in self.room_ids:
            session = self.sessions.get(room_id)
            if session:
                health = session.radio_server.get_health()
                song = session.music_controller.get_current_song()
                if self.states.get(room_id) == "Connected":
                    if health["source_set"]:
                        if health["last_error"]:
                            status = "Audio error"
                        elif not health["audio_recent"]:
                            status = "Audio stalled" if health["source_age"] > 12 else "Preparing audio"
                        else:
                            status = "Playing · broadcasting" if health["clients"] else "Playing · no listeners"
                    else:
                        status = "Ready · idle" if health["clients"] else "Ready · no listeners"
                else:
                    status = self.states.get(room_id, "Connecting")
                records.append({
                    "room_id": room_id, "status": status,
                    "connected": True, "port": session.radio_port,
                    "playing": song.get("title", "Unknown") if song else "—",
                    "queue": session.music_controller.get_queue(),
                    "source": "Music" if health["source_set"] else "Idle",
                    "clients": health["clients"],
                    "stream_url": session.stream_url or (
                        session.tunnel.get_stream_url() if session.tunnel else ""
                    ),
                })
            else:
                records.append({
                    "room_id": room_id, "status": "Offline", "connected": False,
                    "port": "—", "playing": "—", "queue": [],
                    "source": "—", "clients": 0, "stream_url": "",
                })
        self.window.room_panel.set_rooms(records)

    def shutdown(self):
        for room_id in list(self.sessions):
            self.disconnect_room(room_id)
        for worker in list(self.retired_workers):
            if worker.isRunning():
                worker.wait(5000)
