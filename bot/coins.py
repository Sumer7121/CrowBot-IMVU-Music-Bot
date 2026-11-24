"""Persistent, fictional CrowBot coins. No real-world value or cash-out."""
import json
import os
import time
from pathlib import Path
from threading import RLock

from config.runtime_paths import get_local_app_data

STARTING_COINS = 1000
HOURLY_COINS = 200
HOUR_SECONDS = 3600


class CoinWallet:
    def __init__(self, path=None, clock=None):
        self.path = Path(path) if path is not None else get_local_app_data() / "casino_coins.json"
        self.clock = clock or time.time
        self.lock = RLock()
        self.users = {}
        self._load()

    @staticmethod
    def key(username):
        return str(username or "").strip().lower()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("users"), dict):
                self.users = data["users"]
        except (ValueError, OSError):
            # Do not overwrite a broken save file until a change is made.
            self.users = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(json.dumps({"users": self.users}, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        os.replace(temp, self.path)

    def _account(self, username):
        key = self.key(username)
        if not key:
            raise ValueError("A valid IMVU username is required")
        now = float(self.clock())
        if key not in self.users:
            self.users[key] = {"name": str(username).strip(), "balance": STARTING_COINS,
                               "last_hour": now}
            self._save()
        account = self.users[key]
        # Accrual is lazy: each completed hour is credited on the next command,
        # even if CrowBot was offline. Never credit for a backwards clock.
        last = float(account.get("last_hour", now))
        completed = max(0, int((now - last) // HOUR_SECONDS))
        if completed:
            account["balance"] += completed * HOURLY_COINS
            account["last_hour"] = last + completed * HOUR_SECONDS
            self._save()
        return account

    def balance(self, username):
        with self.lock:
            return int(self._account(username)["balance"])

    def withdraw(self, username, amount):
        with self.lock:
            if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
                return False
            account = self._account(username)
            if account["balance"] < amount:
                return False
            account["balance"] -= amount
            self._save()
            return True

    def deposit(self, username, amount):
        with self.lock:
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise ValueError("Coin deposit must be a nonnegative integer")
            account = self._account(username)
            account["balance"] += amount
            self._save()
            return account["balance"]

    def status(self, username):
        with self.lock:
            account = self._account(username)
            now = float(self.clock())
            seconds = max(0, HOUR_SECONDS - int((now - account["last_hour"]) % HOUR_SECONDS))
            minutes = (seconds + 59) // 60
            return (f"🪙 {username}: {account['balance']:,} CrowCoins. "
                    f"+{HOURLY_COINS} every hour; next refill in about {minutes} min.")

    def leaderboard(self, limit=10):
        with self.lock:
            for key in list(self.users):
                self._account(self.users[key].get("name", key))
            ranked = sorted(self.users.values(),
                            key=lambda a: (-int(a["balance"]), a["name"].lower()))
            if not ranked:
                return "🏆 No CrowCoins accounts yet."
            return "🏆 RICHEST CROWBOT PLAYERS\n" + "\n".join(
                f"{i}. {a['name']} — {int(a['balance']):,} coins"
                for i, a in enumerate(ranked[:limit], 1))
