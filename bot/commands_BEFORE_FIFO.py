from urllib.parse import urlparse

from PySide6.QtCore import QObject, QThread, Signal, Slot

from database.users import UserManager
from music.resolver import MusicResolver
from music.youtube_owned import YouTubeOwnedProvider


# =============================================================
# BACKGROUND MUSIC RESOLVER
# =============================================================

class MusicResolveWorker(QThread):

    resolved = Signal(str, str, object)
    failed = Signal(str, str, str)

    def __init__(
        self,
        resolver,
        query,
        username,
        parent=None,
    ):
        super().__init__(parent)

        self.resolver = resolver
        self.query = str(query or "").strip()
        self.username = str(username or "").strip()

    def run(self):

        try:
            print()
            print(
                "BACKGROUND MUSIC: "
                f"Preparing '{self.query}' "
                f"for {self.username}..."
            )

            result = self.resolver.resolve(
                self.query,
                requested_by=self.username,
            )

            if not result:
                self.failed.emit(
                    self.username,
                    self.query,
                    (
                        "No playable tracks "
                        f"found for: {self.query}"
                    ),
                )
                return

            self.resolved.emit(
                self.username,
                self.query,
                result,
            )

        except Exception as error:

            self.failed.emit(
                self.username,
                self.query,
                str(error),
            )


# =============================================================
# COMMAND HANDLER
# =============================================================

class CommandHandler(QObject):

    # Emitted after a background !play request finishes.
    #
    # We will connect this to live IMVU output in the next stage.
    async_response = Signal(str, str)

    def __init__(
        self,
        music_controller,
        user_manager=None,
        prefix="!",
    ):
        super().__init__()

        self.music_controller = music_controller

        self.user_manager = (
            user_manager
            if user_manager
            else UserManager()
        )

        self.prefix = prefix or "!"

        # -----------------------------------------------------
        # UNIFIED MUSIC RESOLVER
        # -----------------------------------------------------

        self.music_resolver = MusicResolver(
            jamendo_client_id="2c99fb24",
            timeout=10,
        )

        # -----------------------------------------------------
        # YOUTUBE SEARCH PROVIDER
        # -----------------------------------------------------

        self.youtube_search = YouTubeOwnedProvider()

        # Keep QThread objects alive until they finish.
        self.music_resolve_workers = []

        # -----------------------------------------------------
        # COMMANDS
        # -----------------------------------------------------

        self.commands = {
            "play": self.play,
            "ytsearch": self.ytsearch,
            "queue": self.show_queue,
            "nowplaying": self.now_playing,
            "skip": self.skip,
            "pause": self.pause,
            "resume": self.resume,
            "stop": self.stop,
            "clear": self.clear,
            "remove": self.remove,
            "help": self.help,
        }

        self.permissions = {
            "play": "User",
            "ytsearch": "User",
            "queue": "User",
            "nowplaying": "User",
            "help": "User",
            "skip": "DJ",
            "pause": "DJ",
            "resume": "DJ",
            "stop": "Moderator",
            "remove": "Moderator",
            "clear": "Moderator",
        }

    # =========================================================
    # PREFIX
    # =========================================================

    def set_prefix(self, prefix):

        prefix = str(prefix or "").strip()

        if not prefix:
            prefix = "!"

        self.prefix = prefix

    # =========================================================
    # COMMAND HANDLER
    # =========================================================

    def handle(
        self,
        message,
        username="Owner",
    ):

        if not message:
            return "Empty command."

        message = message.strip()

        if not message.startswith(
            self.prefix
        ):
            return None

        command_text = (
            message[len(self.prefix):]
            .strip()
        )

        if not command_text:
            return "Enter a command."

        parts = command_text.split()

        command = parts[0].lower()
        arguments = parts[1:]

        if command not in self.commands:

            return (
                f"Unknown command: "
                f"{self.prefix}{command}"
            )

        required_role = (
            self.permissions.get(
                command,
                "User",
            )
        )

        if not self.user_manager.has_permission(
            username,
            required_role,
        ):

            user_role = (
                self.user_manager.get_role(
                    username
                )
            )

            return (
                f"Permission denied. "
                f"{username} has role "
                f"{user_role}, but "
                f"{self.prefix}{command} "
                f"requires {required_role}."
            )

        return self.commands[command](
            arguments,
            username,
        )

    # =========================================================
    # URL VALIDATION
    # =========================================================

    def is_valid_url(
        self,
        url,
    ):

        try:

            parsed = urlparse(url)

            return (
                parsed.scheme
                in (
                    "http",
                    "https",
                )
                and bool(
                    parsed.netloc
                )
            )

        except Exception:
            return False

    # =========================================================
    # PLAY
    # =========================================================

    def play(
        self,
        arguments,
        username,
    ):

        if not arguments:

            current = (
                self.music_controller
                .get_current_song()
            )

            if current:

                title = current.get(
                    "title",
                    "Unknown",
                )

                return (
                    f"Currently playing: "
                    f"{title}"
                )

            return "Queue is empty."

        first_argument = arguments[0]

        # -----------------------------------------------------
        # DIRECT URL
        #
        # Direct URLs do not require searching/downloading,
        # so they remain immediate.
        # -----------------------------------------------------

        if self.is_valid_url(
            first_argument
        ):

            url = first_argument

            title = " ".join(
                arguments[1:]
            ).strip()

            if not title:
                title = url

            track = {
                "title": title,
                "url": url,
                "requested_by": username,
                "source": "direct",
            }

            added = (
                self.music_controller
                .add_song(
                    track
                )
            )

            if not added:

                return (
                    "Could not add the track "
                    "to the music queue."
                )

            current = (
                self.music_controller
                .get_current_song()
            )

            if current == track:

                return (
                    f"Now playing: "
                    f"{title}"
                )

            return (
                f"Added to queue: "
                f"{title}"
            )

        # -----------------------------------------------------
        # SEARCH QUERY
        #
        # YouTube/Jamendo resolution now happens in a QThread.
        # -----------------------------------------------------

        query = " ".join(
            arguments
        ).strip()

        if not query:

            return (
                f"Usage: {self.prefix}play "
                "<song, artist, or URL>"
            )

        self.start_music_resolve(
            query,
            username,
        )

        # Return immediately.
        #
        # This means IMVU chat does not have to wait for
        # yt-dlp search/download/FFmpeg preparation.
        return (
            f"Preparing: {query}"
        )

    # =========================================================
    # START BACKGROUND MUSIC RESOLUTION
    # =========================================================

    def start_music_resolve(
        self,
        query,
        username,
    ):

        worker = MusicResolveWorker(
            self.music_resolver,
            query,
            username,
            self,
        )

        worker.resolved.connect(
            self.music_resolve_succeeded
        )

        worker.failed.connect(
            self.music_resolve_failed
        )

        worker.finished.connect(
            lambda w=worker:
            self.cleanup_music_resolve_worker(
                w
            )
        )

        self.music_resolve_workers.append(
            worker
        )

        print()
        print(
            "BACKGROUND MUSIC: "
            f"Starting worker for "
            f"{username}: {query}"
        )

        worker.start()

    # =========================================================
    # BACKGROUND MUSIC SUCCESS
    # =========================================================

    @Slot(str, str, object)
    def music_resolve_succeeded(
        self,
        username,
        query,
        result,
    ):

        try:

            track = dict(
                result
            )

            track[
                "requested_by"
            ] = username

            title = track.get(
                "title",
                "Unknown",
            )

            added = (
                self.music_controller
                .add_song(
                    track
                )
            )

            if not added:

                response = (
                    "Could not add the track "
                    "to the music queue."
                )

                self.async_response.emit(
                    username,
                    response,
                )

                return

            current = (
                self.music_controller
                .get_current_song()
            )

            if current == track:

                response = (
                    f"Now playing: "
                    f"{title}"
                )

            else:

                response = (
                    f"Added to queue: "
                    f"{title}"
                )

            print()
            print(
                "BACKGROUND MUSIC: "
                f"{response}"
            )

            self.async_response.emit(
                username,
                response,
            )

        except Exception as error:

            response = (
                "Music preparation failed: "
                f"{error}"
            )

            print()
            print(
                "BACKGROUND MUSIC ERROR: "
                f"{error}"
            )

            self.async_response.emit(
                username,
                response,
            )

    # =========================================================
    # BACKGROUND MUSIC FAILURE
    # =========================================================

    @Slot(str, str, str)
    def music_resolve_failed(
        self,
        username,
        query,
        error,
    ):

        error = str(
            error or ""
        ).strip()

        if error.startswith(
            "No playable tracks found"
        ):

            response = error

        else:

            response = (
                "Music search failed: "
                f"{error}"
            )

        print()
        print(
            "BACKGROUND MUSIC ERROR: "
            f"{query}: {error}"
        )

        self.async_response.emit(
            username,
            response,
        )

    # =========================================================
    # CLEANUP BACKGROUND WORKER
    # =========================================================

    def cleanup_music_resolve_worker(
        self,
        worker,
    ):

        if worker in self.music_resolve_workers:

            self.music_resolve_workers.remove(
                worker
            )

        worker.deleteLater()

    # =========================================================
    # YOUTUBE SEARCH
    # =========================================================

    def ytsearch(
        self,
        arguments,
        username,
    ):

        query = " ".join(
            arguments
        ).strip()

        if not query:

            return (
                f"Usage: "
                f"{self.prefix}ytsearch "
                "<song or artist>"
            )

        print()
        print(
            "IMVU YTSEARCH: "
            f"{username}: {query}"
        )

        try:

            results = (
                self.youtube_search
                .search_candidates(
                    query,
                    limit=5,
                )
            )

        except Exception as error:

            print(
                "IMVU YTSEARCH ERROR: "
                f"{error}"
            )

            return (
                "YouTube search failed: "
                f"{error}"
            )

        if not results:

            return (
                "No YouTube results "
                f"found for: {query}"
            )

        lines = [
            f"YouTube results for "
            f"{query}:"
        ]

        for number, result in enumerate(
            results[:3],
            start=1,
        ):

            title = result.get(
                "title",
                "Unknown",
            )

            channel = result.get(
                "channel",
                "Unknown",
            )

            video_id = result.get(
                "id",
                "",
            )

            lines.append(
                f"{number}. {title} "
                f"- {channel} "
                f"[{video_id}]"
            )

        return "\n".join(
            lines
        )

    # =========================================================
    # QUEUE
    # =========================================================

    def show_queue(
        self,
        arguments,
        username,
    ):

        queue = (
            self.music_controller
            .get_queue()
        )

        if not queue:
            return "Queue is empty."

        lines = []

        for number, track in enumerate(
            queue,
            start=1,
        ):

            title = track.get(
                "title",
                "Unknown",
            )

            requester = track.get(
                "requested_by",
                "Unknown",
            )

            lines.append(
                f"{number}. {title} "
                f"(requested by "
                f"{requester})"
            )

        return "\n".join(
            lines
        )

    # =========================================================
    # NOW PLAYING
    # =========================================================

    def now_playing(
        self,
        arguments,
        username,
    ):

        song = (
            self.music_controller
            .get_current_song()
        )

        if song:

            title = song.get(
                "title",
                "Unknown",
            )

            requester = song.get(
                "requested_by",
                "Unknown",
            )

            if (
                self.music_controller
                .queue
                .is_paused
            ):

                return (
                    f"Paused: {title} "
                    f"(requested by "
                    f"{requester})"
                )

            return (
                f"Now playing: {title} "
                f"(requested by "
                f"{requester})"
            )

        return (
            "Nothing is playing."
        )

    # =========================================================
    # SKIP
    # =========================================================

    def skip(
        self,
        arguments,
        username,
    ):

        if (
            self.music_controller
            .skip()
        ):

            song = (
                self.music_controller
                .get_current_song()
            )

            if song:

                title = song.get(
                    "title",
                    "Unknown",
                )

                return (
                    "Skipped. "
                    f"Now playing: {title}"
                )

        return "Queue is empty."

    # =========================================================
    # PAUSE
    # =========================================================

    def pause(
        self,
        arguments,
        username,
    ):

        if (
            self.music_controller
            .pause()
        ):

            return "Music paused."

        return (
            "Nothing is currently "
            "playing."
        )

    # =========================================================
    # RESUME
    # =========================================================

    def resume(
        self,
        arguments,
        username,
    ):

        if (
            self.music_controller
            .resume()
        ):

            return "Music resumed."

        return (
            "Nothing is currently "
            "playing."
        )

    # =========================================================
    # STOP
    # =========================================================

    def stop(
        self,
        arguments,
        username,
    ):

        self.music_controller.stop()

        return "Music stopped."

    # =========================================================
    # CLEAR
    # =========================================================

    def clear(
        self,
        arguments,
        username,
    ):

        self.music_controller.clear_queue()

        return "Queue cleared."

    # =========================================================
    # REMOVE
    # =========================================================

    def remove(
        self,
        arguments,
        username,
    ):

        if not arguments:

            return (
                "Usage: "
                f"{self.prefix}remove "
                "<number>"
            )

        try:

            number = int(
                arguments[0]
            )

        except ValueError:

            return (
                "Queue number must "
                "be a number."
            )

        index = number - 1

        song = (
            self.music_controller
            .remove_song(
                index
            )
        )

        if song:

            title = song.get(
                "title",
                "Unknown",
            )

            return (
                f"Removed: {title}"
            )

        return (
            "Invalid queue number."
        )

    # =========================================================
    # HELP
    # =========================================================

    def help(
        self,
        arguments,
        username,
    ):

        return (
            f"{self.prefix}play "
            "<song/artist or URL>\n"

            f"{self.prefix}ytsearch "
            "<song/artist>\n"

            f"{self.prefix}queue\n"

            f"{self.prefix}nowplaying\n"

            f"{self.prefix}skip\n"

            f"{self.prefix}pause\n"

            f"{self.prefix}resume\n"

            f"{self.prefix}stop\n"

            f"{self.prefix}remove "
            "<number>\n"

            f"{self.prefix}clear\n"

            f"{self.prefix}help"
        )
