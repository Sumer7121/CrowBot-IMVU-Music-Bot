"""Persistent, text-card bestiary and tiered-ticket inventory."""
import random
import sqlite3
import time
from contextlib import closing
from pathlib import Path

LEGACY_PET_NAMES = {
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
    "bird": {
        "common": ["Pip","Kiwi","Peep","Doodle","Bluebell","Chirpy","Feather","Sproutlet","Skittles","Bubbles","Goldie","Tweet","Poppywing","Saffron","Nibbles","Fluffy","Cloverwing","Pebblebeak","Sunnyfinch","Mangolet","Tiki","Wren","Biscuitbeak","Dewdrop"],
        "rare": ["Azure Macaw","Moonlit Cockatiel","Ruby Finch","Silver Canary","Violet Lorikeet","Golden Conure","Cloud Budgie","Jade Parakeet","Coral Lovebird","Frosty Owl","Scarlet Tanager","Dusk Starling","Opal Dove","Royal Robin","Midnight Raven","Arctic Puffin"],
        "epic": ["Thunderwing","Aurora Phoenix","Crystal Harpy","Emerald Macaw","Stormfeather","Glacier Owl","Cosmic Hummingbird","Mystic Swan","Silver Roc","Diamond Albatross"],
        "legendary": ["Celestial Phoenix","Prismatic Peacock","Nebula Raven","Sunflare Eagle","Eclipse Owl","Shiny Thunderwing","Starfire Roc","Moonfeather Phoenix"],
    },
}

RARITY_WEIGHT = {"common": 50, "uncommon": 25, "rare": 15, "epic": 8, "legendary": 2}
RARITY_RANK = {name: i for i, name in enumerate(RARITY_WEIGHT)}
RARITY_MARK = {"common": "·", "uncommon": "+", "rare": "*", "epic": "◆", "legendary": "★"}
TICKET_TYPES = ("steal", "defend")
TICKET_DROP_CHANCE = 0.10

# Curated name stems and animal forms produce a stable, exactly 1,000-card
# original bestiary. The creature silhouettes are ASCII/Unicode chat art.
PREFIXES = (
    ("Aqualume", "water", "Riptide"),
    ("Pyroclast", "fire", "Cinder"),
    ("Triarch Tempest", "storm", "Cyclone"),
    ("Blackglass", "shadow", "Night Pounce"),
    ("Galeglass", "wind", "Crosswind"),
    ("Stormcrown", "lightning", "Thunder Dive"),
    ("Thorncrown", "nature", "Root Snare"),
    ("Voltmaw", "electric", "Static Howl"),
    ("Abyssal", "abyss", "Pressure Crush"),
    ("Stonevault", "earth", "Bastion"),
    ("Moonbeam", "moon", "Lunar Gleam"),
    ("Frostfang", "ice", "Glacier Rush"),
    ("Sunflare", "light", "Solar Flash"),
    ("Ironbark", "metal", "Iron Guard"),
    ("Shadowtide", "shadow", "Veil Strike"),
    ("Crystalfizz", "crystal", "Shard Burst"),
    ("Emberpop", "fire", "Spark Sprint"),
    ("Venomgiggle", "poison", "Venom Mist"),
    ("Starwhistle", "cosmic", "Starfall"),
    ("Cloudskip", "sky", "Updraft"),
    ("MagmaMunch", "lava", "Eruption"),
    ("MistyMirth", "mist", "Mirage"),
    ("PrismPounce", "prism", "Prism Dash"),
    ("Duskzoom", "dusk", "Dusk Ambush"),
    ("Dawnroar", "dawn", "Radiant Roar"),
)
SPECIES = (
    ("cat", "Cat", "🐈", "feline", "Whisker Pounce"),
    ("lion", "Lion", "🦁", "feline", "Royal Pounce"),
    ("tiger", "Tiger", "🐅", "feline", "Stripe Rush"),
    ("panther", "Panther", "🐈‍⬛", "feline", "Shadow Leap"),
    ("leopard", "Leopard", "🐆", "feline", "Spotted Dash"),
    ("lynx", "Lynx", "🐈", "feline", "Keen-Eye Strike"),
    ("dog", "Dog", "🐕", "canine", "Loyal Guard"),
    ("wolf", "Wolf", "🐺", "canine", "Pack Howl"),
    ("fox", "Fox", "🦊", "canine", "Clever Feint"),
    ("jackal", "Jackal", "🐺", "canine", "Dune Sprint"),
    ("bear", "Bear", "🐻", "bear", "Crushing Hug"),
    ("panda", "Panda", "🐼", "bear", "Bamboo Bonk"),
    ("rabbit", "Rabbit", "🐇", "rabbit", "Lucky Hop"),
    ("hare", "Hare", "🐇", "rabbit", "Moonlit Bound"),
    ("stag", "Stag", "🦌", "forest", "Antler Guard"),
    ("antlerbeast", "Antlerbeast", "🦌", "forest", "Briar Bind"),
    ("boar", "Boar", "🐗", "forest", "Bramble Charge"),
    ("eagle", "Eagle", "🦅", "bird", "Talon Dive"),
    ("heron", "Heron", "🐦", "bird", "Reedstep"),
    ("raven", "Raven", "🐦‍⬛", "bird", "Clever Caw"),
    ("owl", "Owl", "🦉", "bird", "Silent Sweep"),
    ("macaw", "Macaw", "🦜", "bird", "Colorburst"),
    ("finch", "Finch", "🐦", "bird", "Bright Chirp"),
    ("crane", "Crane", "🦢", "bird", "Sky Dance"),
    ("dragon", "Dragon", "🐉", "dragon", "Element Breath"),
    ("tide drake", "Tide Drake", "🐉", "dragon", "Tidal Coil"),
    ("ember wyrm", "Ember Wyrm", "🐉", "dragon", "Cinder Spiral"),
    ("hydra", "Hydra", "🐍", "dragon", "Threefold Surge"),
    ("wyvern", "Wyvern", "🐲", "dragon", "Wing Gust"),
    ("griffin", "Griffin", "🦅", "griffin", "Skyclaw"),
    ("phoenix", "Phoenix", "🐦‍🔥", "phoenix", "Rebirth Flare"),
    ("serpent", "Serpent", "🐍", "reptile", "Coil Snap"),
    ("basilisk", "Basilisk", "🦎", "reptile", "Glimmer Gaze"),
    ("tortoise", "Tortoise", "🐢", "reptile", "Bastion Shell"),
    ("crocodile", "Crocodile", "🐊", "reptile", "River Roll"),
    ("shark", "Shark", "🦈", "sea", "Fin Cutter"),
    ("orca", "Orca", "🐋", "sea", "Tide Song"),
    ("kraken", "Kraken", "🐙", "sea", "Deep Grasp"),
    ("triceratops", "Triceratops", "🦕", "dinosaur", "Horn Rush"),
    ("raptor", "Raptor", "🦖", "dinosaur", "Quick Claw"),
)
assert len(PREFIXES) == 25 and len(SPECIES) == 40

FORCED_RARITY = {
    "Aqualume Tide Drake": "rare",
    "Pyroclast Ember Wyrm": "epic",
    "Triarch Tempest Hydra": "legendary",
    "Blackglass Lion": "legendary",
    "Galeglass Heron": "uncommon",
    "Stormcrown Eagle": "rare",
    "Thorncrown Antlerbeast": "uncommon",
    "Voltmaw Wolf": "epic",
    "Abyssal Kraken": "epic",
    "Stonevault Tortoise": "rare",
    "Frostfang Raptor": "rare",
}
_FORTUNES = (
    "A kind heart makes powerful magic.",
    "Today, your courage is bigger than your worries.",
    "A little luck is following your footprints.",
    "Your next great idea is already taking shape.",
    "You bring a bright spark wherever you go.",
    "A loyal friend may be closer than you think.",
    "Your patience is quietly becoming strength.",
    "A tiny win can start a wonderful streak.",
    "The world needs your particular kind of brave.",
    "You deserve the same kindness you give others.",
    "Adventure likes your curious spirit.",
    "Your smile could outshine a legendary aura.",
)
_ART = {
    "feline": (r" /\_/\\", r"( o.o )-<", r" / >*\\"),
    "canine": (r" / \__/", r"( •ᴥ• )=>", r" /|  |\ "),
    "bear": (r"  .--.", r" (o.o )", r" /|___|\ "),
    "rabbit": (r" (\_/)", r" (o.o )", r" / >♡ "),
    "forest": (r"  /\/\ ", r" ( •.• )", r"  /|\\ "),
    "bird": (r"  .-.", r" (o )>", r" /|\\ "),
    "dragon": (r"  /\_/\\", r"<( o.o )~~~~", r"  / >==<\\"),
    "griffin": (r" \ \__/ /", r" ( ^.^ )>", r" /|  |\ "),
    "phoenix": (r" \ .*/ ", r" ( >o< )", r" /~\_/~\ "),
    "reptile": (r" __/\____", r"( o  .  )>", r" /_/ \_\ "),
    "sea": (r"  .~~~~.", r" ( o.o )>", r"  ~~~~~ "),
    "dinosaur": (r"   .---.", r" __/o.o \__", r"/_/\___/\\"),
}
def _card_rarity(index, name):
    bucket = (index * 317 + 13) % 1000
    if name in FORCED_RARITY:
        return FORCED_RARITY[name]
    if bucket < 500:
        return "common"
    if bucket < 750:
        return "uncommon"
    if bucket < 900:
        return "rare"
    if bucket < 980:
        return "epic"
    return "legendary"

def _build_catalog():
    cards = []
    index = 0
    for prefix, element, prefix_trait in PREFIXES:
        for key, animal, emoji, family, animal_trait in SPECIES:
            index += 1
            name = f"{prefix} {animal}"
            rarity = _card_rarity(index, name)
            power = {"common": 20, "uncommon": 35, "rare": 50,
                     "epic": 70, "legendary": 90}[rarity] + ((index * 13) % 11)
            cards.append((key, name, emoji, rarity, f"B{index:04d}",
                          element, f"{prefix_trait} {animal_trait}", power, family))
    return tuple(cards)

CATALOG = _build_catalog()
CATALOG_BY_NAME = {card[1].casefold(): card for card in CATALOG}
CATALOG_BY_ID = {card[4].casefold(): card for card in CATALOG}
assert len(CATALOG) == len(CATALOG_BY_NAME) == len(CATALOG_BY_ID) == 1000

LEGACY_FAMILY = {"cat": "feline", "dog": "canine", "bird": "bird"}
def _legacy_name_map():
    mapping = {}
    for kind, groups in LEGACY_PET_NAMES.items():
        family = LEGACY_FAMILY[kind]
        for rarity, old_names in groups.items():
            candidates = [card for card in CATALOG
                          if card[8] == family and card[3] == rarity]
            if not candidates:
                candidates = [card for card in CATALOG if card[8] == family]
            for i, old_name in enumerate(old_names):
                mapping[old_name.casefold()] = candidates[i % len(candidates)][1]
    return mapping

LEGACY_NAME_MAP = _legacy_name_map()

class CollectibleDrops:
    PAGE_SIZE = 4
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
            db.execute("""CREATE TABLE IF NOT EXISTS ticket_inventory (
                player TEXT NOT NULL, ticket_type TEXT NOT NULL, tier TEXT NOT NULL,
                quantity INTEGER NOT NULL, PRIMARY KEY (player, ticket_type, tier))""")
            db.execute("""CREATE TABLE IF NOT EXISTS protected_cards (
                player TEXT NOT NULL, item TEXT NOT NULL, quantity INTEGER NOT NULL,
                PRIMARY KEY (player, item))""")
            self._migrate_legacy_collections(db)
            db.commit()

    @staticmethod
    def _migrate_legacy_collections(db):
        for player, old_name, quantity in db.execute(
                "SELECT player,item,quantity FROM collections").fetchall():
            new_name = LEGACY_NAME_MAP.get(old_name.casefold())
            if not new_name:
                continue
            db.execute("""INSERT INTO collections (player,item,quantity) VALUES (?,?,?)
                          ON CONFLICT(player,item) DO UPDATE SET quantity=quantity+excluded.quantity""",
                       (player, new_name, quantity))
            db.execute("DELETE FROM collections WHERE player=? AND item=?",
                       (player, old_name))

    @staticmethod
    def _player(username):
        return str(username or "").strip().casefold()

    @staticmethod
    def _rank(tier):
        return RARITY_RANK.get(str(tier or "").casefold(), -1)

    def spawn(self, species=None, ticket_type=None, tier=None):
        if self.active is not None:
            return None
        if ticket_type:
            if ticket_type == "random":
                ticket_type = self.rng.choice(TICKET_TYPES)
            if ticket_type not in TICKET_TYPES:
                return None
            tier = tier or self.rng.choices(
                list(RARITY_WEIGHT), weights=list(RARITY_WEIGHT.values()), k=1
            )[0]
            self.active = {"kind": "ticket", "ticket_type": ticket_type,
                           "tier": tier, "deadline": self.clock() + 90}
            return self.render_ticket(ticket_type, tier) + "\nType !catch to claim it! (90s)"
        if species == "ticket":
            return self.spawn(ticket_type="random", tier=tier)
        if species and species not in {"cat", "dog", "bird", "dinosaur", "dragon"}:
            return None
        if species is None and self.rng.random() < TICKET_DROP_CHANCE:
            return self.spawn(ticket_type="random")
        rarity = self.rng.choices(
            list(RARITY_WEIGHT), weights=list(RARITY_WEIGHT.values()), k=1
        )[0]
        choices = [card for card in CATALOG
                   if card[3] == rarity and
                   (species is None or card[8] == species or card[0] == species)]
        if not choices:
            return None
        card = self.rng.choice(choices)
        self.active = {"kind": "animal", "card": card, "deadline": self.clock() + 90}
        return self.render_card(card) + "\nType !catch to claim it! (90s)"

    @staticmethod
    def _sigil(card):
        number = int(card[4][1:])
        glyphs = ".:*+-=~^"
        out = []
        for _ in range(7):
            number, digit = divmod(number, len(glyphs))
            out.append(glyphs[digit])
        return "".join(out[:4]) + " / " + "".join(out[4:])

    @classmethod
    def render_card(cls, card, quantity=1):
        rarity, mark = card[3], RARITY_MARK[card[3]]
        art = _ART.get(card[8], _ART["dragon"])
        fortune = _FORTUNES[int(card[4][1:]) % len(_FORTUNES)]
        return (f"╭─ {mark} {rarity.upper()} · {card[5].upper()} · {card[4]} ─╮\n"
                f"{card[2]} {card[1]}\n"
                f"{art[0]}  {cls._sigil(card)}\n{art[1]}\n{art[2]}\n"
                f"Trait: {card[6]} · Power {card[7]} · x{quantity}\n"
                f"Fortune: {fortune}\n╰────────────────────────╯")

    @classmethod
    def render_compact(cls, card, quantity):
        art = _ART.get(card[8], _ART["dragon"])
        return (f"{RARITY_MARK[card[3]]}{card[3][0].upper()} {card[4]} "
                f"{card[2]} {card[1]} x{quantity}\n"
                f"{art[0]} {cls._sigil(card)} {art[1]}\n"
                f"{card[5].title()} · {card[6]} · POW {card[7]}\n"
                f"Fortune: {_FORTUNES[int(card[4][1:]) % len(_FORTUNES)]}")

    @staticmethod
    def render_ticket(ticket_type, tier):
        icon = "⚔" if ticket_type == "steal" else "🛡"
        title = "STEAL" if ticket_type == "steal" else "DEFENSE"
        if ticket_type == "steal":
            effect = f"Accepted duel can take one unshielded card up to {tier.upper()}."
        else:
            effect = f"Protect one {tier.upper()} creature with !defend <card-id>."
        return (f"╭──── 🎟 {title} TICKET ────╮\n"
                f"│ {icon} TIER: {tier.upper()} │\n"
                f"│ .-========-.           │\n"
                f"│ |  .  *  .  |           │\n"
                f"│ '-========-'           │\n"
                f"│ {effect}\n"
                f"╰────────────────────────╯")

    def catch(self, username):
        player = self._player(username)
        if not player:
            return "A username is required."
        if not self.active:
            return "No drop right now! Watch the room for a surprise."
        drop = self.active
        if self.clock() > drop["deadline"]:
            self.active = None
            return "💨 That drop escaped! Next time!"
        self.active = None
        with closing(sqlite3.connect(self.database_path)) as db:
            if drop["kind"] == "ticket":
                db.execute("""INSERT INTO ticket_inventory (player,ticket_type,tier,quantity)
                              VALUES (?,?,?,1) ON CONFLICT(player,ticket_type,tier)
                              DO UPDATE SET quantity=quantity+1""",
                           (player, drop["ticket_type"], drop["tier"]))
                db.commit()
                return (f"🎉 {username} caught a {drop['tier'].upper()} "
                        f"{drop['ticket_type'].upper()} TICKET! "
                        "See !collection for your tickets.")
            card = drop["card"]
            db.execute("""INSERT INTO collections (player,item,quantity) VALUES (?,?,1)
                          ON CONFLICT(player,item) DO UPDATE SET quantity=quantity+1""",
                       (player, card[1]))
            db.commit()
        return f"🎉 {username} caught a creature card!\n{self.render_card(card)}"

    def ticket_counts(self, username):
        player = self._player(username)
        with closing(sqlite3.connect(self.database_path)) as db:
            rows = db.execute("""SELECT ticket_type,tier,quantity FROM ticket_inventory
                                 WHERE player=? ORDER BY ticket_type,tier""",
                              (player,)).fetchall()
        return {(kind, tier): qty for kind, tier, qty in rows}

    def spend_ticket(self, username, ticket_type, tier):
        player = self._player(username)
        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT quantity FROM ticket_inventory
                                WHERE player=? AND ticket_type=? AND tier=?""",
                             (player, ticket_type, tier)).fetchone()
            if not row or row[0] < 1:
                db.rollback()
                return False
            if row[0] == 1:
                db.execute("""DELETE FROM ticket_inventory
                              WHERE player=? AND ticket_type=? AND tier=?""",
                           (player, ticket_type, tier))
            else:
                db.execute("""UPDATE ticket_inventory SET quantity=quantity-1
                              WHERE player=? AND ticket_type=? AND tier=?""",
                           (player, ticket_type, tier))
            db.commit()
        return True

    def has_eligible_pet(self, username, max_tier, unshielded=False):
        player = self._player(username)
        max_rank = self._rank(max_tier)
        with closing(sqlite3.connect(self.database_path)) as db:
            rows = db.execute("SELECT item,quantity FROM collections WHERE player=?",
                              (player,)).fetchall()
            protected = dict(db.execute(
                "SELECT item,quantity FROM protected_cards WHERE player=?", (player,)
            ).fetchall()) if unshielded else {}
        return any(item.casefold() in CATALOG_BY_NAME and
                   self._rank(CATALOG_BY_NAME[item.casefold()][3]) <= max_rank and
                   qty - protected.get(item, 0) > 0 for item, qty in rows)

    def choose_owned_card(self, username):
        player = self._player(username)
        with closing(sqlite3.connect(self.database_path)) as db:
            rows = db.execute("SELECT item,quantity FROM collections WHERE player=?",
                              (player,)).fetchall()
        owned = [(CATALOG_BY_NAME[item.casefold()], qty) for item, qty in rows
                 if item.casefold() in CATALOG_BY_NAME and qty > 0]
        if not owned:
            return None
        return self.rng.choices([card for card, _ in owned],
                                weights=[qty for _, qty in owned], k=1)[0]

    def steal_random_pet(self, loser, winner, max_tier):
        loser_key, winner_key = self._player(loser), self._player(winner)
        max_rank = self._rank(max_tier)
        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT item,quantity FROM collections WHERE player=?",
                              (loser_key,)).fetchall()
            protected = dict(db.execute(
                "SELECT item,quantity FROM protected_cards WHERE player=?", (loser_key,)
            ).fetchall())
            eligible = []
            for item, qty in rows:
                card = CATALOG_BY_NAME.get(item.casefold())
                free = qty - protected.get(item, 0)
                if card and free > 0 and self._rank(card[3]) <= max_rank:
                    eligible.extend([card] * free)
            if not eligible:
                db.rollback()
                return None
            card = self.rng.choice(eligible)
            db.execute("UPDATE collections SET quantity=quantity-1 WHERE player=? AND item=?",
                       (loser_key, card[1]))
            db.execute("DELETE FROM collections WHERE player=? AND item=? AND quantity<=0",
                       (loser_key, card[1]))
            db.execute("""INSERT INTO collections(player,item,quantity) VALUES (?,?,1)
                          ON CONFLICT(player,item) DO UPDATE SET quantity=quantity+1""",
                       (winner_key, card[1]))
            db.commit()
        return card

    def defend_card(self, username, reference):
        card = self.lookup_card(reference)
        if not card:
            return "Card not found. Use its card ID from !collection."
        if card[3] == "common":
            # Common cards can be protected with a common defense ticket.
            pass
        player = self._player(username)
        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            owned = db.execute("SELECT quantity FROM collections WHERE player=? AND item=?",
                               (player, card[1])).fetchone()
            shielded = db.execute("SELECT quantity FROM protected_cards WHERE player=? AND item=?",
                                  (player, card[1])).fetchone()
            if not owned or owned[0] <= (shielded[0] if shielded else 0):
                db.rollback()
                return "You need an unshielded copy of that card."
            ticket = db.execute("""SELECT quantity FROM ticket_inventory
                                   WHERE player=? AND ticket_type='defend' AND tier=?""",
                                (player, card[3])).fetchone()
            if not ticket or ticket[0] < 1:
                db.rollback()
                return f"You need a {card[3].upper()} Defense Ticket for this card."
            if ticket[0] == 1:
                db.execute("""DELETE FROM ticket_inventory WHERE player=? AND ticket_type='defend' AND tier=?""",
                           (player, card[3]))
            else:
                db.execute("""UPDATE ticket_inventory SET quantity=quantity-1
                              WHERE player=? AND ticket_type='defend' AND tier=?""",
                           (player, card[3]))
            db.execute("""INSERT INTO protected_cards(player,item,quantity) VALUES (?,?,1)
                          ON CONFLICT(player,item) DO UPDATE SET quantity=quantity+1""",
                       (player, card[1]))
            db.commit()
        return f"🛡 {card[4]} {card[1]} is protected from steals."

    def unprotect_card(self, username, reference):
        card = self.lookup_card(reference)
        if not card:
            return "Card not found. Use its card ID from !collection."
        player = self._player(username)
        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT quantity FROM protected_cards WHERE player=? AND item=?",
                             (player, card[1])).fetchone()
            if not row:
                db.rollback()
                return "That card is not protected."
            if row[0] <= 1:
                db.execute("DELETE FROM protected_cards WHERE player=? AND item=?",
                           (player, card[1]))
            else:
                db.execute("UPDATE protected_cards SET quantity=quantity-1 WHERE player=? AND item=?",
                           (player, card[1]))
            db.commit()
        return f"Protection removed from {card[4]} {card[1]}."

    @staticmethod
    def lookup_card(reference):
        key = str(reference or "").strip().casefold()
        return CATALOG_BY_ID.get(key) or CATALOG_BY_NAME.get(key)

    def collection(self, username, page=1):
        player = self._player(username)
        with closing(sqlite3.connect(self.database_path)) as db:
            rows = db.execute("SELECT item,quantity FROM collections WHERE player=?",
                              (player,)).fetchall()
            tickets = db.execute("""SELECT ticket_type,tier,quantity FROM ticket_inventory
                                    WHERE player=?""", (player,)).fetchall()
            protected = dict(db.execute(
                "SELECT item,quantity FROM protected_cards WHERE player=?", (player,)
            ).fetchall())
        cards = [(CATALOG_BY_NAME[item.casefold()], qty, protected.get(item, 0))
                 for item, qty in rows if item.casefold() in CATALOG_BY_NAME and qty > 0]
        rank = RARITY_RANK
        cards.sort(key=lambda row: (rank[row[0][3]], row[0][1].casefold()))
        total = sum(qty for _, qty, _ in cards)
        pages = max(1, (len(cards) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 1
        page = max(1, min(page, pages))
        ticket_summary = ", ".join(
            f"{tier.title()} {kind}:{qty}" for kind, tier, qty in tickets
        ) or "none"
        lines = [f"🎒 {username}'s bestiary · {total} cards · page {page}/{pages}",
                 f"🎟 Tickets: {ticket_summary}"]
        selected = cards[(page-1)*self.PAGE_SIZE:page*self.PAGE_SIZE]
        if not selected:
            lines.append("No creature cards yet. Watch for a drop!")
        for card, qty, shielded in selected:
            lines.extend((self.render_compact(card, qty),
                          f"Shielded copies: {shielded}"))
        if page < pages:
            lines.append(f"Next: !collection {page+1}")
        if page > 1:
            lines.append(f"Previous: !collection {page-1}")
        return "\n".join(lines)

    def expired(self):
        if self.active and self.clock() > self.active["deadline"]:
            self.active = None
            return True
        return False
