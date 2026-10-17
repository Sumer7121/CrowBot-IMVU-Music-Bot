"""Saved room owner, equal moderators and per-room greeting configuration.

The owner is set only through CrowBot's trusted local GUI, never by an IMVU
chat claim. No unverified username may bootstrap moderator permissions.
"""
from config.settings import load_settings, save_settings

# Safety: lock management and moderator recovery must always remain available
# to authenticated room moderators. Regular users cannot invoke these.
UNLOCKABLE = frozenset({"lock", "unlock", "locks", "mods"})
ALIASES = {
    "p": "play", "q": "queue", "np": "nowplaying",
    "s": "skip", "pa": "pause", "r": "resume", "rm": "remove",
    "lang": "language", "dropstatus": "drops",
    "pets": "collection", "cats": "collection", "dogs": "collection",
    "h": "help", "j": "joke", "tr": "truth", "d": "dare",
    "tt": "ttt", "m": "move", "g": "guess", "a": "quizanswer",
    "c4": "five", "fiveaccept": "join", "fiveboard": "board",
    "fivemove": "drop", "fiveend": "end4",
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
    "petdrop", "mods", "lock", "unlock", "locks",
    "welcome", "welcometest",
})


def _username(name):
    return " ".join(str(name or "").strip().lstrip("@").split())[:60]


class RoomPermissions:
    def __init__(self, room_id):
        self.room_id = str(room_id)
        settings = load_settings()
        state = settings.get("room_policies", {}).get(self.room_id, {})
        self.owner = _username(state.get("owner"))
        self.mods = {_username(v).casefold(): _username(v)
                     for v in state.get("mods", []) if _username(v)}
        self.welcome = str(state.get("welcome", DEFAULT_WELCOME))[:240]
        self.welcome_enabled = bool(state.get("welcome_enabled", True))
        self.locked_commands = {canonical_command(x) for x in state.get("locked_commands", [])}
        self.locked_commands.difference_update(UNLOCKABLE)

    def save(self):
        settings = load_settings()
        policies = settings.setdefault("room_policies", {})
        policies[self.room_id] = {
            "owner": self.owner,
            "mods": list(self.mods.values()),
            "welcome": self.welcome,
            "welcome_enabled": self.welcome_enabled,
            "locked_commands": sorted(self.locked_commands),
        }
        save_settings(settings)

    def is_mod(self, username):
        key = _username(username).casefold()
        return bool(key and (
            key == self.owner.casefold() or key in self.mods
        ))

    def set_owner_from_dashboard(self, username):
        name = _username(username)
        if not name:
            raise ValueError("Enter the verified IMVU room owner's username.")
        self.owner = name
        self.mods.pop(name.casefold(), None)
        self.save()

    def add_mod(self, username):
        name = _username(username)
        if not name:
            raise ValueError("Enter a username to promote.")
        if name.casefold() == self.owner.casefold():
            return False
        self.mods[name.casefold()] = name
        self.save()
        return True

    def remove_mod(self, username):
        key = _username(username).casefold()
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
        import re
        fields = re.findall(r"\{([^{}]+)\}", text)
        if any(value not in ("user", "room") for value in fields):
            raise ValueError("Only {user} and {room} placeholders are allowed.")
        self.welcome = text
        self.save()

    def welcome_message(self, username):
        if not self.welcome_enabled:
            return ""
        return self.welcome.replace("{user}", _username(username)).replace(
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

    def is_locked(self, command):
        return canonical_command(command) in self.locked_commands

    def may_run(self, command, username):
        name = canonical_command(command)
        if self.is_mod(username):
            return True
        if name in self.locked_commands:
            return False
        return command.casefold() not in RESTRICTED
