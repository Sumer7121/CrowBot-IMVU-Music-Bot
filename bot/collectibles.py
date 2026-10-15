"""Persistent cats-and-dogs collectible drops (legacy anime items are not dropped)."""
import random
import sqlite3
from contextlib import closing
import time
from pathlib import Path

PET_NAMES = {
    "cat": {
        "common": ["Mochi","Shadow","Biscuit","Luna","Oliver","Mittens","Whiskers","Pumpkin","Smokey","Pebbles","Patches","Marmalade","Clover","Peaches","Dusty","Mango","Cookie","Hazel","Poppy","Sprout","Chai","Waffles","Button","Toffee"],
        "rare": ["Snowball","Nori","Silver Tabby","Velvet Paws","Midnight Maine Coon","Arctic Siamese","Golden Bengal","Sapphire Ragdoll","Jade Sphynx","Twilight Calico","Marble Persian","Frosty Lynx","Ruby Tuxedo","Dusk Abyssinian","Moonlit Munchkin","Amber Scottish Fold"],
        "epic": ["Stardust","Crystal Lynx","Aurora Bengal","Emerald Panther","Thunder Whiskers","Glacier Ragdoll","Cosmic Calico","Mystic Savannah","Silver Mooncat","Royal Snow Leopard"],
        "legendary": ["Moonwhisker","Phantom Panther","Celestial Lioness","Sunflare Lynx","Eclipse Tiger","Shiny Stardust","Nebula Panther","Prismatic Sphinx"],
    },
    "dog": {
        "common": ["Buddy","Coco","Barkley","Max","Bailey","Charlie","Daisy","Teddy","Piper","Scout","Rocky","Nala","Honey","Finn","Lucky","Rover","Penny","Marley","Rusty","Oreo","Ziggy","Sunny","Maple","Archie"],
        "rare": ["Silver Husky","Golden Retriever","Blue Merle Collie","Arctic Samoyed","Chocolate Labrador","Speckled Dalmatian","Ruby Poodle","White Shepherd","Marshmallow Maltese","Royal Beagle","Midnight Doberman","Copper Corgi","Sable Shiba","Frost Foxhound","Velvet Spaniel","Spotted Terrier"],
        "epic": ["Thunderpaw","Royal Corgi","Lightning Husky","Crystal Akita","Storm Chaser Collie","Glacier Shepherd","Amber Wolfdog","Silver Samoyed","Meteor Shiba","Diamond Dalmatian"],
        "legendary": ["Aurora Wolfhound","Starlight Shiba","Celestial Husky","Golden Phoenix Retriever","Eclipse Wolfdog","Shiny Thunderpaw","Nebula Corgi","Prismatic Shepherd"],
    },
}
PET_EMOJI = {"cat": "🐱", "dog": "🐶"}
RARITY_WEIGHT = {"common": 60, "rare": 27, "epic": 10, "legendary": 3}
CATALOG = tuple(
    (kind, name, PET_EMOJI[kind], rarity)
    for kind, groups in PET_NAMES.items()
    for rarity, names in groups.items()
    for name in names
)
CATALOG_BY_NAME = {item[1]: item for item in CATALOG}
assert len(CATALOG) >= 100 and len(CATALOG_BY_NAME) == len(CATALOG)

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
        # Roll rarity first, then choose a pet within that rarity. This
        # prevents category sizes from distorting the advertised odds.
        rarity = self.rng.choices(
            list(RARITY_WEIGHT), weights=list(RARITY_WEIGHT.values()), k=1
        )[0]
        choices = [pet for pet in CATALOG if pet[3] == rarity]
        item = self.rng.choice(choices)
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
        # Keep old records intact, but only display active cat/dog pets.
        pets = [(CATALOG_BY_NAME[item], qty) for item, qty in rows
                if item in CATALOG_BY_NAME]
        if not pets:
            return f"🎒 {username}'s pet collection is empty. Try !catch!"
        # Rarest pets first, with their collectible tier clearly visible.
        rank = {"legendary": 0, "epic": 1, "rare": 2, "common": 3}
        pets.sort(key=lambda pair: (rank[pair[0][3]], pair[0][1].casefold()))
        lines = [f"🎒 {username}'s cats & dogs ({sum(q for _, q in pets)} caught)"]
        for item, quantity in pets[:20]:
            kind, name, emoji, rarity = item
            lines.append(f"• {emoji} {name} [{rarity.upper()}] x{quantity}")
        if len(pets) > 20:
            lines.append(f"+{len(pets) - 20} more types")
        return "\n".join(lines)

    def expired(self):
        if self.active and self.clock() > self.active[1]:
            self.active = None
            return True
        return False
