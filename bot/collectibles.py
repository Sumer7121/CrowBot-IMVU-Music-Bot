"""Discord-style random chat drops with persistent cat/anime collections."""
import random
import sqlite3
from contextlib import closing
import time
from pathlib import Path

CATALOG = (
    ("cat", "Mochi", "🐱", "common"),
    ("cat", "Shadow", "🐈‍⬛", "common"),
    ("cat", "Biscuit", "🐈", "common"),
    ("cat", "Snowball", "🐱", "rare"),
    ("cat", "Nori", "🐈‍⬛", "rare"),
    ("cat", "Stardust", "🐱", "epic"),
    ("cat", "Celestial Neko", "🐱", "legendary"),
    ("anime", "Kira the Blade", "⚔️", "common"),
    ("anime", "Yuna the Mage", "🪄", "common"),
    ("anime", "Ren the Runner", "🏃", "common"),
    ("anime", "Akari the Fox", "🦊", "rare"),
    ("anime", "Haru the Guardian", "🛡️", "rare"),
    ("anime", "Sora the Dragon", "🐉", "epic"),
    ("anime", "Empress Tsuki", "🌙", "legendary"),
)
RARITY_WEIGHT = {"common": 60, "rare": 27, "epic": 10, "legendary": 3}


class CollectibleDrops:
    def __init__(self, database_path=None, rng=None, clock=None):
        self.rng = rng or random.Random()
        self.clock = clock or time.monotonic
        self.active = None
        self.database_path = str(database_path or
            (Path(__file__).resolve().parent.parent / "data" / "crowbot_collectibles.sqlite"))
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS collections (
                player TEXT NOT NULL, item TEXT NOT NULL, quantity INTEGER NOT NULL,
                PRIMARY KEY (player, item))""")
            db.commit()

    def spawn(self):
        if self.active is not None:
            return None
        choices = list(CATALOG)
        item = self.rng.choices(choices, weights=[
            RARITY_WEIGHT[x[3]] for x in choices], k=1)[0]
        self.active = (item, self.clock() + 90)
        kind, name, emoji, rarity = item
        return (f"✨ WILD {kind.upper()} DROP! ✨\n"
                f"{emoji} {name} [{rarity.upper()}]\n"
                "First to type !catch wins! (90s)")

    def catch(self, username):
        if not self.active:
            return "No drop right now! Watch the room for a surprise."
        item, deadline = self.active
        if self.clock() > deadline:
            self.active = None
            return "💨 That drop escaped! Next time!"
        self.active = None
        player = str(username or "").strip()
        if not player:
            return "A username is required."
        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("""INSERT INTO collections (player, item, quantity)
                          VALUES (?, ?, 1) ON CONFLICT(player, item)
                          DO UPDATE SET quantity=quantity+1""",
                       (player.casefold(), item[1]))
            db.commit()
        return f"🎉 {player} caught {item[2]} {item[1]} [{item[3]}]! Type !collection"

    def collection(self, username):
        player = str(username or "").strip().casefold()
        with closing(sqlite3.connect(self.database_path)) as db:
            rows = db.execute(
                "SELECT item, quantity FROM collections WHERE player=? ORDER BY item",
                (player,)).fetchall()
        if not rows:
            return f"🎒 {username}'s collection is empty. Catch a wild drop!"
        return f"🎒 {username}'s collection\n" + "\n".join(
            f"• {item} x{qty}" for item, qty in rows[:20]
        ) + (f"\n+{len(rows)-20} more" if len(rows) > 20 else "")

    def expired(self):
        if self.active and self.clock() > self.active[1]:
            self.active = None
            return True
        return False
