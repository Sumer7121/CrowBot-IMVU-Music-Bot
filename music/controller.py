from PySide6.QtCore import QObject, Signal

from music.queue import MusicQueue
from music.player import MusicPlayer


class MusicController(QObject):

    now_playing_changed = Signal(object)
    queue_changed = Signal()
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):

        super().__init__()

        self.queue = MusicQueue()

        self.player = MusicPlayer()

        self.radio_server = None

        self.player.song_started.connect(
            self.on_song_started
        )

        self.player.song_finished.connect(
            self.on_song_finished
        )

        self.player.playback_error.connect(
            self.on_playback_error
        )

    # =========================================================
    # RADIO SERVER
    # =========================================================

    def attach_radio_server(
        self,
        radio_server
    ):

        self.radio_server = radio_server

    # =========================================================
    # ADD SONG
    # =========================================================

    def add_song(
        self,
        song
    ):

        if not song:

            return False

        url = song.get(
            "url"
        )

        if not url:

            self.error_occurred.emit(
                "Track has no audio URL."
            )

            return False

        self.queue.add(
            song
        )

        self.queue_changed.emit()

        if (
            self.queue.get_current_song()
            is None
        ):

            return self.play_next()

        else:

            title = song.get(
                "title",
                "Unknown"
            )

            self.status_changed.emit(
                f"Added to queue: {title}"
            )

        return True

    # =========================================================
    # PLAY NEXT
    # =========================================================

    def play_next(self):

        song = (
            self.queue.next_song()
        )

        if not song:

            self.now_playing_changed.emit(
                None
            )

            self.status_changed.emit(
                "Queue is empty."
            )

            if self.radio_server:

                if self.radio_server.is_running():

                    self.radio_server.clear_sources()

            self.queue_changed.emit()

            return False

        url = song.get(
            "url"
        )

        title = song.get(
            "title",
            "Unknown"
        )

        if not url:

            self.error_occurred.emit(
                "Track has no audio URL."
            )

            self.queue_changed.emit()

            return False

        # -----------------------------------------------------
        # Update public radio source
        # -----------------------------------------------------

        if self.radio_server:

            if not self.radio_server.is_running():

                try:

                    self.radio_server.set_source(url, force_restart=True)

                    self.radio_server.start()

                except Exception as error:

                    self.error_occurred.emit(
                        f"Radio server error: {error}"
                    )

                    return False

            else:

                self.radio_server.set_source(url, force_restart=True)

        # -----------------------------------------------------
        # Local playback
        # -----------------------------------------------------

        self.player.play(
            url,
            title
        )

        self.now_playing_changed.emit(
            song
        )

        self.queue_changed.emit()

        self.status_changed.emit(
            f"Now playing: {title}"
        )

        return True

    # =========================================================
    # PLAY
    # =========================================================

    def play(self):

        current = (
            self.queue.get_current_song()
        )

        if current:

            self.player.resume()

            self.queue.is_paused = False

            self.status_changed.emit(
                "Playback resumed."
            )

            return True

        return self.play_next()

    # =========================================================
    # PAUSE
    # =========================================================

    def pause(self):
        current = self.queue.get_current_song()
        if not current:
            self.status_changed.emit("Nothing is currently playing.")
            return False

        # The public station is separate from muted local QMediaPlayer audio.
        # Switch listeners to idle MP3 while paused; do not let music keep
        # broadcasting to IMVU after users request !pause.
        if self.radio_server and self.radio_server.is_running():
            self.radio_server.clear_sources()
            self.player.stop()
            self.status_changed.emit(
                "Music paused in this room (resume restarts the track)."
            )
        else:
            self.player.pause()
            self.status_changed.emit("Music paused.")
        self.queue.pause()
        return True

    def resume(self):
        current = self.queue.get_current_song()
        if not current:
            self.status_changed.emit("Nothing is currently playing.")
            return False

        if self.radio_server and self.radio_server.is_running():
            url = current.get("url")
            if not url:
                self.error_occurred.emit("Cannot resume: track URL missing.")
                return False
            self.radio_server.set_source(url, force_restart=True)
            self.player.play(url, current.get("title", "Unknown"))
            self.status_changed.emit(
                "Music resumed in this room (track restarted)."
            )
        else:
            self.player.resume()
            self.status_changed.emit("Music resumed.")
        self.queue.resume()
        return True

    # =========================================================
    # SKIP
    # =========================================================

    def skip(self):

        if not self.queue.get_current_song():

            self.status_changed.emit(
                "Nothing is currently playing."
            )

            return False

        self.player.stop()

        result = self.play_next()

        if result:

            self.status_changed.emit(
                "Skipped to next track."
            )

        return result

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):

        self.player.stop()

        self.queue.stop()

        if self.radio_server:

            if self.radio_server.is_running():

                self.radio_server.clear_sources()

        self.now_playing_changed.emit(
            None
        )

        self.queue_changed.emit()

        self.status_changed.emit(
            "Music stopped."
        )

    # =========================================================
    # CLEAR QUEUE
    # =========================================================

    def clear_queue(self):

        self.queue.clear()

        self.queue_changed.emit()

        self.status_changed.emit(
            "Queue cleared."
        )

    # =========================================================
    # REMOVE SONG
    # =========================================================

    def remove_song(
        self,
        index
    ):

        song = (
            self.queue.remove(
                index
            )
        )

        if song:

            self.queue_changed.emit()

            title = song.get(
                "title",
                "Unknown"
            )

            self.status_changed.emit(
                f"Removed: {title}"
            )

            return song

        self.error_occurred.emit(
            "Invalid queue number."
        )

        return None

    # =========================================================
    # VOLUME
    # =========================================================

    def set_volume(
        self,
        volume
    ):

        self.player.set_volume(
            volume
        )

    # =========================================================
    # GET CURRENT
    # =========================================================

    def get_current_song(self):

        return (
            self.queue.get_current_song()
        )

    # =========================================================
    # GET QUEUE
    # =========================================================

    def get_queue(self):

        return (
            self.queue.get_queue()
        )

    # =========================================================
    # PLAYING STATUS
    # =========================================================

    def is_playing(self):

        return (
            self.player.is_playing()
        )

    # =========================================================
    # SONG STARTED
    # =========================================================

    def on_song_started(
        self,
        song_name
    ):

        self.status_changed.emit(
            f"Started: {song_name}"
        )

    # =========================================================
    # SONG FINISHED
    # =========================================================

    def on_song_finished(self):

        self.status_changed.emit(
            "Song finished."
        )

        self.play_next()

    # =========================================================
    # PLAYBACK ERROR
    # =========================================================

    def on_playback_error(
        self,
        message
    ):

        self.error_occurred.emit(
            f"Playback error: {message}"
        )