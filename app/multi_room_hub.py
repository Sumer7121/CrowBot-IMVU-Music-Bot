"""Room-first runtime: every IMVU room owns an independent music station.

There is deliberately no primary room. Rooms are connected/disconnected
individually, while all Playwright workers share one dedicated Chrome profile.
"""
import socket
import random
import time

from PySide6.QtCore import QObject, Signal, Slot, Qt, QThread, QTimer

from bot.room_ids import make_room_url, normalize_room_id
from bot.room_session import RoomSession
from bot.room_permissions import RoomPermissions
from config.settings import load_settings, save_settings


class MultiRoomHub(QObject):
    radio_event = Signal(str, str)
    radio_finished_event = Signal(str, int, str, int)
    room_joined_event = Signal(str, int)
    room_chat_event = Signal(str, int, str, str, str, str)
    chat_finished_event = Signal(str, int, object)
    # Cloudflare emits from Python validator/reader threads. Its callbacks
    # must be marshalled onto the Qt GUI thread before creating QThreads.
    tunnel_ready_event = Signal(str, int, str)
    tunnel_error_event = Signal(str, int, str)
    tunnel_status_event = Signal(str, int, str)
    tunnel_stopped_event = Signal(str, int)
    imvu_radio_progress_event = Signal(str, int, str)
    imvu_radio_loaded_event = Signal(str, int, str)
    imvu_radio_error_event = Signal(str, int, str)
    imvu_radio_worker_finished_event = Signal(str, object)

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
        self.drop_timers = {}
        self._announced_tracks = {}
        self.retired_workers = []
        self.retired_djs = []
        self._epoch = {}
        self.radio_event.connect(self._on_radio_event, Qt.ConnectionType.AutoConnection)
        self.radio_finished_event.connect(self._radio_track_finished, Qt.ConnectionType.AutoConnection)
        self.room_joined_event.connect(self._room_joined, Qt.ConnectionType.AutoConnection)
        self.room_chat_event.connect(self._chat, Qt.ConnectionType.AutoConnection)
        self.chat_finished_event.connect(self._chat_finished, Qt.ConnectionType.AutoConnection)
        self.tunnel_ready_event.connect(self._tunnel_ready, Qt.ConnectionType.AutoConnection)
        self.tunnel_error_event.connect(self._tunnel_error, Qt.ConnectionType.AutoConnection)
        self.tunnel_status_event.connect(self._tunnel_status, Qt.ConnectionType.AutoConnection)
        self.tunnel_stopped_event.connect(self._tunnel_stopped, Qt.ConnectionType.AutoConnection)
        self.imvu_radio_progress_event.connect(self._imvu_radio_progress, Qt.ConnectionType.AutoConnection)
        self.imvu_radio_loaded_event.connect(self._radio_loaded, Qt.ConnectionType.AutoConnection)
        self.imvu_radio_error_event.connect(self._imvu_radio_failed, Qt.ConnectionType.AutoConnection)
        self.imvu_radio_worker_finished_event.connect(self._imvu_radio_worker_finished, Qt.ConnectionType.AutoConnection)
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
        session.radio_server.track_finished_callback = (
            lambda source, generation, rid=room_id, e=epoch:
            self.radio_finished_event.emit(rid, e, source, generation)
        )
        session.music_controller.now_playing_changed.connect(
            lambda song, rid=room_id, e=epoch: self._song_changed(rid, e, song)
        )
        session.music_controller.queue_changed.connect(self.refresh_ui)
        session.dj.status_changed.connect(
            lambda message, rid=room_id, e=epoch: self._session_event(
                rid, e, "DJ: " + str(message)
            )
        )
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
            lambda url, rid=room_id, e=epoch: self.tunnel_ready_event.emit(rid, e, url)
        )
        session.tunnel.tunnel_error.connect(
            lambda err, rid=room_id, e=epoch: self.tunnel_error_event.emit(rid, e, str(err))
        )
        session.tunnel.tunnel_stopped.connect(
            lambda rid=room_id, e=epoch: self.tunnel_stopped_event.emit(rid, e)
        )
        session.tunnel.status_changed.connect(
            lambda text, rid=room_id, e=epoch: self.tunnel_status_event.emit(rid, e, str(text))
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
            lambda url, rid=room_id, e=epoch: self.room_joined_event.emit(rid, e)
        )
        worker.failed.connect(
            lambda url, err, rid=room_id, e=epoch: self._fail(rid, e, "JOIN/LISTENER: " + err)
        )
        worker.message_received.connect(
            lambda url, user, text, account, identity, rid=room_id, e=epoch:
            self.room_chat_event.emit(rid, e, user, text, account, identity)
        )
        worker.finished.connect(
            lambda w=worker, rid=room_id, e=epoch:
            self.chat_finished_event.emit(rid, e, w)
        )
        worker.start()
        self._log(room_id, "Room tab open. Waiting for IMVU JOIN...")
        self.refresh_ui()

    @Slot(str, int, object)
    def _chat_finished(self, room_id, epoch, worker):
        self._worker_finished(self.chat_workers, room_id, worker)
        if self._current(room_id, epoch):
            # Never keep posting auto-drops when this room's chat listener
            # died, even if radio errors had already changed its status.
            self._stop_room_drops(room_id)
            if self.states.get(room_id) != "Error":
                self.states[room_id] = "Chat disconnected"
            self._log(room_id, "Chat listener ended. Pet drops paused until reconnect.")
            self.refresh_ui()

    @Slot(str, int)
    def _room_joined(self, room_id, epoch):
        if not self._current(room_id, epoch):
            return
        session = self.sessions[room_id]
        self.states[room_id] = "Starting private station"
        self._log(room_id, f"JOIN confirmed. Starting radio {session.radio_port} and own tunnel.")
        self._start_room_drops(room_id, epoch)
        try:
            session.start_radio()
        except Exception as error:
            self._fail(room_id, epoch, "RADIO: " + str(error))
        self.refresh_ui()

    def _send_room_announcement(self, room_id, epoch, message):
        """All automatic chat responses require an explicit IMVU room URL."""
        if not self._current(room_id, epoch):
            return
        clean = " ".join(str(message or "").split())
        if not clean:
            return
        try:
            self.window.send_bot_response_to_imvu(
                clean[:300], room_url=make_room_url(room_id)
            )
        except Exception as error:
            self._log(room_id, "IMVU announcement queue failed: " + str(error))

    def _start_room_drops(self, room_id, epoch):
        """Create a separate automatic cat/dog-drop timer for every joined room."""
        if not self._current(room_id, epoch):
            return
        self._stop_room_drops(room_id)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda rid=room_id, e=epoch: self._spawn_room_drop(rid, e)
        )
        self.drop_timers[room_id] = timer
        self._schedule_room_drop(room_id, epoch, initial=True)
        self._log(room_id, "Automatic cat/dog drops enabled. Use !drops or !petdrop.")

    def _schedule_room_drop(self, room_id, epoch, initial=False):
        if not self._current(room_id, epoch):
            return
        timer = self.drop_timers.get(room_id)
        if timer is None:
            return
        # First drop is fairly quick; follow-up drops are spaced to avoid
        # interrupting IMVU chat and music every minute.
        milliseconds = random.randint(60_000, 90_000) if initial else random.randint(
            6 * 60_000, 10 * 60_000
        )
        self.sessions[room_id].command_handler.next_auto_drop_at = (
            time.monotonic() + milliseconds / 1000.0
        )
        timer.start(milliseconds)

    def _spawn_room_drop(self, room_id, epoch):
        if not self._current(room_id, epoch):
            return
        session = self.sessions[room_id]
        try:
            session.command_handler.collectibles.expired()
            message = session.command_handler.collectibles.spawn()
            if message:
                self._log(room_id, "PET DROP: " + " ".join(message.split()))
                self._send_room_announcement(room_id, epoch, message)
            else:
                self._log(room_id, "Pet drop postponed: an existing wild pet is active.")
        except Exception as error:
            self._log(room_id, "PET DROP ERROR: " + str(error))
        finally:
            self._schedule_room_drop(room_id, epoch)

    def _stop_room_drops(self, room_id):
        timer = self.drop_timers.pop(room_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        session = self.sessions.get(room_id)
        if session is not None:
            session.command_handler.next_auto_drop_at = None

    @Slot(str, int, str)
    def _tunnel_error(self, room_id, epoch, message):
        self._fail(room_id, epoch, "TUNNEL ERROR: " + message)

    @Slot(str, int, str)
    def _tunnel_status(self, room_id, epoch, message):
        self._session_event(room_id, epoch, "Tunnel: " + message)

    @Slot(str, int)
    def _tunnel_stopped(self, room_id, epoch):
        if not self._current(room_id, epoch):
            return
        session = self.sessions[room_id]
        session.stream_url = ""
        session.dj.set_ready(False)
        self.states[room_id] = "Tunnel disconnected"
        self._log(room_id, "Cloudflare tunnel stopped; radio URL is no longer usable.")
        self.refresh_ui()

    @Slot(str, int, str)
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
        """Start the IMVU LOAD worker on the main Qt thread, never in CF's thread."""
        if not self._current(room_id, epoch):
            return
        try:
            if QThread.currentThread() != self.thread():
                raise RuntimeError("Radio LOAD dispatched outside the Qt GUI thread")
            current = self.radio_workers.get(room_id)
            if current is not None and current.isRunning():
                self._log(room_id, "Radio LOAD already in progress; please wait.")
                return

            self.states[room_id] = "Loading IMVU radio"
            session = self.sessions[room_id]
            self._log(room_id, f"RADIO LOAD: Opening Media controls in IMVU room {room_id}...")
            worker = self.radio_worker_class(
                url, self.window, room_url=session.room_url + "/"
            )
            self.radio_workers[room_id] = worker
            if hasattr(worker, "progress"):
                worker.progress.connect(
                    lambda message, rid=room_id, e=epoch:
                    self.imvu_radio_progress_event.emit(rid, e, str(message))
                )
            worker.succeeded.connect(
                lambda stream, prev, rid=room_id, e=epoch:
                self.imvu_radio_loaded_event.emit(rid, e, stream)
            )
            worker.failed.connect(
                lambda err, rid=room_id, e=epoch:
                self.imvu_radio_error_event.emit(rid, e, str(err))
            )
            worker.finished.connect(
                lambda w=worker, rid=room_id:
                self.imvu_radio_worker_finished_event.emit(rid, w)
            )
            worker.start()
            self._log(room_id, "RADIO LOAD: Worker started, awaiting IMVU confirmation...")
            QTimer.singleShot(
                75000,
                lambda rid=room_id, e=epoch, w=worker:
                self._check_radio_load_timeout(rid, e, w)
            )
            self.refresh_ui()
        except Exception as error:
            self._fail(
                room_id, epoch,
                f"RADIO LOAD FAILED TO START: {type(error).__name__}: {error}"
            )

    def _check_radio_load_timeout(self, room_id, epoch, worker):
        if not self._current(room_id, epoch):
            return
        if (self.radio_workers.get(room_id) is worker
                and self.states.get(room_id) == "Loading IMVU radio"):
            self._fail(
                room_id, epoch,
                "IMVU radio LOAD timed out. Use RELOAD RADIO and check the "
                "selected room's Radio Streaming controls and permissions."
            )

    @Slot(str, int, str)
    def _imvu_radio_progress(self, room_id, epoch, message):
        self._session_event(room_id, epoch, "RADIO LOAD: " + message)

    @Slot(str, int, str)
    def _imvu_radio_failed(self, room_id, epoch, error):
        self._fail(room_id, epoch, "IMVU RADIO LOAD: " + error)

    @Slot(str, object)
    def _imvu_radio_worker_finished(self, room_id, worker):
        self._worker_finished(self.radio_workers, room_id, worker)

    @Slot(str, int, str)
    def _radio_loaded(self, room_id, epoch, url):
        if not self._current(room_id, epoch):
            return
        self.sessions[room_id].stream_url = url
        self.states[room_id] = "Connected"
        self.sessions[room_id].dj.set_ready(True)
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
            if not song:
                self._announced_tracks.pop(room_id, None)
            else:
                session = self.sessions[room_id]
                fingerprint = (
                    id(song),
                    str(song.get("url") or ""),
                    getattr(session.music_controller, "_radio_generation", None),
                )
                if (session.stream_url
                        and self._announced_tracks.get(room_id) != fingerprint):
                    self._announced_tracks[room_id] = fingerprint
                    title = " ".join(str(song.get("title") or "Unknown").split())[:150]
                    if song.get("dj_auto"):
                        artist = str(song.get("dj_artist") or "").strip()
                        suffix = (" | Artist: " + artist[:65]) if artist else ""
                        announcement = "🎧 DJ NOW PLAYING: " + title + suffix
                    else:
                        announcement = "🎵 NOW PLAYING: " + title
                    self._send_room_announcement(room_id, epoch, announcement)
            if song and song.get("cache_master_file"):
                mode = "MASTER CACHE HIT" if song.get("cache_hit") else "MASTER CACHE SAVED"
                self._log(
                    room_id,
                    f"{mode}: {song.get('id', 'unknown')} | "
                    f"room copy: {str(song.get('temporary_file', '')).rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}"
                )
            self.refresh_ui()

    @Slot(str, int, str, int)
    def _radio_track_finished(self, room_id, epoch, url, generation):
        if not self._current(room_id, epoch):
            return
        session = self.sessions[room_id]
        if session.music_controller.on_radio_track_finished(url, generation):
            self._log(room_id, "AutoDJ: Public song ended; next room track requested.")
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

    @Slot(str, int, str, str, str, str)
    def _chat(self, room_id, epoch, username, message, account_username="", user_id=""):
        if not self._current(room_id, epoch) or not username or not message:
            return
        session = self.sessions[room_id]
        self._log(room_id, f"{username}: {message}")
        # A chat-only listener cannot see silent joins reliably, so greet
        # users at their first observed message per connected room.
        identity = username.casefold()
        if identity not in session.welcomed_users:
            session.welcomed_users.add(identity)
            welcome = session.permissions.welcome_message(username)
            if welcome:
                self._send_room_announcement(room_id, epoch, welcome)
        try:
            result = session.process(
                username, message, account_username=account_username,
                user_id=user_id,
            )
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

    def set_room_owner(self, room_id, username):
        if room_id not in self.room_ids:
            return
        try:
            policy = (self.sessions[room_id].permissions
                      if room_id in self.sessions else RoomPermissions(room_id))
            policy.set_owner_from_dashboard(username)
        except ValueError as error:
            self._log(room_id, "OWNER ERROR: " + str(error))
            return
        self._log(
            room_id, "Trusted dashboard configured room owner: " + policy.owner
        )
        self.refresh_ui()

    def approve_owner_link(self, room_id):
        """Trusted local approval of a pending IMVU account-ID claim."""
        session = self.sessions.get(room_id)
        if session is None:
            self._log(room_id, "Connect this room before approving an owner link.")
            return
        pending = getattr(session, "pending_owner_link", None)
        if not pending:
            self._log(room_id, "No pending owner link. Ask the owner to send !linkowner.")
            return
        if time.monotonic() - pending["created_at"] > 300:
            session.pending_owner_link = None
            self._log(room_id, "Owner link expired. Send !linkowner again.")
            self.refresh_ui()
            return
        from PySide6.QtWidgets import QMessageBox
        question = (
            f"Approve this IMVU chat account as @{session.permissions.owner}?\n\n"
            f"Room: {room_id}\n"
            f"Chat display: {pending['display']}\n"
            f"Account ID: {pending['user_id']}\n\n"
            "Verify the actual room owner's identity in IMVU before approving. "
            "A display name alone is not proof of identity."
        )
        answer = QMessageBox.question(
            self.window, "Approve verified room owner", question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            session.permissions.link_owner_from_dashboard(pending["user_id"])
        except ValueError as error:
            self._log(room_id, "OWNER LINK ERROR: " + str(error))
            return
        session.pending_owner_link = None
        self._log(room_id, "Room owner account link verified: @" + session.permissions.owner)
        self.refresh_ui()

    def artist_dj(self, room_id, artist):
        session = self.sessions.get(room_id)
        if not session or not session.stream_url:
            self._log(room_id, "Connect this room's radio before starting DJ.")
            return
        try:
            label = session.dj.set_artist(artist)
        except ValueError as error:
            self._log(room_id, str(error))
            return
        self._log(room_id, "Artist radio enabled: " + label)
        self.refresh_ui()

    def set_autoplay(self, room_id, enabled):
        session = self.sessions.get(room_id)
        if not session or not session.stream_url:
            self._log(room_id, "Connect this room's radio first.")
            return
        mode = session.dj.set_autoplay(enabled)
        self._log(room_id, "Autoplay set to: " + mode)
        self.refresh_ui()

    def set_language(self, room_id, language):
        session = self.sessions.get(room_id)
        if not session:
            self._log(room_id, "Connect this room before selecting a DJ language.")
            return
        try:
            mode = session.dj.set_language(language)
        except ValueError as error:
            self._log(room_id, str(error))
            return
        self._log(room_id, "Language preference updated: " + mode)
        self.refresh_ui()

    def stop_dj(self, room_id):
        session = self.sessions.get(room_id)
        if session:
            session.dj.off()
            self._log(room_id, "Artist DJ and autoplay switched off.")
            self.refresh_ui()

    def control_music(self, room_id, action):
        session = self.sessions.get(room_id)
        if not session:
            self._log(room_id, "Room isn't connected.")
            return
        if action == "skip":
            session.music_controller.skip()
        elif action == "stop":
            session.dj.set_autoplay(False)
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
        self._stop_room_drops(room_id)
        self._announced_tracks.pop(room_id, None)
        self._log(room_id, "Disconnecting only this room...")
        # Clear pending chat messages for this room, not the other rooms.
        target = make_room_url(room_id).rstrip("/")
        outgoing = getattr(self.window, "_outgoing_chat_queue", None)
        if outgoing is not None:
            self.window._outgoing_chat_queue = [
                (url, message) for url, message in outgoing
                if str(url or "").rstrip("/") != target
            ]
        self._retire(room_id, self.chat_workers, timeout=2500)
        self._retire(room_id, self.open_workers, timeout=500)
        self._retire(room_id, self.radio_workers, timeout=500)
        session = self.sessions.pop(room_id)
        try:
            session.dj.off()
            session.music_controller.stop()
            session.stop_radio()
            worker = getattr(session.dj, "_worker", None)
            if worker is not None and worker.isRunning():
                self.retired_djs.append(session.dj)
                worker.finished.connect(
                    lambda dj=session.dj: self._release_dj(dj)
                )
        except Exception as error:
            self._log(room_id, f"Shutdown warning: {error}")
        self.states[room_id] = "Offline"
        self._log(room_id, "Disconnected. Other rooms remain active.")
        self.refresh_ui()

    def _release_dj(self, dj):
        if dj in self.retired_djs:
            self.retired_djs.remove(dj)

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
            policy = session.permissions if session else RoomPermissions(room_id)
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
                    "owner": policy.owner,
                    "owner_linked": bool(getattr(policy, "owner_user_id", "")),
                    "pending_owner_link": dict(getattr(session, "pending_owner_link", None) or {}) if session else {},
                    "admins": list(policy.mods.values()),
                    "connected": True, "port": session.radio_port,
                    "dj_mode": session.dj.label,
                    "dj_activity": session.dj.last_activity,
                    "dj_error": session.dj.last_error,
                    "dj_language": session.dj.language,
                    "dj_match_current": session.dj.match_current_language,
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
                    "room_id": room_id, "status": "Offline",
                    "owner": policy.owner,
                    "owner_linked": bool(getattr(policy, "owner_user_id", "")),
                    "pending_owner_link": dict(getattr(session, "pending_owner_link", None) or {}) if session else {},
                    "admins": list(policy.mods.values()),
                    "connected": False,
                    "dj_mode": "DJ OFF", "dj_activity": "Offline",
                    "dj_error": "", "dj_language": "",
                    "dj_match_current": False,
                    "port": "—", "playing": "—", "queue": [],
                    "source": "—", "clients": 0, "stream_url": "",
                })
        self.window.room_panel.set_rooms(records)
        ready = sum(1 for rid in self.sessions if self.states.get(rid) == "Connected")
        connecting = len(self.sessions) - ready
        title = f"●  {ready} CONNECTED / {len(self.room_ids)} ROOMS"
        if connecting:
            title += f" · {connecting} STARTING / NEED ATTENTION"
        if hasattr(self.window, "connection_status"):
            self.window.connection_status.setText(title)

    def shutdown(self):
        for room_id in list(self.sessions):
            self.disconnect_room(room_id)
        for worker in list(self.retired_workers):
            if worker.isRunning():
                worker.wait(5000)
        for dj in list(self.retired_djs):
            worker = dj._worker
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(10000)
