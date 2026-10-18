"""Saved room owner, equal moderators and per-room greeting configuration.

The owner is set only through CrowBot's trusted local GUI, never by an IMVU
chat claim. No unverified username may bootstrap moderator permissions.
"""
import re

from config.settings import load_settings, save_settings

# Safety: lock management and moderator recovery must always remain available
# to authenticated room moderators. Regular users cannot invoke these.
UNLOCKABLE = frozenset({"lock", "unlock", "locks", "mods", "requestmod", "removemod", "linkowner", "approvemod", "whoami"})
ALIASES = {
    "p": "play", "q": "queue", "np": "nowplaying",
    "s": "skip", "pa": "pause", "r": "resume", "rm": "remove",
    "lang": "language", "dropstatus": "drops",
    "pets": "collection", "cats": "collection", "dogs": "collection",
    "h": "help", "j": "joke", "tr": "truth", "d": "dare",
    "tt": "ttt", "m": "move", "g": "guess", "a": "quizanswer",
    "c4": "five", "fiveaccept": "join", "fiveboard": "board",
    "fivemove": "drop", "fiveend": "end4",
    "truthordare": "tod", "questions": "question", "qotd": "question",
    "wouldyourather": "wyr", "neverhaveiever": "nhie", "memes": "meme",
}

def canonical_command(command):
    key = str(command or "").strip().lstrip("!").casefold()
    seen = set()
    while key in ALIASES and key not in seen:
        seen.add(key)
        key = ALIASES[key]
    return key

DEFAULT_WELCOME = "👋 Welcome to {room}, {user}! Enjoy the music and games!"
RESTRICTED = frozenset({
    "skip", "s", "stop", "clear", "remove", "rm", "pause", "pa",
    "resume", "r", "dj", "autoplay", "language", "lang",
    "petdrop", "removemod", "approvemod", "lock", "unlock",
    "welcome", "welcometest",
})


def _username(name):
    """IMVU account handle; never authorize decorated/duplicated display names."""
    value = str(name or "").strip()
    if value.startswith("@"):
        value = value[1:]
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", value) else ""


def _display_name(name):
    return " ".join(str(name or "").strip().split())[:100]


class RoomPermissions:
    def __init__(self, room_id):
        self.room_id = str(room_id)
        settings = load_settings()
        state = settings.get("room_policies", {}).get(self.room_id, {})
        self.owner = _username(state.get("owner"))
        # Owner uses an account username; moderators use chat display names.
        # If IMVU chat hides an account username, the trusted GUI can bind
        # its stable chat account ID to the already-registered room owner.
        self.owner_user_id = str(state.get("owner_user_id") or "").strip()
        self.mods = {_display_name(v).casefold(): _display_name(v)
                     for v in state.get("mods", [])
                     if _display_name(v) and not self.is_owner(v)}
        self.welcome = str(state.get("welcome", DEFAULT_WELCOME))[:240]
        self.welcome_enabled = bool(state.get("welcome_enabled", True))
        self.locked_commands = {canonical_command(x) for x in state.get("locked_commands", [])}
        self.locked_commands.difference_update(UNLOCKABLE)

    def save(self):
        settings = load_settings()
        policies = settings.setdefault("room_policies", {})
        policies[self.room_id] = {
            "owner": self.owner,
            "owner_user_id": self.owner_user_id,
            "mods": list(self.mods.values()),
            "welcome": self.welcome,
            "welcome_enabled": self.welcome_enabled,
            "locked_commands": sorted(self.locked_commands),
        }
        save_settings(settings)

    def is_owner(self, username):
        handle = _username(username).casefold()
        return bool(handle and self.owner and handle == self.owner.casefold())

    def is_mod(self, username):
        handle = _display_name(username).casefold()
        return bool(handle and (self.is_owner(handle) or handle in self.mods))

    def resolve_actor(self, display_name="", account_username="", user_id=""):
        """Keep owner account verification separate from display-name mods."""
        account = self.resolve_account(account_username, user_id)
        if self.is_owner(account):
            return self.owner
        name = _display_name(display_name)
        if not self.is_owner(name) and name.casefold() in self.mods:
            return self.mods[name.casefold()]
        return ""

    def set_owner_from_dashboard(self, username):
        name = _username(username)
        if not name:
            raise ValueError("Enter the verified IMVU room owner's username.")
        if self.owner.casefold() != name.casefold():
            self.owner_user_id = ""
        self.owner = name
        self.mods.pop(name.casefold(), None)
        self.save()

    def resolve_account(self, account_username="", user_id=""):
        """Resolve account metadata for the owner and account reporting.

        Moderator authorization uses resolve_actor's display-name matching.
        """
        name = _username(account_username)
        identity = str(user_id or "").strip()
        key = name.casefold()
        if key:
            if self.owner and key == self.owner.casefold():
                if self.owner_user_id and identity and identity != self.owner_user_id:
                    return ""
                return self.owner
            if self.owner_user_id and identity == self.owner_user_id:
                return ""  # Conflicting account name cannot claim owner CID.
            return name
        if identity and self.owner_user_id and identity == self.owner_user_id:
            return self.owner
        return ""

    def link_owner_from_dashboard(self, user_id):
        identity = str(user_id or "").strip()
        if not self.owner:
            raise ValueError("Set the room owner username in the app first.")
        if not identity:
            raise ValueError("IMVU did not expose a stable account ID.")
        # One IMVU account must not be tied to conflicting roles.
        self.owner_user_id = identity
        self.save()

    def add_mod(self, username):
        name = _display_name(username)
        if not name:
            raise ValueError("Enter a display name to promote.")
        if self.is_owner(name):
            return False
        if name.casefold() in self.mods:
            return False
        self.mods[name.casefold()] = name
        self.save()
        return True

    def remove_mod(self, username):
        key = _display_name(username).casefold()
        if key not in self.mods:
            return False
        self.mods.pop(key)
        self.save()
        return True

    def set_welcome(self, message):
        text = " ".join(str(message or "").split())[:240]
        if not text:
            raise ValueError("Welcome text cannot be empty.")
        # Strict format fields: format_map would accept arbitrary fields.
        fields = re.findall(r"\{([^{}]+)\}", text)
        if any(value not in ("user", "room") for value in fields):
            raise ValueError("Only {user} and {room} placeholders are allowed.")
        self.welcome = text
        self.save()

    def welcome_message(self, username):
        if not self.welcome_enabled:
            return ""
        return self.welcome.replace("{user}", _display_name(username)).replace(
            "{room}", self.room_id
        )

    def lock_command(self, command, valid_commands):
        name = canonical_command(command)
        if name not in {canonical_command(x) for x in valid_commands}:
            raise ValueError("Unknown CrowBot command. Use !help to see valid commands.")
        if name in UNLOCKABLE:
            raise ValueError("Admin status and unlock commands cannot be locked.")
        self.locked_commands.add(name)
        self.save()
        return name

    def unlock_command(self, command, valid_commands):
        name = canonical_command(command)
        if name not in {canonical_command(x) for x in valid_commands}:
            raise ValueError("Unknown CrowBot command.")
        self.locked_commands.discard(name)
        self.save()
        return name

    def room_role(self, account_username="", user_id="", display_name=""):
        account = self.resolve_actor(display_name, account_username, user_id)
        if self.is_owner(account):
            return "owner"
        if self.is_mod(account):
            return "admin"
        return "member"

    def is_locked(self, command):
        return canonical_command(command) in self.locked_commands

    def may_run(self, command, username):
        name = canonical_command(command)
        if self.is_mod(username):
            return True
        if name in self.locked_commands:
            return False
        return command.casefold() not in RESTRICTED
