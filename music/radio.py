from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from urllib.parse import urlparse


class RadioStreamManager(QObject):

    stream_started = Signal(str)
    stream_stopped = Signal()
    stream_error = Signal(str)
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.current_url = ""
        self.playing = False

        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()

        self.player.setAudioOutput(
            self.audio_output
        )

        self.audio_output.setVolume(
            0.0
        )

        self.player.errorOccurred.connect(
            self.on_error
        )

        self.player.mediaStatusChanged.connect(
            self.on_media_status_changed
        )

    def is_valid_url(
        self,
        url
    ):

        if not url:
            return False

        try:

            parsed = urlparse(
                url.strip()
            )

            return (
                parsed.scheme
                in ("http", "https")
                and bool(parsed.netloc)
            )

        except Exception:

            return False

    def set_volume(
        self,
        volume
    ):

        volume = max(
            0.0,
            min(
                1.0,
                volume
            )
        )

        self.audio_output.setVolume(
            volume
        )

    def start(
        self,
        url
    ):

        url = (
            url or ""
        ).strip()

        if not self.is_valid_url(
            url
        ):

            self.stream_error.emit(
                "Invalid radio stream URL."
            )

            return False

        self.current_url = url

        self.player.setSource(
            QUrl(url)
        )

        self.player.play()

        self.playing = True

        self.status_changed.emit(
            "Radio stream starting..."
        )

        self.stream_started.emit(
            url
        )

        return True

    def stop(self):

        self.player.stop()

        self.playing = False

        self.status_changed.emit(
            "Radio stream stopped."
        )

        self.stream_stopped.emit()

    def pause(self):

        if not self.playing:
            return False

        self.player.pause()

        self.status_changed.emit(
            "Radio stream paused."
        )

        return True

    def resume(self):

        if not self.current_url:
            return False

        self.player.play()

        self.playing = True

        self.status_changed.emit(
            "Radio stream resumed."
        )

        return True

    def is_playing(self):

        return (
            self.playing
            and
            self.player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )

    def get_current_url(self):

        return self.current_url

    def on_media_status_changed(
        self,
        status
    ):

        if status == QMediaPlayer.MediaStatus.InvalidMedia:

            self.playing = False

            self.stream_error.emit(
                "The radio stream could not be opened."
            )

        elif status == QMediaPlayer.MediaStatus.EndOfMedia:

            self.playing = False

            self.status_changed.emit(
                "Radio stream ended."
            )

    def on_error(
        self,
        error,
        error_string
    ):

        if error != QMediaPlayer.Error.NoError:

            self.playing = False

            message = (
                error_string
                or
                "Unknown radio stream error."
            )

            self.stream_error.emit(
                message
            )
