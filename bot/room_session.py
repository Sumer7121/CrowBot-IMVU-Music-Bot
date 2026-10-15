"""Per-room CrowBot command/game state.

Music streaming is intentionally disabled for secondary rooms until each room
has a separate radio output and Cloudflare endpoint. The primary room retains
its existing, known-working music stack.
"""
from bot.commands import CommandHandler
from music.controller import MusicController
from radio_server.server import RadioStreamServer
from radio_server.cloudflare import CloudflareTunnel


MUSIC_COMMANDS = frozenset({
    "play", "p", "ytsearch", "queue", "q", "nowplaying", "np",
    "skip", "s", "pause", "pa", "resume", "r", "stop", "clear",
    "remove", "rm",
})


class RoomSession:
    def __init__(self, room_url, prefix="!", user_manager=None, radio_port=None):
        self.room_url = str(room_url).rstrip("/")
        self.music_controller = MusicController()
        self.command_handler = CommandHandler(
            self.music_controller, user_manager, prefix
        )
        self.welcomed_users = set()
        self.radio_port = radio_port
        self.radio_server = None
        self.tunnel = None
        self.stream_url = ""
        if radio_port is not None:
            self.radio_server = RadioStreamServer(port=radio_port)
            self.music_controller.attach_radio_server(self.radio_server)
            self.tunnel = CloudflareTunnel()
            self.tunnel.local_url = f"http://127.0.0.1:{radio_port}"

    def start_radio(self):
        if self.radio_server is None or self.tunnel is None:
            raise RuntimeError("No radio assigned to this room")
        self.radio_server.clear_sources()
        if not self.radio_server.is_running():
            self.radio_server.start()
        self.tunnel.start()

    def stop_radio(self):
        if self.tunnel is not None and self.tunnel.is_running():
            self.tunnel.stop()
        if self.radio_server is not None and self.radio_server.is_running():
            self.radio_server.stop()
        self.stream_url = ""


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
        if command in MUSIC_COMMANDS and not self.stream_url:
            return (
                "🎵 Music streaming is not enabled in this room yet. "
                "Games and chat commands are available."
            )
        return self.command_handler.handle(message, username)
