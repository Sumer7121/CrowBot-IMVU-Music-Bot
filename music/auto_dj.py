"""Per-room artist DJ, YouTube discovery autoplay, and language-aware radio.

The search stage uses public YouTube search metadata, not a claim to every song
in an artist's discography. A room has one worker at a time, one prepared song
ahead, a recent-ID exclusion list and its own settings. YouTube availability
and recording-language metadata depend on the upstream provider.
"""
import random
import re
import time

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from music.youtube_owned import get_shared_youtube_provider


LANGUAGES = {
    "english": "en", "hindi": "hi", "telugu": "te", "tamil": "ta",
    "malayalam": "ml", "kannada": "kn", "punjabi": "pa", "bengali": "bn",
    "urdu": "ur", "spanish": "es", "french": "fr", "arabic": "ar",
    "korean": "ko", "japanese": "ja", "portuguese": "pt",
    "german": "de", "italian": "it", "marathi": "mr",
}
# YouTube sometimes returns regional tags such as 'en-US', or none at all.


def normalize_language(value):
    name = str(value or "").strip().casefold()
    if name in ("", "off", "any", "all", "auto", "none"):
        return ""
    for language, code in LANGUAGES.items():
        if name in (language, code):
            return language
    raise ValueError(
        "Unsupported language. Try: " + ", ".join(LANGUAGES)
        + ". Use !language off for any."
    )


def detect_song_language(track):
    """Best-effort music language from a video tag, title or search query."""
    track = track or {}
    text = (
        str(track.get("title") or "") + " " +
        str(track.get("search_query") or "")
    ).casefold()
    for language in LANGUAGES:
        if re.search(r"\b" + re.escape(language) + r"\b", text):
            return language
    # Strongly distinctive scripts; Devanagari can also be Marathi, so
    # explicit metadata takes precedence over that ambiguous script.
    scripts = (
        (r"[\u0C00-\u0C7F]", "telugu"),
        (r"[\u0B80-\u0BFF]", "tamil"),
        (r"[\u0D00-\u0D7F]", "malayalam"),
        (r"[\u0C80-\u0CFF]", "kannada"),
        (r"[\u0980-\u09FF]", "bengali"),
        (r"[\u0600-\u06FF]", "urdu"),
        (r"[\uAC00-\uD7AF]", "korean"),
        (r"[\u3040-\u30FF]", "japanese"),
    )
    for expression, language in scripts:
        if re.search(expression, text):
            return language
    code = str(track.get("dj_language") or track.get("language") or "")
    code = code.strip().casefold().split("-")[0]
    for language, expected in LANGUAGES.items():
        if code in (language, expected):
            return language
    return ""


def search_queries(artist="", language="", current_title="", round_index=0):
    """Rotate discovery terms, excluding previous songs by YouTube ID."""
    artist = str(artist or "").strip()
    language = normalize_language(language)
    language_text = (language + " ") if language else ""
    if artist:
        variants = (
            f"{artist} {language_text}official audio songs",
            f"{artist} {language_text}popular songs original audio",
            f"{artist} {language_text}top hits music",
            f"{artist} {language_text}songs full audio",
        )
    else:
        seed = str(current_title or "").strip()
        variants = (
            f"{language_text}popular music songs official audio",
            f"{language_text}new music songs official audio",
            f"{language_text}top hits songs official audio",
            f"{language_text}best music songs official audio",
        )
        if seed:
            variants = (f"{language_text}songs similar to {seed} official audio",) + variants
    offset = round_index % len(variants)
    return (variants[offset], variants[(offset + 1) % len(variants)])


def candidate_allowed(candidate, artist="", language=""):
    """Conservative metadata filter; a language label is not audio analysis."""
    title = str(candidate.get("title") or "").strip()
    channel = str(candidate.get("channel") or "").strip()
    duration = candidate.get("duration") or 0
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        return False
    if duration < 65 or duration > 900:
        return False
    normalized = (title + " " + channel + " " +
                  str(candidate.get("artist") or "")).casefold()
    if any(term in normalized for term in (
        "reaction to", "reaction video", "movie trailer", "full movie",
        "interview with", "behind the scenes", "tutorial", "8d audio",
        "sped up", "slowed reverb", "nightcore", "shorts",
    )):
        return False
    if artist:
        pieces = [piece for piece in re.split(r"\s+", artist.casefold()) if len(piece) > 1]
        if not pieces or not all(piece in normalized for piece in pieces):
            return False
    language = normalize_language(language)
    declared = str(candidate.get("language") or "").casefold().split("-")[0]
    if language and declared and declared != LANGUAGES[language]:
        return False
    return True


class DJFetchWorker(QThread):
    prepared = Signal(object)
    failed = Signal(str)

    def __init__(self, artist, language, seen_ids, current_title, round_index,
                 room_id="legacy", session_key="legacy"):
        super().__init__()
        self.artist = artist
        self.language = language
        self.room_id = room_id
        self.session_key = session_key
        self.seen_ids = set(seen_ids)
        self.current_title = current_title
        self.round_index = round_index

    def run(self):
        try:
            provider = get_shared_youtube_provider()
            candidates = []
            for phrase in search_queries(
                self.artist, self.language, self.current_title, self.round_index
            ):
                if self.isInterruptionRequested():
                    return
                found = provider.search_candidates(
                    phrase, limit=35, cancel_check=self.isInterruptionRequested
                )
                candidates.extend(found)
            random.shuffle(candidates)
            checked = set()
            failures = []
            for candidate in candidates:
                if self.isInterruptionRequested():
                    return
                identity = str(candidate.get("id") or "")
                if not identity or identity in self.seen_ids or identity in checked:
                    continue
                checked.add(identity)
                if not candidate_allowed(candidate, self.artist, self.language):
                    continue
                metadata = provider._get_video_metadata(
                    candidate, cancel_check=self.isInterruptionRequested
                )
                if metadata is None or not candidate_allowed(
                    metadata, self.artist, self.language
                ):
                    continue
                try:
                    track = provider._prepare_track(
                        metadata,
                        "CrowBot AutoDJ",
                        "CrowBot DJ",
                        cancel_check=self.isInterruptionRequested,
                        room_id=self.room_id,
                        session_key=self.session_key,
                    )
                except Exception as error:
                    failures.append(str(error))
                    if len(failures) >= 3:
                        break
                    continue
                track["dj_auto"] = True
                track["dj_language"] = self.language
                track["dj_artist"] = self.artist
                self.prepared.emit(track)
                return
            if self.isInterruptionRequested():
                return
            reason = (failures[-1] if failures else
                      "No new matching playable songs in this YouTube search.")
            self.failed.emit(reason)
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))


class AutoDJ(QObject):
    status_changed = Signal(str)

    def __init__(self, music_controller, room_id="legacy", session_key="legacy"):
        super().__init__()
        self.music_controller = music_controller
        self.room_id = room_id
        self.session_key = session_key
        self.artist = ""
        self.language = ""
        self.match_current_language = False
        self._detected_language = ""
        self.enabled = False
        self._generation = 0
        self._worker = None
        self._retired_workers = []
        self._seen = []
        self._round = 0
        self._retry_at = 0.0
        self._closed = False
        self.radio_ready = False

        self._timer = QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._maybe_fill)
        self.music_controller.now_playing_changed.connect(self._observe_song)
        self.music_controller.now_playing_changed.connect(self._maybe_fill)
        self.music_controller.queue_changed.connect(self._maybe_fill)

    def set_ready(self, ready):
        was_ready = self.radio_ready
        self.radio_ready = bool(ready)
        if was_ready and not self.radio_ready:
            self._generation += 1
            if self._worker is not None:
                self._worker.requestInterruption()
        if self.radio_ready:
            if not self._timer.isActive():
                self._timer.start()
            self._maybe_fill()
        else:
            self._timer.stop()

    @property
    def mode(self):
        if not self.enabled:
            return "OFF"
        if self.artist:
            return "ARTIST DJ: " + self.artist
        return "YOUTUBE AUTOPLAY"

    @property
    def label(self):
        if self.match_current_language:
            return self.mode + " · Match current: " + (
                self._detected_language.title() if self._detected_language
                else "Unknown (any until detected)"
            )
        return self.mode + (
            " · " + self.language.title() if self.language else " · Any language"
        )

    def _observe_song(self, song):
        if not song or not self.match_current_language:
            return
        detected = detect_song_language(song)
        if detected:
            self._detected_language = detected

    def set_artist(self, artist):
        text = " ".join(str(artist or "").strip().split())
        if not text or len(text) > 80:
            raise ValueError("Specify an artist name (1–80 characters).")
        self._change()
        self.artist = text
        self.enabled = True
        self._drop_prefetched()
        self.status_changed.emit("Artist radio ON: " + self.label)
        self._maybe_fill()
        return self.label

    def set_autoplay(self, enabled):
        self._change()
        self.enabled = bool(enabled)
        if not self.enabled:
            self._drop_prefetched()
        self.status_changed.emit("Autoplay " + ("ON: " + self.label if enabled else "OFF"))
        self._maybe_fill()
        return self.label

    def set_language(self, language):
        text = str(language or "").strip().casefold()
        auto = text in ("match", "match current", "match current song", "auto")
        selected = "" if auto else normalize_language(language)
        if selected != self.language or auto != self.match_current_language:
            self._change()
            self.language = selected
            self.match_current_language = auto
            self._detected_language = ""
            if auto:
                self._observe_song(self.music_controller.get_current_song())
            self._drop_prefetched()
        self.status_changed.emit("Music discovery language: " + self.label)
        self._maybe_fill()
        return self.label

    def off(self):
        self._change()
        self.enabled = False
        self.artist = ""
        self._drop_prefetched()
        self.status_changed.emit("Artist DJ and autoplay OFF.")
        return self.label

    def _drop_prefetched(self):
        # Preserve user-requested songs; only remove AutoDJ's old selections.
        pending = self.music_controller.get_queue()
        if not pending:
            return
        for index in reversed(range(len(pending))):
            if pending[index].get("dj_auto"):
                self.music_controller.remove_song(index)

    def _change(self):
        self._generation += 1
        self._seen.clear()
        self._round = 0
        self._retry_at = 0
        if self._worker is not None:
            self._worker.requestInterruption()

    def _maybe_fill(self, *args):
        if (self._closed or not self.radio_ready or not self.enabled
                or self._worker is not None):
            return
        if time.monotonic() < self._retry_at:
            return
        if self.music_controller.get_queue():
            return
        current = self.music_controller.get_current_song()
        title = (current or {}).get("title", "")
        effective_language = (
            self._detected_language if self.match_current_language
            else self.language
        )
        worker = DJFetchWorker(
            self.artist, effective_language, tuple(self._seen),
            title, self._round, self.room_id, self.session_key
        )
        generation = self._generation
        self._worker = worker
        self._round += 1
        worker.prepared.connect(
            lambda track, g=generation: self._on_prepared(g, track)
        )
        worker.failed.connect(
            lambda error, g=generation: self._on_failed(g, error)
        )
        worker.finished.connect(lambda w=worker: self._finished(w))
        worker.start()
        self.status_changed.emit("AutoDJ discovering next track: " + self.label)

    def _on_prepared(self, generation, track):
        if (self._closed or not self.enabled or not self.radio_ready
                or generation != self._generation):
            return
        video_id = str(track.get("id") or "")
        if video_id:
            self._seen.append(video_id)
            self._seen = self._seen[-250:]
        self.status_changed.emit(
            "AutoDJ selected: " + str(track.get("title", "Unknown"))
        )
        self.music_controller.add_song(track)

    def _on_failed(self, generation, error):
        if self._closed or generation != self._generation:
            return
        self._retry_at = time.monotonic() + 25
        self.status_changed.emit("AutoDJ search failed; retrying in 25s: " + str(error))

    def _finished(self, worker):
        if self._worker is worker:
            self._worker = None
        if worker in self._retired_workers:
            self._retired_workers.remove(worker)
        worker.deleteLater()
        if not self._closed:
            QTimer.singleShot(500, self._maybe_fill)

    def shutdown(self):
        self._closed = True
        self._timer.stop()
        self._change()
        worker = self._worker
        if worker is not None:
            worker.requestInterruption()
            # Do not block the GUI on a slow YouTube subprocess.
            self._retired_workers.append(worker)
        return worker
