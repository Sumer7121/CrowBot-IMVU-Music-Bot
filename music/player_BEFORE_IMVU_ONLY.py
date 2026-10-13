from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class MusicPlayer(QObject):

    song_started = Signal(str)
    song_finished = Signal()
    playback_error = Signal(str)

    def __init__(self):
        super().__init__()

        self.audio_output = QAudioOutput()

        self.player = QMediaPlayer()

        self.player.setAudioOutput(
            self.audio_output
        )

        self.audio_output.setVolume(0.8)

        self.player.mediaStatusChanged.connect(
            self.on_media_status_changed
        )

        self.player.errorOccurred.connect(
            self.on_error
        )

        self.current_url = None

    def play(self, url, song_name="Unknown"):

        if not url:
            return

        self.current_url = url

        media_url = QUrl(url)

        self.player.setSource(
            media_url
        )

        self.player.play()

        self.song_started.emit(
            song_name
        )

    def pause(self):

        self.player.pause()

    def resume(self):

        self.player.play()

    def stop(self):

        self.player.stop()

    def set_volume(self, volume):

        volume = max(
            0.0,
            min(1.0, volume)
        )

        self.audio_output.setVolume(
            volume
        )

    def is_playing(self):

        return (
            self.player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )

    def on_media_status_changed(
        self,
        status
    ):

        if (
            status
            == QMediaPlayer.MediaStatus.EndOfMedia
        ):

            self.song_finished.emit()

    def on_error(
        self,
        error,
        error_string
    ):

        if error != QMediaPlayer.Error.NoError:

            self.playback_error.emit(
                error_string
            )