import json
from music.download_proxy import proxy_arguments, private_proxy_error
import uuid
import shutil
import subprocess
import sys
import threading
import time

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from config.runtime_paths import get_youtube_temp_dir
from music.track_library import RoomTrackLibrary, is_valid_mp3
from urllib.parse import quote, unquote
from music.song_ranking import ranked_candidates, candidate_score, query_parts


# =============================================================
# CONFIGURATION
# =============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEMP_DIR = get_youtube_temp_dir()
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------
# TEMPORARY AUDIO SERVER
# -------------------------------------------------------------

HTTP_HOST = "127.0.0.1"
# Let Windows select an unused ephemeral port. Fixed 8766 collided with
# CrowBot's second room radio, leaving secondary rooms silent.
HTTP_PORT = 0


# -------------------------------------------------------------
# FFMPEG
# -------------------------------------------------------------

BUNDLED_FFMPEG = PROJECT_ROOT / "bin" / "ffmpeg.exe"

if BUNDLED_FFMPEG.exists():
    FFMPEG_DIR = BUNDLED_FFMPEG.parent
else:
    system_ffmpeg = shutil.which("ffmpeg")

    if system_ffmpeg:
        FFMPEG_DIR = Path(system_ffmpeg).parent
    else:
        FFMPEG_DIR = PROJECT_ROOT / "bin"


def _run_cancellable(command, timeout, capture_output=False, cancel_check=None):
    with proxy_arguments() as arguments:
        result = _run_cancellable_process(
            command + arguments, timeout,
            capture_output=capture_output or bool(arguments),
            cancel_check=cancel_check,
        )
        if arguments:
            # Never print raw subprocess diagnostics with proxy credentials.
            result.stderr = private_proxy_error(result.stderr) if result.returncode else ""
            if not capture_output:
                result.stdout = None
        return result


def _run_cancellable_process(command, timeout, capture_output=False, cancel_check=None):
    """Run yt-dlp while allowing room disconnect to interrupt slow downloads."""
    flags = (
        subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    )
    if cancel_check is None:
        return subprocess.run(
            command,
            capture_output=capture_output,
            text=capture_output,
            encoding="utf-8" if capture_output else None,
            errors="replace" if capture_output else None,
            timeout=timeout,
            creationflags=flags,
        )
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        text=capture_output,
        encoding="utf-8" if capture_output else None,
        errors="replace" if capture_output else None,
        creationflags=flags,
    )
    end = time.monotonic() + timeout
    try:
        while True:
            if cancel_check():
                raise RuntimeError("AutoDJ request cancelled.")
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                stdout, stderr = proc.communicate(timeout=min(0.4, remaining))
                return subprocess.CompletedProcess(
                    command, proc.returncode, stdout, stderr
                )
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
        raise


# =============================================================
# REUSABLE HTTP SERVER
# =============================================================

class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# =============================================================
# YOUTUBE PROVIDER
# =============================================================

class YouTubeOwnedProvider:

    def __init__(self):
        self.http_server = None
        self.http_thread = None
        self.http_port = None

        self.lock = threading.RLock()

        self.track_info = {}
        self.cleanup_started = set()
        self.library = RoomTrackLibrary(TEMP_DIR)
        self.library.prune_master()

        self._purge_old_temp_files()


    # =========================================================
    # YT-DLP COMMAND
    # =========================================================

    def _ytdlp(self):
        """
        Return the yt-dlp command used by CrowBot.

        IMPORTANT:
        In a PyInstaller build, sys.executable is CrowBot.exe.
        Calling:

            sys.executable -m yt_dlp

        would therefore start another CrowBot process.

        CrowBot uses its bundled standalone yt-dlp.exe instead.
        """

        # Packaged CrowBot.exe
        if getattr(sys, "frozen", False):

            app_root = Path(
                sys.executable
            ).resolve().parent

            bundled = (
                app_root
                / "bin"
                / "yt-dlp.exe"
            )

            if bundled.exists():
                return [str(bundled)]

            raise RuntimeError(
                "CrowBot could not find its bundled "
                f"yt-dlp executable: {bundled}"
            )

        # Source / VS Code
        project_ytdlp = (
            PROJECT_ROOT
            / "bin"
            / "yt-dlp.exe"
        )

        if project_ytdlp.exists():
            return [str(project_ytdlp)]

        executable = shutil.which(
            "yt-dlp"
        )

        if executable:
            return [executable]

        # Safe only when running from normal Python.
        return [
            sys.executable,
            "-m",
            "yt_dlp",
        ]


    # =========================================================
    # FAST YT-DLP SEARCH
    # =========================================================

    def search_candidates(
        self,
        query,
        limit=10,
        cancel_check=None,
    ):

        query = str(query or "").strip()

        if not query:
            return []

        print()
        print("========================================")
        print(f"YTDLP SEARCH: {query}")
        print("========================================")

        command = (
            self._ytdlp()
            + [
                f"ytsearch{limit}:{query}",
                "--flat-playlist",
                "--dump-json",
                "--skip-download",
                "--no-warnings",
                "--socket-timeout",
                "15",
            ]
        )

        try:
            process = _run_cancellable(
                command, timeout=45, capture_output=True,
                cancel_check=cancel_check,
            )

        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "yt-dlp YouTube search timed out."
            ) from error

        if process.returncode != 0:
            raise RuntimeError(
                process.stderr.strip()
                or "yt-dlp YouTube search failed."
            )

        results = []

        for line in process.stdout.splitlines():

            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            video_id = str(
                data.get("id", "")
            ).strip()

            if not video_id:
                continue

            title = str(
                data.get("title", "Unknown")
            ).strip()

            channel = str(
                data.get("channel")
                or data.get("uploader")
                or "Unknown"
            ).strip()

            channel_id = str(
                data.get("channel_id")
                or data.get("uploader_id")
                or ""
            ).strip()

            duration = data.get("duration", 0)

            try:
                duration = int(duration or 0)
            except (TypeError, ValueError):
                duration = 0

            youtube_url = (
                data.get("webpage_url")
                or data.get("url")
            )

            if (
                not youtube_url
                or not str(youtube_url).startswith("http")
            ):
                youtube_url = (
                    "https://www.youtube.com/"
                    f"watch?v={video_id}"
                )

            results.append(
                {
                    "id": video_id,
                    "title": title,
                    "channel": channel,
                    "channel_id": channel_id,
                    "duration": duration,
                    "youtube_url": youtube_url,
                }
            )

        return results


    # =========================================================
    # GET EXACT VIDEO METADATA
    # =========================================================

    def _get_video_metadata(
        self,
        candidate,
        cancel_check=None,
    ):

        youtube_url = candidate["youtube_url"]

        command = (
            self._ytdlp()
            + [
                youtube_url,
                "--skip-download",
                "--no-playlist",
                "--dump-single-json",
                "--no-warnings",
                "--socket-timeout",
                "15",
            ]
        )

        try:
            process = _run_cancellable(
                command,
                timeout=22,
                capture_output=True,
                cancel_check=cancel_check,
            )

        except subprocess.TimeoutExpired:
            return None

        if process.returncode != 0:
            # A failed metadata lookup used to disappear silently, making a
            # cloud-only provider failure look like endless loading.
            reason = str(process.stderr or "")
            if "confirm" in reason.lower() and "bot" in reason.lower():
                raise RuntimeError("YouTube requires verification from this server; this track cannot be loaded.")
            if "429" in reason or "Too Many Requests" in reason:
                raise RuntimeError("YouTube is rate-limiting this server. Try again later.")
            print("YTDLP METADATA FAILED: " + reason[-1200:])
            return None

        try:
            data = json.loads(process.stdout)
        except json.JSONDecodeError:
            return None

        metadata = dict(candidate)

        metadata["channel"] = str(
            data.get("channel")
            or data.get("uploader")
            or candidate.get("channel", "Unknown")
        ).strip()

        metadata["channel_id"] = str(
            data.get("channel_id")
            or data.get("uploader_id")
            or candidate.get("channel_id", "")
        ).strip()

        metadata["title"] = str(
            data.get("title")
            or candidate.get("title", "Unknown")
        ).strip()

        # YouTube can expose language and music artist in video metadata.
        # AutoDJ uses these fields when present, and its language-specific
        # search query when they are not available.
        metadata["language"] = str(
            data.get("language") or candidate.get("language") or ""
        ).strip()
        metadata["artist"] = str(
            data.get("artist") or candidate.get("artist") or ""
        ).strip()

        duration = (
            data.get("duration")
            or candidate.get("duration", 0)
        )

        try:
            duration = int(duration or 0)
        except (TypeError, ValueError):
            duration = 0

        metadata["duration"] = duration

        return metadata


    # =========================================================
    # MAIN SEARCH
    # =========================================================

    def search(self, query, requested_by=None, room_id="legacy", session_key="legacy",
               cancel_check=None, progress_callback=None):
        """Resolve a cached request first; otherwise rank safe YouTube candidates."""
        if progress_callback:
            progress_callback("Checking master song library...")
        cached = self.library.find_query(query)
        if cached:
            print(f"RESOLVER: MASTER INDEX HIT: {query}")
            if progress_callback:
                progress_callback("Master cache hit — copying song into this room...")
            track = self._prepare_track(
                cached, query, requested_by, room_id=room_id,
                session_key=session_key, cancel_check=cancel_check
            )
            if progress_callback:
                progress_callback("Cached song verified and ready for room playback.")
            return track
        song, artist = query_parts(query)
        searches = [f"{artist} {song} official audio" if artist else f"{song} official audio"]
        searches.append(query)
        attempted = set()
        last_error = None
        for search_text in searches:
            if cancel_check and cancel_check():
                raise RuntimeError("Music request was cancelled.")
            if search_text.casefold() in attempted:
                continue
            attempted.add(search_text.casefold())
            if progress_callback:
                progress_callback("Searching YouTube: " + search_text[:70])
            try:
                candidates = ranked_candidates(
                    self.search_candidates(
                        search_text, limit=15, cancel_check=cancel_check
                    ), query
                )
            except Exception as error:
                print(f"YTDLP SEARCH ERROR: {error}")
                continue
            for candidate in candidates[:8]:
                if cancel_check and cancel_check():
                    raise RuntimeError("Music request was cancelled.")
                metadata = self._get_video_metadata(
                    candidate, cancel_check=cancel_check
                )
                if not metadata:
                    continue
                # Never download a candidate unless FULL metadata still
                # matches the song/artist and duration is known.
                duration = metadata.get("duration", 0)
                if not duration or candidate_score(metadata, query) is None:
                    print(f"YTDLP: Skipping non-song: {metadata.get('title')}")
                    continue
                try:
                    if progress_callback:
                        progress_callback(
                            "Preparing MP3: " + str(metadata.get("title", "Track"))[:70]
                        )
                    track = self._prepare_track(
                        metadata, query, requested_by, room_id=room_id,
                        session_key=session_key, cancel_check=cancel_check
                    )
                    self.library.index_query(query, metadata)
                    if progress_callback:
                        progress_callback("Song verified and ready for room playback.")
                    return track
                except Exception as error:
                    last_error = error
                    if cancel_check and cancel_check():
                        raise RuntimeError("Music request was cancelled.") from error
                    print(f"YTDLP: Candidate failed, trying next: {error}")
                    continue
        if last_error is not None:
            raise RuntimeError(
                "No playable track could be prepared: " + str(last_error)
            ) from last_error
        return None


    # =========================================================
    # PREPARE TRACK
    # =========================================================

    def _prepare_track(
        self,
        candidate,
        query,
        requested_by,
        cancel_check=None,
        room_id="legacy",
        session_key="legacy",
    ):

        video_id = candidate["id"]
        title = candidate["title"]
        channel = candidate["channel"]

        duration = candidate.get(
            "duration",
            0,
        )

        youtube_url = candidate["youtube_url"]

        print()
        print("YTDLP: Preparing audio...")
        was_in_master = is_valid_mp3(self.library.master_path(video_id))

        master_path = self._download_mp3(
            video_id,
            youtube_url,
            cancel_check=cancel_check,
        )
        if cancel_check and cancel_check():
            raise RuntimeError("Music preparation cancelled.")
        mp3_path = self.library.stage_for_room(
            video_id, room_id, session_key
        )
        try:
            self._start_http_server()
            local_url = self._build_local_url(mp3_path)
            self._verify_local_song_url(local_url, mp3_path)
        except Exception:
            # Failed preparation must not leave unplayable files queued.
            self.library.release_track(mp3_path, room_id, session_key)
            raise
        print(
            f"ROOM MUSIC READY: room={room_id}; master={master_path.name}; "
            f"copy={mp3_path.name}; url={local_url}"
        )

        return {
            "id": video_id,
            "title": title,
            "track_title": title,
            "artist": candidate.get("artist") or channel,
            "language": str(candidate.get("language") or ""),
            "duration": duration,
            "url": local_url,
            "youtube_url": youtube_url,
            "provider": "youtube",
            "source": "youtube",
            "search_query": query,
            "requested_by": requested_by,
            "temporary_file": str(mp3_path),
            "room_id": room_id,
            "room_session": session_key,
            "cache_master_file": str(master_path),
            "cache_hit": bool(was_in_master),
        }


    # =========================================================
    # DOWNLOAD / CONVERT
    # =========================================================

    def _download_mp3(self, video_id, youtube_url, cancel_check=None):
        """Reuse validated masters; download and publish atomically on miss."""
        def downloader(workspace, token):
            output_template = str(workspace / (token + ".%(ext)s"))
            command = self._ytdlp() + [
                youtube_url,
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "192K",
                "--ffmpeg-location", str(FFMPEG_DIR),
                "--output", output_template,
                "--no-playlist", "--no-warnings",
            ]
            print(f"YTDLP: Downloading new master MP3 for {video_id}...")
            process = _run_cancellable(
                command, timeout=600, cancel_check=cancel_check
            )
            if process.returncode != 0:
                raise RuntimeError(
                    f"yt-dlp failed for {video_id} (exit {process.returncode})."
                )
            path = workspace / (token + ".mp3")
            if not is_valid_mp3(path):
                raise RuntimeError(f"yt-dlp returned missing or invalid MP3 for {video_id}.")
            return path

        path, reused = self.library.get_or_download(
            video_id, downloader, cancel_check=cancel_check
        )
        if reused:
            print(f"ROOM MUSIC: Reusing master MP3 {path.name}")
        else:
            self.library.prune_master()
        return path


    # =========================================================
    # TEMP HTTP SERVER :8766
    # =========================================================

    def _start_http_server(self):

        with self.lock:

            if self.http_server:
                return

            provider = self

            class Handler(SimpleHTTPRequestHandler):

                def __init__(
                    self,
                    *args,
                    **kwargs,
                ):
                    super().__init__(
                        *args,
                        directory=str(TEMP_DIR),
                        **kwargs,
                    )

                def log_message(
                    self,
                    format,
                    *args,
                ):
                    print(
                        "YOUTUBE HTTP:",
                        format % args,
                    )

                def do_GET(self):

                    filename = (
                        self.path
                        .split("?", 1)[0]
                        .lstrip("/")
                    )

                    filename = unquote(
                        filename
                    )

                    # Session files are cleaned after playback by RoomSession,
                    # never by time-based HTTP request callbacks.
                    provider._file_requested(
                        filename
                    )

                    try:
                        super().do_GET()

                    except (
                        ConnectionAbortedError,
                        ConnectionResetError,
                        BrokenPipeError,
                    ):
                        pass

            try:
                self.http_server = ReusableHTTPServer(
                    (
                        HTTP_HOST,
                        HTTP_PORT,
                    ),
                    Handler,
                )

            except OSError as error:
                raise RuntimeError(
                    "Could not start temporary "
                    "YouTube server on port "
                    f"{HTTP_PORT}. "
                    "Close any old test server first. "
                    f"{error}"
                ) from error

            self.http_port = self.http_server.server_address[1]
            self.http_thread = threading.Thread(
                target=self.http_server.serve_forever,
                daemon=True,
                name="YouTubeTempHTTP",
            )

            self.http_thread.start()

            print()
            print(
                "YTDLP: Temporary HTTP "
                "server started:"
            )

            print(
                f"http://{HTTP_HOST}:"
                f"{self.http_port}/"
            )


    # =========================================================
    # LOCAL URL
    # =========================================================

    def _build_local_url(self, mp3_path):
        # Preserve rooms/<room-id>/<session-key>/<unique-track>.mp3 path;
        # using only the basename caused 404 for staged room copies.
        path = Path(mp3_path).resolve()
        relative = path.relative_to(TEMP_DIR.resolve()).as_posix()
        return (
            f"http://{HTTP_HOST}:{self.http_port}/"
            + quote(relative, safe="/")
        )

    def _verify_local_song_url(self, url, path):
        """A song isn't 'ready' until the local HTTP service returns its file."""
        from urllib.request import Request, urlopen
        if not is_valid_mp3(path):
            raise RuntimeError(f"Song is not a valid MP3: {path}")
        try:
            with urlopen(Request(url, method="HEAD"), timeout=7) as response:
                size = int(response.headers.get("Content-Length") or 0)
                if response.status != 200 or size < 2048:
                    raise RuntimeError(
                        f"Local MP3 server returned HTTP {response.status} / {size} bytes"
                    )
        except Exception as error:
            raise RuntimeError(
                f"Room music file failed local HTTP check: {error}"
            ) from error

    def cleanup_room_files(self, room_id, session_key):
        self.library.cleanup_room(room_id, session_key)

    def release_room_track(self, path, room_id, session_key):
        self.library.release_track(path, room_id, session_key)


    # =========================================================
    # TRACK REGISTRATION
    # =========================================================

    def _register_track(
        self,
        mp3_path,
        duration,
    ):

        filename = Path(
            mp3_path
        ).name

        with self.lock:

            self.track_info[filename] = {
                "path": Path(mp3_path),
                "duration": int(
                    duration or 0
                ),
            }


    # =========================================================
    # FILE REQUEST
    # =========================================================

    def _file_requested(
        self,
        filename,
    ):

        with self.lock:

            info = self.track_info.get(
                filename
            )

            if not info:
                return

            if filename in self.cleanup_started:
                return

            self.cleanup_started.add(
                filename
            )

        threading.Thread(
            target=self._cleanup_after_playback,
            args=(
                filename,
                info["path"],
                info["duration"],
            ),
            daemon=True,
            name=(
                "YouTubeCleanup-"
                f"{filename}"
            ),
        ).start()


    # =========================================================
    # AUTOMATIC CLEANUP
    # =========================================================

    def _cleanup_after_playback(
        self,
        filename,
        path,
        duration,
    ):

        if duration > 0:
            wait_seconds = duration + 60
        else:
            wait_seconds = 3600

        print(
            "YOUTUBE CLEANUP: "
            f"{filename} scheduled "
            f"in {wait_seconds}s."
        )

        time.sleep(wait_seconds)

        deleted = False

        # Windows may temporarily keep the file open.
        # Retry for up to 12 minutes.
        for attempt in range(1, 721):

            try:

                if not path.exists():
                    deleted = True
                    break

                path.unlink()

                print(
                    "YOUTUBE CLEANUP: "
                    f"Deleted {filename}"
                )

                deleted = True
                break

            except PermissionError:

                if attempt == 1:
                    print(
                        "YOUTUBE CLEANUP: "
                        f"{filename} is still in use. "
                        "Waiting..."
                    )

                time.sleep(1)

            except OSError as error:

                print(
                    "YOUTUBE CLEANUP: "
                    f"Could not delete "
                    f"{filename}: {error}"
                )

                time.sleep(1)

        with self.lock:

            self.track_info.pop(
                filename,
                None,
            )

            self.cleanup_started.discard(
                filename
            )

        if not deleted and path.exists():

            print(
                "YOUTUBE CLEANUP: "
                f"Giving up deleting "
                f"{filename} for now."
            )


    # =========================================================
    # PURGE OLD TEMP FILES
    # =========================================================

    def _purge_old_temp_files(
        self,
        max_age_seconds=21600,
    ):

        try:
            now = time.time()

            for path in TEMP_DIR.iterdir():

                if not path.is_file():
                    continue

                try:
                    age = (
                        now
                        - path.stat().st_mtime
                    )

                    if age >= max_age_seconds:
                        path.unlink()

                        print(
                            "YOUTUBE CLEANUP: "
                            f"Removed old temp file: "
                            f"{path.name}"
                        )

                except OSError:
                    pass

        except OSError:
            pass


    # =========================================================
    # MANUAL CLEANUP
    # =========================================================

    def cleanup(self):

        print()
        print(
            "YTDLP: Cleaning temporary "
            "YouTube provider..."
        )

        with self.lock:

            server = self.http_server

            self.http_server = None
            self.http_thread = None
            self.http_port = None

        if server:

            try:
                server.shutdown()
            except Exception:
                pass

            try:
                server.server_close()
            except Exception:
                pass

        print(
            "YTDLP: Temporary server stopped."
        )


    # =========================================================
    # CLOSE
    # =========================================================

    def close(self):
        self.cleanup()


    # =========================================================
    # DESTRUCTOR
    # =========================================================

    def __del__(self):

        try:
            self.cleanup()
        except Exception:
            pass




# All CommandHandlers and AutoDJ workers in one CrowBot process reuse this
# provider's temporary HTTP station. Radio stations remain per-room.
_shared_provider = None
_shared_provider_lock = threading.Lock()


def get_shared_youtube_provider():
    global _shared_provider
    with _shared_provider_lock:
        if _shared_provider is None:
            _shared_provider = YouTubeOwnedProvider()
        return _shared_provider
