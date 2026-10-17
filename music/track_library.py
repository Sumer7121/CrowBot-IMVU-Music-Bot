"""Persistent MP3 master cache and isolated, disposable room playback copies.

Each YouTube video ID has one validated master MP3. Every connected room
session copies that master into its own directory, so no room can delete or
overwrite another room's active media. Only room copies are removed on room
disconnect; master entries are reused until pruned by bounded cache limits.
"""
import os
import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from config.runtime_paths import get_youtube_temp_dir

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{2,80}$")
MIN_MP3_BYTES = 2048
MAX_MASTER_BYTES = 2 * 1024 ** 3
MAX_MASTER_AGE_DAYS = 30


def _safe_token(value, label):
    token = str(value or "").strip()
    if not SAFE_ID.fullmatch(token):
        raise ValueError(f"Invalid {label}: only letters, numbers, _ and - are allowed.")
    return token


def is_valid_mp3(path):
    """Reject missing, partial, empty or obviously non-MP3 downloads."""
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size < MIN_MP3_BYTES:
            return False
        with path.open("rb") as handle:
            header = handle.read(4)
        return header[:3] == b"ID3" or (
            len(header) >= 2 and header[0] == 0xFF
            and header[1] & 0xE0 == 0xE0
        )
    except OSError:
        return False


class RoomTrackLibrary:
    def __init__(self, root=None):
        self.root = Path(root) if root else get_youtube_temp_dir()
        self.master = self.root / "master"
        self.rooms = self.root / "rooms"
        self.incoming = self.root / "incoming"
        for directory in (self.root, self.master, self.rooms, self.incoming):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._video_locks = {}
        self.index_path = self.master / "song_index.json"
        try:
            value = json.loads(self.index_path.read_text(encoding="utf-8"))
            self._query_index = value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            self._query_index = {}

    def master_path(self, video_id):
        return self.master / (_safe_token(video_id, "video ID") + ".mp3")

    def room_path(self, room_id, session_key):
        return self.rooms / _safe_token(room_id, "room ID") / _safe_token(
            session_key, "room session"
        )

    @staticmethod
    def _query_key(query):
        return " ".join(str(query or "").casefold().split())[:250]

    def find_query(self, query):
        """Look for previously downloaded and indexed songs before YouTube."""
        key = self._query_key(query)
        with self._lock:
            candidate = self._query_index.get(key)
            if not isinstance(candidate, dict):
                return None
            try:
                if is_valid_mp3(self.master_path(candidate.get("id"))):
                    return dict(candidate)
            except ValueError:
                pass
            return None

    def index_query(self, query, candidate):
        key = self._query_key(query)
        video_id = str(candidate.get("id") or "")
        if not key or not video_id or not is_valid_mp3(self.master_path(video_id)):
            return
        record = {
            field: candidate.get(field) for field in
            ("id", "title", "channel", "duration", "youtube_url",
             "artist", "language")
        }
        with self._lock:
            self._query_index[key] = record
            # Keep index bounded; a source file is always independently checked.
            if len(self._query_index) > 5000:
                self._query_index = dict(list(self._query_index.items())[-4000:])
            tmp = self.index_path.with_name(
                self.index_path.name + "." + uuid.uuid4().hex + ".tmp"
            )
            try:
                tmp.write_text(
                    json.dumps(self._query_index, ensure_ascii=False),
                    encoding="utf-8",
                )
                os.replace(tmp, self.index_path)
            finally:
                tmp.unlink(missing_ok=True)

    def _video_lock(self, video_id):
        with self._lock:
            return self._video_locks.setdefault(video_id, threading.Lock())

    def get_or_download(self, video_id, download, cancel_check=None):
        """Call download(incoming_directory, unique_token) only on cache misses."""
        video_id = _safe_token(video_id, "video ID")
        target = self.master_path(video_id)
        with self._video_lock(video_id):
            if is_valid_mp3(target):
                os.utime(target, None)
                print(f"MUSIC MASTER CACHE HIT: {video_id} ({target.stat().st_size} bytes)")
                return target, True
            if target.exists():
                try:
                    target.unlink()
                except OSError as error:
                    raise RuntimeError(f"Cannot remove corrupt master MP3: {error}")
            if cancel_check and cancel_check():
                raise RuntimeError("Music download cancelled.")
            token = uuid.uuid4().hex
            workspace = self.incoming / token
            workspace.mkdir(parents=True)
            partial = self.master / (video_id + "." + token + ".part")
            try:
                downloaded = Path(download(workspace, token))
                if not downloaded.is_file() or not downloaded.resolve().is_relative_to(
                    workspace.resolve()
                ):
                    raise RuntimeError("Music downloader did not return a safe workspace file.")
                if not is_valid_mp3(downloaded):
                    raise RuntimeError("Downloaded file is missing or invalid MP3 audio.")
                if cancel_check and cancel_check():
                    raise RuntimeError("Music download cancelled.")
                shutil.copyfile(downloaded, partial)
                if not is_valid_mp3(partial):
                    raise RuntimeError("MP3 failed master-cache verification.")
                os.replace(partial, target)
                print(f"MUSIC MASTER CACHE SAVED: {video_id} ({target.stat().st_size} bytes)")
                return target, False
            finally:
                if partial.exists():
                    partial.unlink(missing_ok=True)
                shutil.rmtree(workspace, ignore_errors=True)

    def stage_for_room(self, video_id, room_id, session_key):
        """Copy a validated master, atomically, into this room session only."""
        video_id = _safe_token(video_id, "video ID")
        folder = self.room_path(room_id, session_key)
        folder.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:12]
        target = folder / f"{video_id}-{token}.mp3"
        temp = folder / f"{video_id}-{token}.part"
        try:
            # Prevent concurrent LRU eviction while another room copies a
            # master file. Every room stages under the same video-ID lock.
            with self._video_lock(video_id):
                master = self.master_path(video_id)
                if not is_valid_mp3(master):
                    raise RuntimeError(f"Master MP3 missing or invalid: {video_id}")
                shutil.copyfile(master, temp)
            if not is_valid_mp3(temp):
                raise RuntimeError("Room MP3 copy failed validation.")
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        print(f"ROOM MUSIC COPY: room={room_id} file={target.name}")
        return target

    def release_track(self, path, room_id, session_key):
        """Only permit deleting copies inside the owning session's folder."""
        if not path:
            return
        folder = self.room_path(room_id, session_key).resolve()
        track = Path(path).resolve()
        if track.parent != folder or track.suffix.lower() != ".mp3":
            return
        try:
            track.unlink(missing_ok=True)
        except OSError as error:
            print(f"ROOM MUSIC CLEANUP RETRY LATER: {track}: {error}")

    def cleanup_room(self, room_id, session_key):
        folder = self.room_path(room_id, session_key)
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            print(f"ROOM MUSIC FOLDER CLEARED: {room_id} / {session_key}")
        parent = folder.parent
        try:
            parent.rmdir()
        except OSError:
            pass

    def prune_master(self, max_bytes=MAX_MASTER_BYTES,
                     max_age_days=MAX_MASTER_AGE_DAYS):
        """LRU/age based; never delete room copies or downloads in progress."""
        now = time.time()
        removed = 0
        with self._lock:
            candidates = sorted(
                (p for p in self.master.glob("*.mp3") if p.is_file()),
                key=lambda p: p.stat().st_mtime
            )
            total = sum(p.stat().st_size for p in candidates)
            for path in candidates:
                size = path.stat().st_size
                expired = now - path.stat().st_mtime > max_age_days * 86400
                if not expired and total <= max_bytes:
                    continue
                video_id = path.stem
                lock = self._video_lock(video_id)
                if not lock.acquire(blocking=False):
                    continue
                try:
                    if path.exists():
                        path.unlink()
                        removed += 1
                        total -= size
                except OSError:
                    pass
                finally:
                    lock.release()
        return removed
