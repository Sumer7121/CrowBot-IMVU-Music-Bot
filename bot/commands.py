from urllib.parse import urlparse
import random
import time

from PySide6.QtCore import QObject, QThread, Signal, Slot

from database.users import UserManager
from music.resolver import MusicResolver
from music.youtube_owned import get_shared_youtube_provider
from bot.five_in_a_row import FiveInARow
from bot.party_games import PartyGames
from bot import party_prompts as prompts
from bot.social_reactions import SocialReactions
from bot.collectibles import CollectibleDrops


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
            timeout=10,
        )
        # Set by RoomSession. Each IMVU room has its own AutoDJ.
        self.dj_controller = None

        # -----------------------------------------------------
        # YOUTUBE SEARCH PROVIDER
        # -----------------------------------------------------

        self.youtube_search = get_shared_youtube_provider()

        # -----------------------------------------------------
        # FIFO MUSIC PREPARATION
        # -----------------------------------------------------
        #
        # Song requests are prepared one at a time.
        #
        # This prevents multiple yt-dlp / FFmpeg preparation
        # jobs from running simultaneously and guarantees that
        # requests enter MusicController in request order.
        #
        # Example:
        #
        #   Request A
        #   Request B
        #   Request C
        #
        # Preparation:
        #
        #   A -> B -> C
        #
        # Playback queue therefore remains:
        #
        #   A -> B -> C
        #
        self.music_prepare_queue = []
        self.active_music_worker = None

        # -----------------------------------------------------
        # COMMANDS
        # -----------------------------------------------------

        self.commands = {
            "play": self.play,
            "dj": self.artist_dj,
            "autoplay": self.autoplay,
            "language": self.music_language,
            "lang": self.music_language,
            "djstatus": self.dj_status,
            "ytsearch": self.ytsearch,
            "queue": self.show_queue,
            "nowplaying": self.now_playing,
            "np": self.now_playing,
            "skip": self.skip,
            "pause": self.pause,
            "resume": self.resume,
            "stop": self.stop,
            "clear": self.clear,
            "remove": self.remove,

            # Fun commands
            "joke": self.joke,
            "roast": self.roast,
            "truth": self.truth,
            "dare": self.dare,
            "tod": self.truth_or_dare,
            "truthordare": self.truth_or_dare,

            # Tic-Tac-Toe
            "ttt": self.tic_tac_toe,
            "accept": self.accept_tic_tac_toe,
            "move": self.tic_tac_toe_move,
            "tttboard": self.tic_tac_toe_board,
            "tttend": self.tic_tac_toe_end,

            "c4": self.five_start,
            "join": self.five_accept,
            "drop": self.five_move,
            "board": self.five_board,
            "end4": self.five_end,
            "five": self.five_start,
            "fiveaccept": self.five_accept,
            "fivemove": self.five_move,
            "fiveboard": self.five_board,
            "fiveend": self.five_end,
            "quiz": self.trivia_start,
            "a": self.trivia_answer,
            "guess": self.guess_start,
            "g": self.guess_answer,
            "rps": self.rock_paper_scissors,
            "top": self.game_scores,
            "catch": self.catch_collectible,
            "collection": self.show_collection,
            "cats": self.show_collection,
            "dogs": self.show_collection,
            "pets": self.show_collection,
            "rarities": self.pet_rarities,
            "spin": self.spin_bottle,
            "question": self.question,
            "questions": self.question,
            "wyr": self.would_you_rather,
            "wouldyourather": self.would_you_rather,
            "nhie": self.never_have_i_ever,
            "neverhaveiever": self.never_have_i_ever,
            "8ball": self.magic_eight_ball,
            "riddle": self.riddle_start,
            "ra": self.riddle_answer,
            "duel": self.duel_player,
            "qotd": self.question,
            "h": self.help,
            "p": self.play,
            "q": self.show_queue,
            "s": self.skip,
            "pa": self.pause,
            "r": self.resume,
            "rm": self.remove,
            "j": self.joke,
            "joke18": self.adult_joke,
            "meme": self.meme,
            "memes": self.meme,
            "tr": self.truth,
            "d": self.dare,
            "tt": self.tic_tac_toe,
            "m": self.tic_tac_toe_move,
            "help": self.help,
        }

        # -----------------------------------------------------
        # SOCIAL / GAME STATE
        # -----------------------------------------------------

        # Public commands intentionally have no role gate.
        self.permissions = {}

        self.jokes = [
            "Why did the computer go to therapy? It had too many unresolved issues.",
            "Why was the keyboard exhausted? It had two shifts.",
            "Why did the developer go broke? They used up all their cache.",
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "I told my computer I needed a break. It said: No problem, I'll go to sleep.",
            "Why was the music bot calm? It knew how to handle the queue.",
            "What do you call eight hobbits? A hobbyte.",
            "Why did the scarecrow get promoted? He was outstanding in his field.",
            "I tried to organize a hide-and-seek tournament, but good players are hard to find.",
            "Why don't skeletons fight each other? They don't have the guts.",
            "What did one wall say to the other wall? I'll meet you at the corner.",
            "Why did the math book look stressed? It had too many problems.",
            "What do you call fake spaghetti? An impasta.",
            "Why couldn't the bicycle stand up? It was two-tired.",
            "What does a cloud wear under its raincoat? Thunderwear.",
        ]

        self.roasts = [
            "{name}, you bring loading-screen energy to every conversation.",
            "{name}, even autocorrect looked at that and said 'you're on your own.'",
            "{name}, your Wi-Fi has better social skills.",
            "{name}, you're proof that buffering can happen in real life.",
            "{name}, your comeback is still downloading.",
            "{name}, I've seen stronger signals from airplane mode.",
            "{name}, you have the confidence of someone who didn't read the instructions.",
            "{name}, even the queue knows when to move on.",
            "{name}, you're running on 1 percent battery energy today.",
            "{name}, that was bold for someone whose brain just hit snooze.",
            "{name}, your plot twist needs a software update.",
            "{name}, you make lag look productive.",
        ]

        self.truths = [
            "What is the most embarrassing song you secretly like?",
            "What is the funniest mistake you've made recently?",
            "What is something you've pretended to understand but actually didn't?",
            "Who was your first crush?",
            "What is the weirdest food combination you actually enjoy?",
            "What is your most useless talent?",
            "What is the last thing you searched for?",
            "What is one habit you wish you could instantly change?",
            "What is the longest you've gone without sleeping?",
            "What is something silly you're surprisingly competitive about?",
            "What is the strangest dream you remember?",
            "What is one thing on your bucket list?",
            "What is the funniest excuse you've ever used?",
            "What is a movie everyone loves that you don't?",
            "What is something you've never told your friends because it seemed too random?",
        ]

        self.dares = [
            "Type your next message using only capital letters.",
            "Use a dramatic movie-trailer voice for your next sentence.",
            "Give someone in the room a genuine compliment.",
            "Describe your day using only three words.",
            "Change your status to something funny for five minutes.",
            "Type a sentence without using the letter E.",
            "Tell the room your best terrible joke.",
            "Write a two-line poem about the person who dared you.",
            "Speak in questions for your next three messages.",
            "Describe yourself as if you were a video-game character.",
            "Make up a ridiculous superhero name for yourself.",
            "Use three random emojis to describe your mood.",
            "Give your favorite song a completely different title.",
            "Say something nice about the last person who spoke.",
            "Invent a fake fact about CrowBot that is obviously ridiculous.",
        ]

        # One pending challenge and one active game are enough for
        # a single IMVU room/session.
        self.ttt_pending = None
        self.ttt_game = None
        self.five_game = FiveInARow()
        self.party_games = PartyGames()
        self.social = SocialReactions()
        self.collectibles = CollectibleDrops()
        self.adult_jokes = False

        # -----------------------------------------------------
        # OBSERVED IMVU USERS
        # -----------------------------------------------------

        # CrowBot learns real IMVU usernames as users send
        # messages/commands during the current bot session.
        #
        # key   = lowercase username
        # value = original IMVU username/capitalization
        self.known_users = {}
        self.last_seen_users = {}
        self.spin_user_ttl_seconds = 300

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

        # Remember the real IMVU username automatically.
        self._remember_user(username)

        # All CrowBot commands are public room commands.
        # No DJ / Moderator / Owner role check is performed here.
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

        if arguments == ["m"]:
            return self.help(["music"], username)

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
        # yt-dlp resolution happens in a QThread.
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
        """
        Add a music request to the FIFO preparation queue.

        Only one MusicResolveWorker is allowed to run at a time.
        """

        request = {
            "query": str(query or "").strip(),
            "username": str(username or "").strip(),
        }

        self.music_prepare_queue.append(
            request
        )

        position = len(
            self.music_prepare_queue
        )

        if self.active_music_worker is not None:
            position += 1

        print()
        print(
            "BACKGROUND MUSIC FIFO: "
            f"Queued {username}: {query}"
        )

        print(
            "BACKGROUND MUSIC FIFO: "
            f"Preparation position: {position}"
        )

        self.start_next_music_resolve()

    # =========================================================
    # START NEXT FIFO REQUEST
    # =========================================================

    def start_next_music_resolve(
        self,
    ):
        """
        Start the next queued preparation request.

        If a worker is already running, this method does nothing.
        """

        if self.active_music_worker is not None:
            return

        if not self.music_prepare_queue:

            print()
            print(
                "BACKGROUND MUSIC FIFO: "
                "Preparation queue is empty."
            )

            return

        request = (
            self.music_prepare_queue.pop(0)
        )

        query = request.get(
            "query",
            "",
        )

        username = request.get(
            "username",
            "",
        )

        worker = MusicResolveWorker(
            self.music_resolver,
            query,
            username,
            self,
        )

        self.active_music_worker = worker

        worker.resolved.connect(
            self.music_resolve_succeeded
        )

        worker.failed.connect(
            self.music_resolve_failed
        )

        worker.finished.connect(
            self.music_resolve_finished
        )

        print()
        print(
            "BACKGROUND MUSIC FIFO: "
            f"Starting {username}: {query}"
        )

        print(
            "BACKGROUND MUSIC FIFO: "
            f"{len(self.music_prepare_queue)} "
            "request(s) waiting after this one."
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

            # This slot runs back on the CommandHandler / Qt
            # thread, so MusicController remains on the main
            # application side.
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
                "BACKGROUND MUSIC FIFO: "
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
                "BACKGROUND MUSIC FIFO ERROR: "
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
            "BACKGROUND MUSIC FIFO ERROR: "
            f"{query}: {error}"
        )

        self.async_response.emit(
            username,
            response,
        )

    # =========================================================
    # FIFO WORKER FINISHED
    # =========================================================

    @Slot()
    def music_resolve_finished(
        self,
    ):
        """
        Clean up the completed worker and automatically start
        the next request in FIFO order.
        """

        worker = self.active_music_worker

        self.active_music_worker = None

        if worker is not None:
            worker.deleteLater()

        print()
        print(
            "BACKGROUND MUSIC FIFO: "
            "Worker finished."
        )

        if self.music_prepare_queue:

            print(
                "BACKGROUND MUSIC FIFO: "
                f"Starting next request. "
                f"{len(self.music_prepare_queue)} "
                "request(s) waiting."
            )

        self.start_next_music_resolve()
    # =========================================================
    # PER-ROOM AUTOMATIC DJ
    # =========================================================

    def _room_dj(self):
        return self.dj_controller

    def artist_dj(self, arguments, username):
        dj = self._room_dj()
        if dj is None:
            return "DJ mode is available inside a connected multi-room session."
        name = " ".join(arguments).strip()
        if not name or name.casefold() in ("status", "help"):
            return (
                "🎧 ARTIST DJ | " + dj.label +
                f"\nUse {self.prefix}dj <artist name> to play the artist continuously, "
                f"or {self.prefix}dj off."
            )
        if name.casefold() in ("off", "stop", "disable"):
            dj.off()
            return "🎧 Artist DJ and autoplay disabled. The current song continues."
        try:
            return "🎧 " + dj.set_artist(name)
        except ValueError as error:
            return str(error)

    def autoplay(self, arguments, username):
        dj = self._room_dj()
        if dj is None:
            return "Autoplay is available inside a connected multi-room session."
        choice = " ".join(arguments).strip().casefold()
        if not choice or choice == "status":
            return "🎶 AutoDJ | " + dj.label
        if choice in ("on", "yes", "enable", "start"):
            return "🎶 " + dj.set_autoplay(True)
        if choice in ("off", "no", "disable", "stop"):
            return "🎶 " + dj.set_autoplay(False)
        return f"Usage: {self.prefix}autoplay on|off|status"

    def music_language(self, arguments, username):
        dj = self._room_dj()
        if dj is None:
            return "Music language settings are available inside a connected room."
        name = " ".join(arguments).strip()
        if not name:
            return (
                "🌐 DJ language: " + (dj.language.title() if dj.language else "Any") +
                f"\nUse {self.prefix}language Hindi, Telugu, Tamil, English, etc., or off."
            )
        try:
            dj.set_language(name)
        except ValueError as error:
            return "🌐 " + str(error)
        return "🌐 Music discovery language set to " + (
            dj.language.title() if dj.language else "Any"
        ) + ". The change affects upcoming AutoDJ songs."

    def dj_status(self, arguments, username):
        dj = self._room_dj()
        return "🎧 DJ status: " + dj.label if dj is not None else "DJ unavailable."

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

        dj = self._room_dj()
        if dj is not None and dj.enabled:
            dj.set_autoplay(False)
        self.music_controller.stop()

        return "Music stopped. Autoplay is off."

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
    # USERNAME MEMORY / RESOLUTION
    # =========================================================

    def _remember_user(
        self,
        username,
    ):
        """
        Remember an observed IMVU username.

        IMVU supplies the actual sender name to CommandHandler.handle().
        We preserve the original capitalization while matching names
        case-insensitively.
        """

        value = str(
            username or ""
        ).strip().lstrip("@")

        if not value:
            return ""

        self.known_users[value.lower()] = value
        self.last_seen_users[value.lower()] = time.monotonic()
        return value

    def _known_user_values(
        self,
    ):
        return sorted(
            self.known_users.values(),
            key=str.lower,
        )

    def _resolve_user(
        self,
        value,
        sender=None,
    ):
        """
        Resolve a remembered room username.

        Matching order:
            1. Sender when no target was supplied
            2. Exact case-insensitive match
            3. Unique starts-with match
            4. Unique contains match

        Returns:
            ("ok", username)
            ("multiple", [usernames])
            ("unknown", query)
        """

        query = str(
            value or ""
        ).strip().lstrip("@")

        if not query:

            sender_name = (
                self._remember_user(
                    sender
                )
            )

            if sender_name:
                return (
                    "ok",
                    sender_name,
                )

            return (
                "unknown",
                "",
            )

        query_lower = (
            query.lower()
        )

        # -----------------------------------------------------
        # EXACT MATCH
        # -----------------------------------------------------

        exact = self.known_users.get(
            query_lower
        )

        if exact:

            return (
                "ok",
                exact,
            )

        users = (
            self._known_user_values()
        )

        # -----------------------------------------------------
        # UNIQUE STARTS-WITH MATCH
        # -----------------------------------------------------

        starts = [
            user
            for user in users
            if user.lower().startswith(
                query_lower
            )
        ]

        if len(starts) == 1:

            return (
                "ok",
                starts[0],
            )

        if len(starts) > 1:

            return (
                "multiple",
                starts,
            )

        # -----------------------------------------------------
        # UNIQUE CONTAINS MATCH
        # -----------------------------------------------------

        contains = [
            user
            for user in users
            if query_lower in user.lower()
        ]

        if len(contains) == 1:

            return (
                "ok",
                contains[0],
            )

        if len(contains) > 1:

            return (
                "multiple",
                contains,
            )

        return (
            "unknown",
            query,
        )

    def _resolve_target(
        self,
        arguments,
        username,
        allow_unknown=False,
    ):

        query = " ".join(
            arguments
        ).strip()

        status, result = (
            self._resolve_user(
                query,
                username,
            )
        )

        if status == "ok":

            return (
                result,
                None,
            )

        if status == "multiple":

            matches = ", ".join(
                result[:6]
            )

            return (
                None,
                (
                    "⚠️ Multiple users match "
                    f'"{query}": {matches}. '
                    "Type a little more of the username."
                ),
            )

        if (
            allow_unknown
            and query
        ):

            return (
                query.lstrip("@"),
                None,
            )

        if query:

            return (
                None,
                (
                    "⚠️ I haven't seen a room user "
                    f'matching "{query}" yet.'
                ),
            )

        sender_name = (
            self._remember_user(
                username
            )
        )

        if sender_name:

            return (
                sender_name,
                None,
            )

        return (
            None,
            "⚠️ I couldn't determine the username.",
        )

    # =========================================================
    # JOKE
    # =========================================================

    def joke(self, arguments, username):
        self._remember_user(username)
        return "😂 JOKE\n" + self.social.pick("jokes_sfw", prompts.JOKES_SFW)

    def adult_joke(self, arguments, username):
        self._remember_user(username)
        return "🌶️ LATE-NIGHT JOKE (mild)\n" + self.social.pick("jokes_adult", prompts.JOKES_ADULT)

    # =========================================================
    # ROAST
    # =========================================================

    def roast(
        self,
        arguments,
        username,
    ):

        self._remember_user(
            username
        )

        target, error = (
            self._resolve_target(
                arguments,
                username,
                allow_unknown=True,
            )
        )

        if error:
            return error

        roast_text = self.social.pick("roasts", prompts.ROASTS).format(
            name=target
        )

        return (
            "🔥 ROAST\n"
            f"{roast_text}"
        )

    # =========================================================
    # TRUTH
    # =========================================================

    def truth(
        self,
        arguments,
        username,
    ):

        self._remember_user(
            username
        )

        target, error = (
            self._resolve_target(
                arguments,
                username,
                allow_unknown=True,
            )
        )

        if error:
            return error

        prompt = self.social.pick("truths", prompts.TOD_TRUTHS)

        return (
            "🎯 TRUTH\n"
            f"👤 {target}\n\n"
            f"{prompt}"
        )

    # =========================================================
    # DARE
    # =========================================================

    def dare(
        self,
        arguments,
        username,
    ):

        self._remember_user(
            username
        )

        target, error = (
            self._resolve_target(
                arguments,
                username,
                allow_unknown=True,
            )
        )

        if error:
            return error

        prompt = self.social.pick("dares", prompts.TOD_DARES)

        return (
            "🔥 DARE\n"
            f"👤 {target}\n\n"
            f"{prompt}"
        )

    # =========================================================
    # TRUTH OR DARE
    # =========================================================

    def truth_or_dare(
        self,
        arguments,
        username,
    ):
        """Random truth/dare for a named player, or the sender when omitted.

        A name can be typed directly (including spaces) even when that person
        has not chatted yet. This is a nomination, not an occupancy check.
        """
        self._remember_user(username)
        target, error = self._resolve_target(
            arguments, username, allow_unknown=True
        )
        if error:
            return error
        if random.choice((True, False)):
            prompt = self.social.pick("truths", prompts.TOD_TRUTHS)
            return f"🎯 TRUTH\n👤 {target}\n\n{prompt}"
        prompt = self.social.pick("dares", prompts.TOD_DARES)
        return f"🔥 DARE\n👤 {target}\n\n{prompt}"

    # =========================================================
    # TIC-TAC-TOE HELPERS
    # =========================================================

    def _normalize_player(
        self,
        value,
    ):

        return str(
            value or ""
        ).strip().lstrip("@").lower()

    def _ttt_number_tile(
        self,
        number,
    ):

        tiles = {
            1: "1️⃣",
            2: "2️⃣",
            3: "3️⃣",
            4: "4️⃣",
            5: "5️⃣",
            6: "6️⃣",
            7: "7️⃣",
            8: "8️⃣",
            9: "9️⃣",
        }

        return tiles.get(
            number,
            str(number),
        )

    def _ttt_render_board(
        self,
        board=None,
    ):

        if board is None:

            if not self.ttt_game:

                return (
                    "No Tic-Tac-Toe game is active."
                )

            board = self.ttt_game[
                "board"
            ]

        cells = []

        for index, value in enumerate(
            board
        ):

            if value == "X":

                cells.append(
                    "❌"
                )

            elif value == "O":

                cells.append(
                    "⭕"
                )

            else:

                cells.append(
                    self._ttt_number_tile(
                        index + 1
                    )
                )

        return (
            f"{cells[0]} │ {cells[1]} │ {cells[2]}\n"
            "──┼──┼──\n"
            f"{cells[3]} │ {cells[4]} │ {cells[5]}\n"
            "──┼──┼──\n"
            f"{cells[6]} │ {cells[7]} │ {cells[8]}"
        )

    def _ttt_winner(
        self,
        board,
    ):

        winning_lines = (
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),
            (0, 4, 8),
            (2, 4, 6),
        )

        for a, b, c in winning_lines:

            if (
                board[a]
                and board[a] == board[b]
                and board[a] == board[c]
            ):

                return board[a]

        return None

    # =========================================================
    # TIC-TAC-TOE CHALLENGE
    # =========================================================

    def tic_tac_toe(
        self,
        arguments,
        username,
    ):
        # Person typing !ttt automatically becomes Player 1.

        player_one = self._remember_user(
            username
        )

        if self.ttt_game:
            return (
                "🎮 A Tic-Tac-Toe game is already active.\n\n"
                f"{self._ttt_render_board()}"
            )

        if self.ttt_pending:
            starter = self.ttt_pending[
                "challenger"
            ]

            if (
                self._normalize_player(starter)
                ==
                self._normalize_player(player_one)
            ):
                return (
                    "🎮 Your challenge is already waiting.\n\n"
                    "👉 Another person should type "
                    f"{self.prefix}accept"
                )

            return (
                "🎮 TIC-TAC-TOE CHALLENGE\n\n"
                f"❌ Player 1: {starter}\n"
                "⭕ Player 2: waiting...\n\n"
                f"👉 Type {self.prefix}accept to play!"
            )

        self.ttt_pending = {
            "challenger": player_one,
        }

        return (
            "🎮 TIC-TAC-TOE CHALLENGE\n\n"
            f"❌ Player 1: {player_one}\n"
            "⭕ Player 2: waiting...\n\n"
            "👉 Next person to type "
            f"{self.prefix}accept joins the game!"
        )

    def accept_tic_tac_toe(
        self,
        arguments,
        username,
    ):
        # Person typing !accept automatically becomes Player 2.

        player_two = self._remember_user(
            username
        )

        if self.ttt_game:
            return (
                "🎮 A Tic-Tac-Toe game is already active."
            )

        if not self.ttt_pending:
            return (
                "🎮 Nobody is waiting for an opponent.\n"
                f"Type {self.prefix}ttt to start a game."
            )

        player_one = self.ttt_pending[
            "challenger"
        ]

        if (
            self._normalize_player(player_one)
            ==
            self._normalize_player(player_two)
        ):
            return (
                "😄 You started this game.\n"
                "Another person needs to type "
                f"{self.prefix}accept"
            )

        self.ttt_game = {
            "x": player_one,
            "o": player_two,
            "turn": "X",
            "board": [""] * 9,
        }

        self.ttt_pending = None

        return (
            "🎮 TIC-TAC-TOE\n\n"
            f"{player_one} ❌  VS  {player_two} ⭕\n\n"
            f"{self._ttt_render_board()}\n\n"
            f"👉 {player_one}'s turn\n"
            f"Use {self.prefix}move 1-9"
        )

    def tic_tac_toe_move(
        self,
        arguments,
        username,
    ):
        player = self._remember_user(
            username
        )

        if not self.ttt_game:
            return (
                "🎮 No Tic-Tac-Toe game is active.\n"
                f"Type {self.prefix}ttt to start one."
            )

        if not arguments:
            return (
                f"Use {self.prefix}move <1-9>"
            )

        try:
            position = int(arguments[0])
        except (TypeError, ValueError):
            return (
                "⚠️ Move must be a number from 1 to 9."
            )

        if not 1 <= position <= 9:
            return (
                "⚠️ Move must be a number from 1 to 9."
            )

        game = self.ttt_game

        player_key = self._normalize_player(
            player
        )

        if player_key == self._normalize_player(
            game["x"]
        ):
            mark = "X"

        elif player_key == self._normalize_player(
            game["o"]
        ):
            mark = "O"

        else:
            return (
                "👀 You're watching this game.\n"
                f"{game['x']} ❌ VS {game['o']} ⭕"
            )

        if game["turn"] != mark:
            current_name = (
                game["x"]
                if game["turn"] == "X"
                else game["o"]
            )

            return (
                f"⏳ Not your turn.\n"
                f"👉 {current_name}'s turn."
            )

        index = position - 1

        if game["board"][index]:
            return (
                "⚠️ That square is already taken.\n\n"
                f"{self._ttt_render_board()}"
            )

        game["board"][index] = mark

        winner = self._ttt_winner(
            game["board"]
        )

        if winner:
            board_text = self._ttt_render_board(
                game["board"]
            )

            winner_name = (
                game["x"]
                if winner == "X"
                else game["o"]
            )

            self.ttt_game = None

            return (
                "🏆 TIC-TAC-TOE WINNER 🏆\n\n"
                f"{board_text}\n\n"
                f"🎉 {winner_name} wins!"
            )

        if all(game["board"]):
            board_text = self._ttt_render_board(
                game["board"]
            )

            self.ttt_game = None

            return (
                "🤝 TIC-TAC-TOE DRAW\n\n"
                f"{board_text}\n\n"
                "GG!"
            )

        game["turn"] = (
            "O"
            if mark == "X"
            else "X"
        )

        next_name = (
            game["x"]
            if game["turn"] == "X"
            else game["o"]
        )

        return (
            "🎮 TIC-TAC-TOE\n\n"
            f"{self._ttt_render_board()}\n\n"
            f"👉 {next_name}'s turn"
        )

    def tic_tac_toe_board(
        self,
        arguments,
        username,
    ):
        self._remember_user(
            username
        )

        if self.ttt_game:
            current_name = (
                self.ttt_game["x"]
                if self.ttt_game["turn"] == "X"
                else self.ttt_game["o"]
            )

            return (
                "🎮 TIC-TAC-TOE\n\n"
                f"{self.ttt_game['x']} ❌  VS  "
                f"{self.ttt_game['o']} ⭕\n\n"
                f"{self._ttt_render_board()}\n\n"
                f"👉 {current_name}'s turn"
            )

        if self.ttt_pending:
            starter = self.ttt_pending[
                "challenger"
            ]

            return (
                "🎮 TIC-TAC-TOE\n\n"
                f"❌ Player 1: {starter}\n"
                "⭕ Player 2: waiting...\n\n"
                f"👉 Type {self.prefix}accept to join."
            )

        return (
            "🎮 No Tic-Tac-Toe game is active."
        )

    def tic_tac_toe_end(
        self,
        arguments,
        username,
    ):
        player = self._remember_user(
            username
        )

        player_key = self._normalize_player(
            player
        )

        if self.ttt_game:
            allowed = {
                self._normalize_player(
                    self.ttt_game["x"]
                ),
                self._normalize_player(
                    self.ttt_game["o"]
                ),
            }

            if player_key not in allowed:
                return (
                    "⚠️ Only one of the players "
                    "can end this game."
                )

            self.ttt_game = None

            return "🛑 Tic-Tac-Toe ended."

        if self.ttt_pending:
            starter = self.ttt_pending[
                "challenger"
            ]

            if (
                player_key
                !=
                self._normalize_player(starter)
            ):
                return (
                    "⚠️ Only the person who started "
                    "the challenge can cancel it."
                )

            self.ttt_pending = None

            return (
                "🛑 Tic-Tac-Toe challenge cancelled."
            )

        return (
            "🎮 There is no Tic-Tac-Toe game to end."
        )


    # =========================================================
    # FIVE IN A ROW
    # =========================================================

    def five_start(self, arguments, username):
        return self.five_game.start(self._remember_user(username))

    def five_accept(self, arguments, username):
        return self.five_game.accept(self._remember_user(username))

    def five_move(self, arguments, username):
        if not arguments:
            return f"Use {self.prefix}drop 1-7"
        return self.five_game.move(self._remember_user(username), arguments[0])

    def five_board(self, arguments, username):
        return self.five_game.render()

    def five_end(self, arguments, username):
        return self.five_game.end(self._remember_user(username))

    # =========================================================
    # QUICK PARTY GAMES
    # =========================================================

    def trivia_start(self, arguments, username):
        return self.party_games.start_trivia()

    def trivia_answer(self, arguments, username):
        return self.party_games.answer(username, " ".join(arguments))

    def guess_start(self, arguments, username):
        return self.party_games.start_guess()

    def guess_answer(self, arguments, username):
        return self.party_games.try_guess(username, arguments[0] if arguments else "")

    def rock_paper_scissors(self, arguments, username):
        return self.party_games.rps(username, arguments[0] if arguments else "")

    def game_scores(self, arguments, username):
        return self.party_games.leaderboard()

    def meme(self, arguments, username):
        return self.social.meme()

    def catch_collectible(self, arguments, username):
        return self.collectibles.catch(username)

    def show_collection(self, arguments, username):
        return self.collectibles.collection(username)

    def pet_rarities(self, arguments, username):
        from bot.collectibles import CATALOG, RARITY_WEIGHT
        return (
            f"🐱🐶 {len(CATALOG)} collectible cats and dogs\n"
            "COMMON 60% | RARE 27% | EPIC 10% | LEGENDARY 3%\n"
            f"Use {self.prefix}catch on wild drops and {self.prefix}pets to view your collection."
        )

    def question(self, arguments, username):
        self._remember_user(username)
        return "💬 QUESTION\n" + self.social.pick("questions", prompts.QUESTIONS)

    def would_you_rather(self, arguments, username):
        self._remember_user(username)
        return "🤔 WOULD YOU RATHER\n" + self.social.pick(
            "would_you_rather", prompts.WOULD_YOU_RATHER
        )

    def never_have_i_ever(self, arguments, username):
        self._remember_user(username)
        return "🙋 NEVER HAVE I EVER\n" + self.social.pick(
            "never_have_i_ever", prompts.NEVER_HAVE_I_EVER
        )

    def magic_eight_ball(self, arguments, username):
        self._remember_user(username)
        question = " ".join(arguments).strip()
        if not question:
            return f"🎱 Ask a question: {self.prefix}8ball <question>"
        answer = self.social.pick("magic_eight_ball", prompts.MAGIC_EIGHT_BALL)
        return f"🎱 {username} asked: {question}\nCrowBot says: {answer}"

    def riddle_start(self, arguments, username):
        self._remember_user(username)
        return self.party_games.start_riddle()

    def riddle_answer(self, arguments, username):
        self._remember_user(username)
        return self.party_games.answer_riddle(username, " ".join(arguments))

    def duel_player(self, arguments, username):
        self._remember_user(username)
        name = " ".join(arguments).strip().lstrip("@")
        return self.party_games.duel(username, name)

    def spin_bottle(self, arguments, username):
        """Spin toward one randomly chosen observed room chatter."""
        self._remember_user(username)
        # The sender is a participant, but prefer someone else if possible.
        now = time.monotonic()
        # Chat observation is not a reliable IMVU occupancy signal. Drop
        # inactive participants rather than selecting indefinitely stale names.
        for key, last_seen in list(self.last_seen_users.items()):
            if now - last_seen > self.spin_user_ttl_seconds:
                self.last_seen_users.pop(key, None)
                self.known_users.pop(key, None)
        names = list(self.known_users.values())
        eligible = [name for name in names if name.casefold() != str(username).casefold()]
        if not eligible:
            return "🍾 SPIN THE BOTTLE\nNeed another person to chat before spinning!"
        target = random.choice(eligible)
        question = self.social.pick("questions", prompts.QUESTIONS)
        return f"🍾 SPIN THE BOTTLE\n🌀 Bottle points to @{target}!\n💬 {question}"

    # =========================================================
    # HELP
    # =========================================================

    def help(self, arguments, username):
        """One command per line. !p m also opens the music menu."""
        p = self.prefix
        topic = arguments[0].casefold() if arguments else ""
        topic = {"m": "music", "g": "games", "f": "fun", "sys": "system"}.get(topic, topic)
        menus = {
            "music": (
                "🎵 MUSIC\n"
                f"{p}p <song> — request song\n"
                f"{p}dj <artist> — artist-only continuous DJ\n"
                f"{p}dj off — turn off artist DJ\n"
                f"{p}autoplay on|off — continuous YouTube music\n"
                f"{p}language <name> — language for next DJ songs\n"
                f"{p}djstatus — active DJ mode\n"
                f"{p}q — queue\n"
                f"{p}np — now playing\n"
                f"{p}s — skip\n"
                f"{p}pa — pause\n"
                f"{p}r — resume\n"
                f"{p}rm <#> — remove\n"
                f"{p}clear — clear queue"
            ),
            "games": (
                "🎮 GAMES\n"
                f"{p}c4 — Connect 4\n"
                f"{p}join — join C4\n"
                f"{p}drop <1-7> — drop coin\n"
                f"{p}board — show C4\n"
                f"⭕ TIC-TAC-TOE (original)\n"
                f"{p}ttt — challenge\n"
                f"{p}accept — join TTT\n"
                f"{p}move 1-9 — place X/O\n"
                f"{p}tttboard — view TTT\n"
                f"{p}tttend — end TTT\n"
                f"{p}quiz — trivia (500 mixed questions)\n"
                f"{p}riddle — riddle, answer with {p}ra\n"
                f"{p}duel <name> — friendly dice duel\n"
                f"{p}guess — number game\n"
                f"{p}rps rock — RPS\n"
                f"{p}spin — random player\n"
                f"{p}top — scores\n"
                f"{p}catch — claim random drop\n"
                f"{p}pets — your cat and dog collection\n"
                f"{p}rarities — pet drop odds"
            ),
            "fun": (
                "🎭 PARTY\n"
                f"{p}tod <name> — truth or dare for player\n"
                f"{p}truth <name> — truth for player\n"
                f"{p}dare <name> — dare for player\n"
                f"{p}wyr — would you rather\n"
                f"{p}nhie — never have I ever\n"
                f"{p}8ball <question> — magic 8 ball\n"
                f"{p}roast @name — playful roast\n"
                f"{p}j — clean joke\n"
                f"{p}meme — dashed meme\n"
                f"{p}joke18 — cheeky joke\n"
                f"{p}question — icebreaker\n"
                f"{p}spin — random player"
            ),
            "system": (
                "⚙️ SYSTEM\n"
                f"{p}reconnect — restart chat\n"
                f"{p}h — commands"
            ),
        }
        if topic in menus:
            return menus[topic]
        return (
            "🐦 CROWBOT\n"
            f"{p}h m — music\n"
            f"{p}h g — games\n"
            f"{p}h f — party\n"
            f"{p}h sys — system"
        )
