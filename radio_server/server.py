import queue
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config.ffmpeg import get_ffmpeg_path


class RadioStreamServer:

    def __init__(self, host="127.0.0.1", port=8765):
        self.host = host
        self.port = port

        self.server = None
        self.thread = None
        self.broadcast_thread = None
        self.ffmpeg_process = None

        self.current_source = ""
        self.source_generation = 0

        self.running = False
        self.source_changed = threading.Event()

        self.clients = set()
        self.clients_lock = threading.Lock()
        self.broadcast_lock = threading.Lock()

        self._last_client_count = None
        self.event_callback = None
        self.source_set_at = time.monotonic()
        self.last_song_audio_at = 0.0
        self.last_song_audio_generation = -1
        self.last_song_error = ""
        self.last_ffmpeg_returncode = None

    # =========================================================
    # SOURCE MANAGEMENT
    # =========================================================

    def _emit_event(self, message):
        """Broadcast diagnostics via a caller-provided, thread-safe callback."""
        callback = self.event_callback
        if callback:
            try:
                callback(str(message))
            except Exception:
                pass

    def set_source(self, url, force_restart=False):
        url = (url or "").strip()

        with self.broadcast_lock:
            changed = force_restart or url != self.current_source

            if changed:
                self.current_source = url
                self.source_generation += 1
                self.source_set_at = time.monotonic()
                self.last_song_audio_at = 0.0
                self.last_song_audio_generation = -1
                self.last_song_error = ""

            generation = self.source_generation

        if changed:
            print(
                f"Radio source updated (generation {generation}):"
            )
            print(url if url else "<idle>")

            self.source_changed.set()
            self._emit_event(
                f"Source generation {generation}: "
                + ("music encoder restart" if url else "idle/silent MP3")
            )

        return True

    def add_source(self, url):
        return self.set_source(url)

    def set_sources(self, urls):
        clean = [
            (u or "").strip()
            for u in (urls or [])
            if (u or "").strip()
        ]

        return self.set_source(
            clean[0] if clean else ""
        )

    def clear_sources(self):
        return self.set_source("")

    def get_source(self):
        with self.broadcast_lock:
            return self.current_source

    def get_source_state(self):
        with self.broadcast_lock:
            return (
                self.current_source,
                self.source_generation,
            )

    def get_sources(self):
        source = self.get_source()
        return [source] if source else []

    # =========================================================
    # SERVER INFORMATION
    # =========================================================

    def is_running(self):
        return (
            self.server is not None
            and self.running
        )

    def get_client_count(self):
        with self.clients_lock:
            return len(self.clients)

    def get_health(self):
        """Read-only status for the multi-room UI (no streaming side effects)."""
        with self.broadcast_lock:
            source = self.current_source
            generation = self.source_generation
            changed_at = self.source_set_at
            audio_at = self.last_song_audio_at
            audio_generation = self.last_song_audio_generation
            error = self.last_song_error
        return {
            "running": self.is_running(),
            "source_set": bool(source),
            "generation": generation,
            "source_age": max(0.0, time.monotonic() - changed_at),
            "audio_recent": (
                bool(source) and audio_generation == generation
                and bool(audio_at) and time.monotonic() - audio_at < 9
            ),
            "has_song_bytes": bool(audio_at) and audio_generation == generation,
            "clients": self.get_client_count(),
            "last_error": error,
            "ffmpeg_alive": (
                self.ffmpeg_process is not None
                and self.ffmpeg_process.poll() is None
            ),
        }

    def get_local_stream_url(self):
        return (
            f"http://{self.host}:{self.port}/stream.mp3"
        )

    # =========================================================
    # START
    # =========================================================

    def start(self):
        if self.is_running():
            return False

        if not get_ffmpeg_path():
            raise FileNotFoundError(
                "FFmpeg was not found."
            )

        self.running = True
        self.source_changed.clear()

        parent = self

        class StreamHandler(BaseHTTPRequestHandler):

            protocol_version = "HTTP/1.1"

            def _headers(self):
                self.send_header(
                    "Content-Type",
                    "audio/mpeg"
                )
                self.send_header(
                    "Cache-Control",
                    "no-cache"
                )
                self.send_header(
                    "Pragma",
                    "no-cache"
                )
                self.send_header(
                    "Connection",
                    "keep-alive"
                )
                self.send_header(
                    "icy-name",
                    "IMVU Music Bot"
                )
                self.send_header(
                    "icy-genre",
                    "Music"
                )
                self.send_header(
                    "icy-pub",
                    "0"
                )
                self.send_header(
                    "icy-br",
                    "128"
                )
                self.send_header(
                    "Access-Control-Allow-Origin",
                    "*"
                )

            def do_HEAD(self):
                if self.path != "/stream.mp3":
                    self.send_response(404)
                    self.end_headers()
                    return

                self.send_response(200)
                self._headers()
                self.end_headers()

            def do_GET(self):
                if self.path != "/stream.mp3":
                    self.send_response(404)
                    self.end_headers()
                    return

                client_queue = queue.Queue(
                    maxsize=256
                )

                with parent.clients_lock:
                    parent.clients.add(
                        client_queue
                    )

                try:
                    # Because the station now produces idle
                    # MP3 continuously, this should normally
                    # return almost immediately.
                    try:
                        first_data = client_queue.get(
                            timeout=8.0
                        )

                    except queue.Empty:
                        body = (
                            b"Audio not ready yet.\n"
                        )

                        self.send_response(503)
                        self.send_header(
                            "Content-Type",
                            "text/plain; charset=utf-8"
                        )
                        self.send_header(
                            "Content-Length",
                            str(len(body))
                        )
                        self.send_header(
                            "Connection",
                            "close"
                        )
                        self.end_headers()

                        self.wfile.write(body)
                        return

                    if not first_data:
                        return

                    self.send_response(200)
                    self._headers()
                    self.end_headers()
                    self.wfile.flush()

                    print(
                        "Radio client connected: "
                        f"{self.client_address[0]}"
                    )

                    self.wfile.write(first_data)
                    self.wfile.flush()

                    while parent.running:
                        try:
                            data = client_queue.get(
                                timeout=5.0
                            )

                        except queue.Empty:
                            # Normally impossible now because
                            # idle MP3 is always being produced.
                            continue

                        if data is None:
                            break

                        if not data:
                            continue

                        try:
                            self.wfile.write(data)
                            self.wfile.flush()

                        except (
                            BrokenPipeError,
                            ConnectionResetError,
                            ConnectionAbortedError,
                            OSError,
                        ):
                            break

                except (
                    BrokenPipeError,
                    ConnectionResetError,
                    ConnectionAbortedError,
                    OSError,
                ):
                    pass

                except Exception as error:
                    print(
                        "Client stream error:",
                        error
                    )

                finally:
                    with parent.clients_lock:
                        parent.clients.discard(
                            client_queue
                        )

                    print(
                        "Radio client disconnected: "
                        f"{self.client_address[0]}"
                    )

            def do_OPTIONS(self):
                if self.path != "/stream.mp3":
                    self.send_response(404)
                    self.end_headers()
                    return

                self.send_response(204)

                self.send_header(
                    "Access-Control-Allow-Origin",
                    "*"
                )
                self.send_header(
                    "Access-Control-Allow-Methods",
                    "GET, HEAD, OPTIONS"
                )
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "*"
                )

                self.end_headers()

            def log_message(self, format, *args):
                return

        try:
            self.server = ThreadingHTTPServer(
                (self.host, self.port),
                StreamHandler,
            )

            self.server.daemon_threads = True

        except Exception:
            self.running = False
            raise

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="RadioHTTPServer",
            daemon=True,
        )
        self.thread.start()

        self.broadcast_thread = threading.Thread(
            target=self._broadcast_loop,
            name="RadioFFmpegBroadcaster",
            daemon=True,
        )
        self.broadcast_thread.start()

        print("Radio server started:")
        print(self.get_local_stream_url())
        print(
            "Continuous station mode enabled."
        )

        return True

    # =========================================================
    # COMMAND BUILDERS
    # =========================================================

    def _build_song_command(
        self,
        ffmpeg_path,
        source,
    ):
        return [
            ffmpeg_path,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "warning",
            "-re",
            "-i",
            source,
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-b:a",
            "128k",
            "-codec:a",
            "libmp3lame",
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            "-f",
            "mp3",
            "pipe:1",
        ]

    def _build_idle_command(
        self,
        ffmpeg_path,
    ):
        # Generate a real continuous silent MP3 stream.
        #
        # -re is important here. anullsrc is synthetic and
        # otherwise FFmpeg would generate silence as fast as
        # the CPU allows instead of in real time.
        return [
            ffmpeg_path,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "warning",
            "-re",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-b:a",
            "128k",
            "-codec:a",
            "libmp3lame",
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            "-f",
            "mp3",
            "pipe:1",
        ]

    # =========================================================
    # CONTINUOUS BROADCAST LOOP
    # =========================================================

    def _broadcast_loop(self):
        ffmpeg_path = get_ffmpeg_path()

        while self.running:

            (
                source,
                session_generation,
            ) = self.get_source_state()

            idle_mode = not bool(source)

            self.source_changed.clear()

            if idle_mode:
                print(
                    "Radio station idle: "
                    "broadcasting silent MP3 bridge."
                )

                command = self._build_idle_command(
                    ffmpeg_path
                )

            else:
                print(
                    "Starting FFmpeg radio source "
                    f"(generation "
                    f"{session_generation}):"
                )
                print(source)

                command = self._build_song_command(
                    ffmpeg_path,
                    source,
                )

            process = None
            natural_eof = False
            source_was_changed = False
            total_bytes = 0
            first_chunk = True

            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=None,
                    bufsize=0,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if hasattr(subprocess, "CREATE_NO_WINDOW")
                        else 0
                    ),
                )

                self.ffmpeg_process = process

                if idle_mode:
                    print(
                        "Idle FFmpeg started. "
                        f"PID={process.pid}."
                    )
                else:
                    print(
                        "FFmpeg started. "
                        f"PID={process.pid}. "
                        "Waiting for MP3 output..."
                    )

                while self.running:

                    (
                        active_source,
                        active_generation,
                    ) = self.get_source_state()

                    # -------------------------------------------------
                    # IDLE -> SONG
                    # -------------------------------------------------

                    if idle_mode:
                        if active_source:
                            source_was_changed = True

                            print(
                                "New song available. "
                                "Switching station from "
                                "idle audio to music..."
                            )

                            break

                    # -------------------------------------------------
                    # SONG -> DIFFERENT SONG / CLEAR
                    # -------------------------------------------------

                    else:
                        if (
                            active_generation
                            != session_generation
                        ):
                            source_was_changed = True

                            print(
                                "Radio source changed "
                                f"from generation "
                                f"{session_generation} "
                                f"to generation "
                                f"{active_generation}."
                            )

                            break

                    data = process.stdout.read(
                        1024
                    )

                    if not data:
                        if process.poll() is not None:

                            if idle_mode:
                                print(
                                    "Idle FFmpeg exited "
                                    f"with code "
                                    f"{process.returncode}. "
                                    "Restarting idle bridge..."
                                )

                            else:
                                print(
                                    "FFmpeg exited "
                                    f"with code "
                                    f"{process.returncode}."
                                )
                                if process.returncode and total_bytes == 0:
                                    with self.broadcast_lock:
                                        if self.source_generation == session_generation:
                                            self.last_song_error = (
                                                f"FFmpeg exited {process.returncode} "
                                                "without MP3 output"
                                            )
                                    self._emit_event(
                                        f"FFmpeg exited {process.returncode} "
                                        "without MP3 audio."
                                    )

                                (
                                    eof_source,
                                    eof_generation,
                                ) = (
                                    self.get_source_state()
                                )

                                if (
                                    self.running
                                    and
                                    eof_source == source
                                    and
                                    eof_generation
                                    == session_generation
                                ):
                                    natural_eof = True
                                else:
                                    source_was_changed = True

                            break

                        time.sleep(0.01)
                        continue

                    total_bytes += len(data)

                    if first_chunk:
                        first_chunk = False

                        if idle_mode:
                            print(
                                "Continuous idle MP3 "
                                "bridge is active."
                            )
                        else:
                            print(
                                "First MP3 bytes "
                                "received from FFmpeg: "
                                f"{len(data)} bytes"
                            )
                            self._emit_event(
                                f"First song MP3 bytes received "
                                f"(generation {session_generation}, {len(data)} bytes)."
                            )

                    if not idle_mode:
                        with self.broadcast_lock:
                            if self.source_generation == session_generation:
                                self.last_song_audio_at = time.monotonic()
                                self.last_song_audio_generation = session_generation
                    self._broadcast_data(data)

                if (
                    total_bytes
                    and
                    not idle_mode
                ):
                    print(
                        "FFmpeg broadcast session "
                        "produced "
                        f"{total_bytes} MP3 bytes."
                    )

            except Exception as error:
                print("FFmpeg stream error:", error)
                self._emit_event(f"FFmpeg streaming error: {error}")
                with self.broadcast_lock:
                    if self.source_generation == session_generation:
                        self.last_song_error = str(error)

            finally:
                if process:
                    self._terminate_process(
                        process
                    )

                self.ffmpeg_process = None

            # -------------------------------------------------
            # NATURAL TRACK EOF
            #
            # Clear only if this exact generation still owns
            # the source. A newer queued song must never be
            # erased by cleanup from the previous song.
            # -------------------------------------------------

            if (
                self.running
                and
                not idle_mode
                and
                natural_eof
                and
                not source_was_changed
            ):
                cleared = False

                with self.broadcast_lock:
                    if (
                        self.current_source == source
                        and
                        self.source_generation
                        == session_generation
                    ):
                        self.current_source = ""
                        self.source_generation += 1

                        cleared_generation = (
                            self.source_generation
                        )

                        cleared = True

                if cleared:
                    print(
                        "Radio track finished naturally."
                    )
                    print(
                        "Completed generation "
                        f"{session_generation} "
                        "cleared safely."
                    )
                    print(
                        "Station remains online "
                        f"(generation "
                        f"{cleared_generation})."
                    )
                    print(
                        "Switching to continuous "
                        "idle MP3 bridge."
                    )

            if self.running:
                # Very short process transition only.
                # The HTTP client itself remains connected.
                time.sleep(0.01)

    # =========================================================
    # BROADCAST DATA
    # =========================================================

    def _broadcast_data(self, data):
        if not data:
            return

        with self.clients_lock:
            clients = list(
                self.clients
            )

        count = len(clients)

        if count != self._last_client_count:
            self._last_client_count = count

            print(
                "Broadcasting audio to "
                f"{count} client(s)."
            )
            self._emit_event(f"Connected radio listeners: {count}")

        for client_queue in clients:
            try:
                client_queue.put_nowait(
                    data
                )

            except queue.Full:
                # Never let one slow HTTP client block
                # the entire station.
                try:
                    client_queue.get_nowait()

                except queue.Empty:
                    pass

                try:
                    client_queue.put_nowait(
                        data
                    )

                except queue.Full:
                    pass

            except Exception:
                with self.clients_lock:
                    self.clients.discard(
                        client_queue
                    )

    # =========================================================
    # PROCESS TERMINATION
    # =========================================================

    def _terminate_process(
        self,
        process,
    ):
        try:
            if process.poll() is None:
                process.terminate()

        except Exception:
            pass

        try:
            process.wait(
                timeout=2
            )

        except Exception:
            try:
                process.kill()
                process.wait(
                    timeout=1
                )

            except Exception:
                pass

        try:
            if process.stdout:
                process.stdout.close()

        except Exception:
            pass

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):
        self.running = False
        self.source_changed.set()

        if self.ffmpeg_process:
            self._terminate_process(
                self.ffmpeg_process
            )

        self.ffmpeg_process = None

        with self.clients_lock:
            clients = list(
                self.clients
            )

        for client_queue in clients:
            try:
                client_queue.put_nowait(
                    None
                )

            except queue.Full:
                try:
                    client_queue.get_nowait()

                except queue.Empty:
                    pass

                try:
                    client_queue.put_nowait(
                        None
                    )

                except queue.Full:
                    pass

        if self.server:
            try:
                self.server.shutdown()

            except Exception:
                pass

            try:
                self.server.server_close()

            except Exception:
                pass

            self.server = None

        self.thread = None
        self.broadcast_thread = None

        with self.clients_lock:
            self.clients.clear()

        self._last_client_count = None

        print(
            "Radio server stopped."
        )

