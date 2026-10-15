"""Per-room CrowBot command/game state.

Music streaming is intentionally disabled for secondary rooms until each room
has a separate radio output and Cloudflare endpoint. The primary room retains
its existing, known-working music stack.
"""
from bot.commands import CommandHandler
from music.controller import MusicController


MUSIC_COMMANDS = frozenset({
    "play", "p", "ytsearch", "queue", "q", "nowplaying", "np",
    "skip", "s", "pause", "pa", "resume", "r", "stop", "clear",
    "remove", "rm",
})


class RoomSession:
    def __init__(self, room_url, prefix="!", user_manager=None):
        self.room_url = str(room_url).rstrip("/")
        self.music_controller = MusicController()
        self.command_handler = CommandHandler(
            self.music_controller, user_manager, prefix
        )
        self.welcomed_users = set()

    def process(self, username, message):
        message = str(message or "").strip()
        username = str(username or "").strip()
        if not message or not username:
            return None
        prefix = self.command_handler.prefix
        if message.casefold() == f"{prefix}ping".casefold():
            return f"🏓 CrowBot pong in this room, {username}!"
        if not message.startswith(prefix):
            # Record participant names for !spin without sending a reply.
            self.command_handler._remember_user(username)
            return None
        command = message[len(prefix):].split(maxsplit=1)[0].casefold()
        if command in MUSIC_COMMANDS:
            return (
                "🎵 Music streaming is not enabled in this room yet. "
                "Games and chat commands are available."
            )
        return self.command_handler.handle(message, username)
