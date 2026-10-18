"""Per-room CrowBot state: dedicated music queue, radio port and tunnel.

Each RoomSession owns its own CommandHandler, MusicController and station;
commands must never reuse the primary room's music controller.
"""
import threading
import uuid
import time

from bot.room_ids import normalize_room_id
from bot.room_permissions import RoomPermissions
from music.youtube_owned import get_shared_youtube_provider
from bot.commands import CommandHandler
from music.auto_dj import AutoDJ
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
        self.room_id = normalize_room_id(self.room_url)
        self.session_key = uuid.uuid4().hex[:16]
        self._last_song_file = ""
        self._stopped = False
        self.music_controller = MusicController()
        self.command_handler = CommandHandler(
            self.music_controller, user_manager, prefix
        )
        self.command_handler.room_id = self.room_id
        self.command_handler.room_session = self.session_key
        self.dj = AutoDJ(
            self.music_controller,
            room_id=self.room_id, session_key=self.session_key
        )
        self.music_controller.now_playing_changed.connect(
            self._song_changed_for_cleanup
        )
        self.command_handler.dj_controller = self.dj
        self.welcomed_users = set()
        self.permissions = RoomPermissions(self.room_id)
        self.command_handler.room_permissions = self.permissions
        self.pending_owner_link = None
        self.pending_admin_links = {}  # pending verified username requests only
        self.command_handler.pending_admin_links = self.pending_admin_links
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

    def _song_changed_for_cleanup(self, song):
        new_file = str((song or {}).get("temporary_file") or "")
        old_file = self._last_song_file
        self._last_song_file = new_file
        if old_file and old_file != new_file:
            # FFmpeg and the Qt player may still be releasing file handles.
            timer = threading.Timer(
                30,
                lambda: get_shared_youtube_provider().release_room_track(
                    old_file, self.room_id, self.session_key
                )
            )
            timer.daemon = True
            timer.start()

    def stop_radio(self):
        if self._stopped:
            return
        self._stopped = True
        manual_worker = self.command_handler.stop_music_requests()
        dj_worker = self.dj.shutdown()
        if self.tunnel is not None and self.tunnel.is_running():
            self.tunnel.stop()
        if self.radio_server is not None and self.radio_server.is_running():
            self.radio_server.stop()
        self.stream_url = ""

        # A worker may still be finishing an interrupted yt-dlp job. Do not
        # delete the folder until those writers are completely finished.
        workers = [
            worker for worker in (manual_worker, dj_worker)
            if worker is not None and worker.isRunning()
        ]
        if not workers:
            self._cleanup_music_folder()
        else:
            for worker in workers:
                worker.finished.connect(self._cleanup_if_downloads_finished)

    def _cleanup_if_downloads_finished(self):
        workers = (
            self.command_handler.active_music_worker,
            self.dj._worker,
        )
        if all(worker is None or not worker.isRunning() for worker in workers):
            self._cleanup_music_folder()

    def _cleanup_music_folder(self):
        get_shared_youtube_provider().cleanup_room_files(
            self.room_id, self.session_key
        )


    def process(self, username, message, account_username="", user_id=""):
        message = str(message or "").strip()
        username = str(username or "").strip()
        account_username = str(account_username or "").strip()
        user_id = str(user_id or "").strip()
        if not message or not username:
            return None
        prefix = self.command_handler.prefix
        if not message.startswith(prefix):
            self.command_handler._remember_user(username)
            return None

        parts = message[len(prefix):].strip().split()
        command = parts[0].casefold() if parts else ""
        if command == "linkowner":
            if not self.permissions.owner:
                return "🔒 Configure the room owner username in CrowBot's app first."
            if account_username and not self.permissions.is_owner(account_username):
                return "🔒 This visible IMVU account is not the configured room owner."
            if not user_id and account_username and self.permissions.is_owner(account_username):
                return "✅ IMVU owner username is already recognized. Use !whoami."
            if not user_id:
                return (
                    "🔒 IMVU provided neither a profile account username nor a "
                    "stable chat account ID. CrowBot cannot securely verify ownership."
                )
            self.pending_owner_link = {
                "user_id": user_id, "display": username,
                "created_at": time.monotonic(),
            }
            return (
                "🔐 Owner verification requested for " + username +
                ". Ask the trusted CrowBot app operator to review and approve "
                "this account in the room dashboard (expires in 5 minutes)."
            )

        if command == "requestmod":
            # Only an account handle from IMVU's profile metadata or direct
            # public account lookup may request permissions, never nicknames.
            verified_handle = self.permissions.resolve_account(
                account_username, user_id
            )
            if not verified_handle or not account_username:
                return (
                    "🔒 Your IMVU account username is not available from this "
                    "chat event. CrowBot cannot safely submit a mod request "
                    "using a display name. Try again after opening your "
                    "IMVU profile in the room."
                )
            if self.permissions.is_owner(verified_handle):
                return "👑 You are already the room owner."
            if self.permissions.is_mod(verified_handle):
                return "🛡️ You are already a room admin."
            self.pending_admin_links[verified_handle.casefold()] = {
                "username": verified_handle,
                "display": username,
                "created_at": time.monotonic(),
            }
            return (
                "🛡️ @" + verified_handle +
                " requested room admin access. The room owner can approve "
                "with " + prefix + "approvemod " + verified_handle +
                " (valid for 15 minutes)."
            )

        account = self.permissions.resolve_account(account_username, user_id)
        if not self.permissions.may_run(command, account):
            if self.permissions.is_locked(command):
                return (
                    "🔒 !" + command + " is locked for regular users in this room."
                )
            if not self.permissions.owner:
                return "🔒 Set the verified room owner username in CrowBot's app first."
            if not account:
                return (
                    "🔒 Account username hidden by IMVU. The owner can use "
                    + prefix + "linkowner and get approved in the app. "
                    "Members can use " + prefix + "requestmod once IMVU exposes their username."
                )
            return "🔒 This command is for the registered room owner or admins."

        if command == "ping":
            return f"🏓 CrowBot pong in this room, {username}!"
        if command in MUSIC_COMMANDS and not self.stream_url:
            return "🎵 Music streaming is not enabled in this room yet."

        self.command_handler.actor_display_name = username
        self.command_handler.actor_account_username = account
        self.command_handler.actor_user_id = user_id
        # The handler must receive an already verified username. Do not
        # silently substitute an unverified decorated chat display name for
        # moderation decisions. Public commands can still attribute chat.
        actor = account or username
        return self.command_handler.handle(message, actor)
