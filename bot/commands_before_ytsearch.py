from urllib.parse import urlparse

from database.users import UserManager
from music.resolver import MusicResolver


class CommandHandler:

    def __init__(
        self,
        music_controller,
        user_manager=None,
        prefix="!",
    ):
        self.music_controller = music_controller

        self.user_manager = (
            user_manager
            if user_manager
            else UserManager()
        )

        self.prefix = prefix or "!"

        # Unified resolver.
        #
        # Current provider:
        #   Jamendo
        #
        # Future providers can be added inside MusicResolver
        # without changing CommandHandler or the radio pipeline.
        self.music_resolver = MusicResolver(
            jamendo_client_id="2c99fb24",
            timeout=10,
        )

        self.commands = {
            "play": self.play,
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

    # =====================================================
    # PREFIX
    # =====================================================

    def set_prefix(self, prefix):
        prefix = prefix.strip()

        if not prefix:
            prefix = "!"

        self.prefix = prefix

    # =====================================================
    # COMMAND HANDLER
    # =====================================================

    def handle(
        self,
        message,
        username="Owner",
    ):
        if not message:
            return "Empty command."

        message = message.strip()

        if not message.startswith(self.prefix):
            return None

        command_text = message[len(self.prefix):].strip()

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

        required_role = self.permissions.get(
            command,
            "User",
        )

        if not self.user_manager.has_permission(
            username,
            required_role,
        ):
            user_role = self.user_manager.get_role(
                username
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

    # =====================================================
    # URL VALIDATION
    # =====================================================

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)

            return (
                parsed.scheme in ("http", "https")
                and bool(parsed.netloc)
            )

        except Exception:
            return False

    # =====================================================
    # PLAY
    # =====================================================

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

        # -------------------------------------------------
        # Direct URL mode
        #
        # !play https://example.com/song.mp3 Optional Title
        # -------------------------------------------------

        if self.is_valid_url(first_argument):
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

        # -------------------------------------------------
        # Unified search mode
        #
        # !play jazz
        # !play rock
        # !play relaxing piano
        # -------------------------------------------------

        else:
            query = " ".join(arguments).strip()

            if not query:
                return (
                    f"Usage: {self.prefix}play "
                    "<song, artist, or URL>"
                )

            try:
                result = (
                    self.music_resolver
                    .resolve(
                        query,
                        requested_by=username,
                    )
                )

            except Exception as error:
                return (
                    f"Music search failed: {error}"
                )

            if not result:
                return (
                    f"No playable tracks found for: "
                    f"{query}"
                )

            track = dict(result)

            track["requested_by"] = username

            title = track.get(
                "title",
                "Unknown",
            )

        added = self.music_controller.add_song(
            track
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

    # =====================================================
    # QUEUE
    # =====================================================

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
                f"(requested by {requester})"
            )

        return "\n".join(lines)

    # =====================================================
    # NOW PLAYING
    # =====================================================

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
                    f"(requested by {requester})"
                )

            return (
                f"Now playing: {title} "
                f"(requested by {requester})"
            )

        return "Nothing is playing."

    # =====================================================
    # SKIP
    # =====================================================

    def skip(
        self,
        arguments,
        username,
    ):
        if self.music_controller.skip():
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
                    f"Skipped. "
                    f"Now playing: {title}"
                )

        return "Queue is empty."

    # =====================================================
    # PAUSE
    # =====================================================

    def pause(
        self,
        arguments,
        username,
    ):
        if self.music_controller.pause():
            return "Music paused."

        return (
            "Nothing is currently playing."
        )

    # =====================================================
    # RESUME
    # =====================================================

    def resume(
        self,
        arguments,
        username,
    ):
        if self.music_controller.resume():
            return "Music resumed."

        return (
            "Nothing is currently playing."
        )

    # =====================================================
    # STOP
    # =====================================================

    def stop(
        self,
        arguments,
        username,
    ):
        self.music_controller.stop()

        return "Music stopped."

    # =====================================================
    # CLEAR
    # =====================================================

    def clear(
        self,
        arguments,
        username,
    ):
        self.music_controller.clear_queue()

        return "Queue cleared."

    # =====================================================
    # REMOVE
    # =====================================================

    def remove(
        self,
        arguments,
        username,
    ):
        if not arguments:
            return (
                "Usage: "
                f"{self.prefix}remove <number>"
            )

        try:
            number = int(
                arguments[0]
            )

        except ValueError:
            return (
                "Queue number must be a number."
            )

        index = number - 1

        song = (
            self.music_controller
            .remove_song(index)
        )

        if song:
            title = song.get(
                "title",
                "Unknown",
            )

            return (
                f"Removed: {title}"
            )

        return "Invalid queue number."

    # =====================================================
    # HELP
    # =====================================================

    def help(
        self,
        arguments,
        username,
    ):
        return (
            f"{self.prefix}play <song/artist or URL>\n"
            f"{self.prefix}queue\n"
            f"{self.prefix}nowplaying\n"
            f"{self.prefix}skip\n"
            f"{self.prefix}pause\n"
            f"{self.prefix}resume\n"
            f"{self.prefix}stop\n"
            f"{self.prefix}remove <number>\n"
            f"{self.prefix}clear\n"
            f"{self.prefix}help"
        )
