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

RARITY_WEIGHT = {"common": 35, "uncommon": 40, "rare": 17, "epic": 7.5, "legendary": 0.5}
RARITY_RANK = {name: i for i, name in enumerate(RARITY_WEIGHT)}
RARITY_MARK = {"common": "·", "uncommon": "+", "rare": "*", "epic": "◆", "legendary": "★"}
RARITY_DOT = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣", "legendary": "🟡"}
TICKET_TYPES = ("steal", "defend", "sacrifice")
TICKET_TYPE_WEIGHT = {"steal": 40, "defend": 40, "sacrifice": 20}
TICKET_DROP_CHANCE = 0.10

# Curated name stems and animal forms produce a stable, exactly 1,000-card
# original bestiary. The creature silhouettes are ASCII/Unicode chat art.
PREFIXES = (
    ("Water", "water", "Riptide", 0),
    ("Fire", "fire", "Cinder", 0),
    ("Storm", "storm", "Cyclone", 1),
    ("Shadow", "shadow", "Night Pounce", 2),
    ("Wind", "wind", "Crosswind", 0),
    ("Lightning", "lightning", "Thunder Dive", 1),
    ("Forest", "nature", "Root Snare", 0),
    ("Electric", "electric", "Static Howl", 1),
    ("Abyss", "abyss", "Pressure Crush", 2),
    ("Stone", "earth", "Bastion", 0),
    ("Moon", "moon", "Lunar Gleam", 1),
    ("Frost", "ice", "Glacier Rush", 0),
    ("Solar", "light", "Solar Flash", 1),
    ("Iron", "metal", "Iron Guard", 0),
    ("Tide", "water", "Tidal Coil", 0),
    ("Crystal", "crystal", "Shard Burst", 2),
    ("Ember", "fire", "Spark Sprint", 0),
    ("Venom", "poison", "Venom Mist", 1),
    ("Star", "cosmic", "Starfall", 2),
    ("Magma", "lava", "Eruption", 1),
)
NAME_STEMS = {
    "Water": ("Aqua", "Riptide", "Tideborn"),
    "Fire": ("Pyro", "Cinder", "Flareborn"),
    "Storm": ("Thundra", "Tempest", "Stormveil"),
    "Shadow": ("Nightshade", "Gloam", "Dreadveil"),
    "Wind": ("Gale", "Skybound", "Whirlwind"),
    "Lightning": ("Volt", "Thunderclap", "Sparkborn"),
    "Forest": ("Verdant", "Wildroot", "Briar"),
    "Electric": ("Neon", "Arcflash", "Pulseborn"),
    "Abyss": ("Abyssal", "Voidtide", "Deepveil"),
    "Stone": ("Terra", "Flint", "Mountainheart"),
    "Moon": ("Lunar", "Moonglow", "Moonveil"),
    "Frost": ("Glacial", "Snowdrift", "Icebound"),
    "Solar": ("Radiant", "Sunflare", "Daybreak"),
    "Iron": ("Ironclad", "Forged", "Steelheart"),
    "Tide": ("Brine", "Surgebound", "Seaborn"),
    "Crystal": ("Prism", "Shardborn", "Glassfire"),
    "Ember": ("Ashen", "Sear", "Emberheart"),
    "Venom": ("Venomfang", "Toxic", "Viper"),
    "Star": ("Astral", "Starfall", "Cometborn"),
    "Magma": ("Pyroclast", "Lavaforged", "Embercore"),
}

SPECIES = (
    ("cat", "Cat", "🐈", "feline", "Whisker Pounce", "common", "small"),
    ("lion", "Lion", "🦁", "feline", "Royal Pounce", "rare", "large"),
    ("tiger", "Tiger", "🐅", "feline", "Stripe Rush", "rare", "large"),
    ("panther", "Panther", "🐈‍⬛", "feline", "Shadow Leap", "rare", "large"),
    ("leopard", "Leopard", "🐆", "feline", "Spotted Dash", "uncommon", "medium"),
    ("dog", "Dog", "🐕", "canine", "Loyal Guard", "common", "small"),
    ("wolf", "Wolf", "🐺", "canine", "Pack Howl", "uncommon", "large"),
    ("fox", "Fox", "🦊", "canine", "Clever Feint", "uncommon", "small"),
    ("bear", "Bear", "🐻", "bear", "Crushing Hug", "rare", "large"),
    ("rabbit", "Rabbit", "🐇", "rabbit", "Lucky Hop", "common", "small"),
    ("stag", "Stag", "🦌", "forest", "Antler Guard", "uncommon", "large"),
    ("eagle", "Eagle", "🦅", "bird", "Talon Dive", "uncommon", "medium"),
    ("heron", "Heron", "🐦", "bird", "Reedstep", "common", "medium"),
    ("raven", "Raven", "🐦‍⬛", "bird", "Clever Caw", "uncommon", "small"),
    ("owl", "Owl", "🦉", "bird", "Silent Sweep", "uncommon", "small"),
    ("dragon", "Dragon", "🐉", "dragon", "Element Breath", "legendary", "mythic"),
    ("tide drake", "Tide Drake", "🐉", "dragon", "Tidal Coil", "epic", "large"),
    ("ember wyrm", "Ember Wyrm", "🐉", "dragon", "Cinder Spiral", "epic", "large"),
    ("hydra", "Hydra", "🐍", "dragon", "Threefold Surge", "legendary", "mythic"),
    ("phoenix", "Phoenix", "🐦‍🔥", "phoenix", "Rebirth Flare", "legendary", "mythic"),
    ("tyrannosaurus", "Tyrannosaurus Rex", "🦖", "dinosaur", "Apex Bite", "legendary", "giant"),
    ("triceratops", "Triceratops", "🦕", "dinosaur", "Horn Rush", "epic", "large"),
    ("stegosaurus", "Stegosaurus", "🦕", "dinosaur", "Plate Wall", "rare", "large"),
    ("velociraptor", "Velociraptor", "🦖", "dinosaur", "Quick Claw", "rare", "small"),
    ("spinosaurus", "Spinosaurus", "🦖", "dinosaur", "Sail Surge", "epic", "giant"),
    ("ankylosaurus", "Ankylosaurus", "🦕", "dinosaur", "Tail Mace", "epic", "large"),
    ("brachiosaurus", "Brachiosaurus", "🦕", "dinosaur", "Canopy Reach", "epic", "giant"),
    ("diplodocus", "Diplodocus", "🦕", "dinosaur", "Longtail Sweep", "rare", "giant"),
    ("allosaurus", "Allosaurus", "🦖", "dinosaur", "Razor Lunge", "epic", "large"),
    ("carnotaurus", "Carnotaurus", "🦖", "dinosaur", "Horned Sprint", "uncommon", "large"),
    ("parasaurolophus", "Parasaurolophus", "🦕", "dinosaur", "Echo Crest", "uncommon", "large"),
    ("pachycephalosaurus", "Pachycephalosaurus", "🦕", "dinosaur", "Dome Bash", "uncommon", "medium"),
    ("iguanodon", "Iguanodon", "🦕", "dinosaur", "Thumb Spike", "uncommon", "large"),
    ("therizinosaurus", "Therizinosaurus", "🦕", "dinosaur", "Longclaw Sweep", "epic", "large"),
    ("deinonychus", "Deinonychus", "🦖", "dinosaur", "Sickle Claw", "uncommon", "small"),
    ("utahraptor", "Utahraptor", "🦖", "dinosaur", "Pack Pounce", "epic", "large"),
    ("giganotosaurus", "Giganotosaurus", "🦖", "dinosaur", "Titan Bite", "epic", "giant"),
    ("styracosaurus", "Styracosaurus", "🦕", "dinosaur", "Frill Charge", "uncommon", "large"),
    ("compsognathus", "Compsognathus", "🦖", "dinosaur", "Swift Scurry", "common", "small"),
    ("microraptor", "Microraptor", "🦖", "dinosaur", "Feather Glide", "uncommon", "small"),
    ("apatosaurus", "Apatosaurus", "🦕", "dinosaur", "Thunder Tail", "epic", "giant"),
    ("argentinosaurus", "Argentinosaurus", "🦕", "dinosaur", "Colossus Stride", "epic", "giant"),
    ("corythosaurus", "Corythosaurus", "🦕", "dinosaur", "Crested Call", "uncommon", "large"),
    ("edmontosaurus", "Edmontosaurus", "🦕", "dinosaur", "River Herd Rush", "uncommon", "large"),
    ("gallimimus", "Gallimimus", "🦖", "dinosaur", "Fleetfoot Dash", "uncommon", "medium"),
    ("oviraptor", "Oviraptor", "🦖", "dinosaur", "Nest Guardian", "uncommon", "small"),
    ("protoceratops", "Protoceratops", "🦕", "dinosaur", "Desert Frill", "uncommon", "small"),
    ("ceratosaurus", "Ceratosaurus", "🦖", "dinosaur", "Horned Ambush", "uncommon", "large"),
    ("dilophosaurus", "Dilophosaurus", "🦖", "dinosaur", "Twin Crest Cry", "uncommon", "large"),
    ("maiasaura", "Maiasaura", "🦕", "dinosaur", "Nurturing Herd", "uncommon", "large"),
)

assert len(PREFIXES) == 20 and len(SPECIES) == 50

RARITY_SAYINGS = {
    "common": (
        "{holder}, {card} says: 'Small wins still count. Keep going.'",
        "A tiny omen follows {card}: good luck often arrives quietly.",
        "{card} believes your next laugh is closer than you think, {holder}.",
        "Plot twist: {card} thinks snacks solve most side quests.",
        "The sun saved one warm little ray for {card} and its keeper.",
        "A cheerful pawprint from {card} says today can surprise you.",
        "Even {card} can carry a very uncommon good day.",
        "{holder}, {card} dares you to make someone's day brighter.",
    ),
    "uncommon": (
        "{card} picked your side, {holder}; may good luck follow its footprints.",
        "A secret shortcut appears whenever {card} joins your party.",
        "{holder}, {card} says your kindness is stronger than it looks.",
        "The clever ones know: {card} is never ordinary for long.",
        "Fortune favors the curious, and {card} has noticed you.",
        "{card} keeps a spare bit of courage for rainy afternoons.",
        "A good friend, a brave choice, and {card}: a fine little alliance.",
        "{holder}, {card} predicts a pleasant surprise before sunset.",
    ),
    "rare": (
        "FORTUNE: {card} sees a turning point just beyond the next hill.",
        "UNO REVERSE omen: {card} turns a bad turn into your comeback.",
        "{holder}, {card} keeps one lucky favor sealed beneath its sigil.",
        "The moon wrote {card} into the margin of your best story.",
        "{card} says: trust the quiet instinct that brought you this far.",
        "A rare ally changes the odds; {card} already knows the move.",
        "{holder}, {card} has hidden a little extra luck in your pocket.",
        "The next twist belongs to {card}; fate can wait its turn.",
    ),
    "epic": (
        "GOTHIC PROPHECY: {card} blooms where the midnight roses grow.",
        "{card} says: 'Let the storm speak. I have survived louder things.'",
        "A velvet-dark favor surrounds {card}; the night knows your name.",
        "{holder}, {card} turns old heartbreak into a sharper kind of courage.",
        "The shadows bow to {card}, but only kindness earns its trust.",
        "EMO ANTHEM: {card} makes the rain sound like a victory song.",
        "{card} carries a moonlit blessing for the one who keeps going.",
        "The villain's plan meets {card}: one dramatic reverse card.",
        "No crown lasts forever; {card} prefers the power of choice.",
        "{holder}, {card} promises that even dark chapters can glow.",
    ),
    "legendary": (
        "FATE REVERSED: {card} holds the final UNO REVERSE of the stars.",
        "{card} needs no throne; the night itself makes room.",
        "LEGENDARY FAVOR: {card} has chosen you for one impossible comeback.",
        "The old gods fell silent when {card} opened its eyes.",
        "{holder}, {card} says: your brave heart can change the ending.",
        "Even the villain checks the shadows before crossing {card}.",
        "A crown of comets follows {card}; destiny is only a suggestion.",
        "The last page is blank. {card} is holding the pen.",
        "{card} turns doom on its heel and walks away laughing.",
        "One impossible favor waits in the wings with {card}.",
    ),
}
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
    "mermaid": (r"  .-=-.", r" (o.o)  ~~~", r" /(  )\\_/"),
    "bat": (r" /\\_/\\", r"( •.• )><", r" /|___|\\ "),
    "moth": (r" /\\  /\\", r"(  .-.  )", r"  /   \\  "),
    "raccoon": (r"  .---.", r" (o.o)=|", r" /|___|\\ "),
}
CARD_FRAME_WIDTH = 58
CARD_FRAME_INNER = CARD_FRAME_WIDTH - 2

def _wrap_card_text(value):
    words = str(value).split()
    if not words:
        return [""]
    lines, line = [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > CARD_FRAME_INNER:
            lines.append(line)
            line = word
        else:
            line = word if not line else line + " " + word
    if line:
        lines.append(line)
    return lines

def _render_card_frame(rows, rarity="common"):
    dot = RARITY_DOT.get(rarity, "⚪")
    # Colored dots decorate both ends; UTF-8 IMVU chat supports these glyphs.
    top = "╭" + dot + "─" * 52 + dot + "╮"
    bottom = "╰" + dot + "─" * 52 + dot + "╯"
    body = []
    for row in rows:
        value = str(row)
        # Keep short ASCII creature art exactly as drawn; wrap only long copy.
        lines = [value] if len(value) <= CARD_FRAME_INNER else _wrap_card_text(value)
        for line in lines:
            line = line[:CARD_FRAME_INNER]
            body.append("│" + line.ljust(CARD_FRAME_INNER) + "│")
    return "\n".join([top, *body, bottom])

def _card_rarity(base_tier, element_bonus, size):
    tiers = tuple(RARITY_WEIGHT)
    # Legends stay scarce: only naturally legendary species with the rarest
    # element families keep the top tier. Giant bodies nudge cards upward,
    # while other creatures can rise only as far as Epic.
    if base_tier == "legendary":
        return "legendary" if element_bonus >= 2 else "epic"
    size_bonus = 1 if size in {"giant", "mythic"} else 0
    rare_element_bonus = 1 if element_bonus >= 2 else 0
    rank = RARITY_RANK[base_tier] + rare_element_bonus + size_bonus
    return tiers[min(RARITY_RANK["epic"], rank)]

LEGENDARY_TITLES = {
    ("Shadow", "Dragon"): "Eclipse Sovereign",
    ("Abyss", "Dragon"): "Voidflare",
    ("Crystal", "Dragon"): "Prismheart",
    ("Star", "Dragon"): "Astral Crown",
    ("Shadow", "Hydra"): "Nightmare Crown",
    ("Abyss", "Hydra"): "Leviathan's Ruin",
    ("Crystal", "Hydra"): "Shardstorm",
    ("Star", "Hydra"): "Worldcoil",
    ("Shadow", "Phoenix"): "Nightfire Reborn",
    ("Abyss", "Phoenix"): "Voidwing",
    ("Crystal", "Phoenix"): "Glassfire",
    ("Star", "Phoenix"): "Celestial Ash",
    ("Shadow", "Tyrannosaurus Rex"): "Dreadmaw, the Eclipse King",
    ("Abyss", "Tyrannosaurus Rex"): "Voidfang, the World Eater",
    ("Crystal", "Tyrannosaurus Rex"): "Shardback, the Titan Breaker",
    ("Star", "Tyrannosaurus Rex"): "Starfall, the Ancient Apex",
}

THEMED_CREATURES = (
    ("gothic_mermaid", "Gothic Mermaid", "🧜‍♀️", "mermaid", "gothic", "Black Tide Ballad", "epic", "medium"),
    ("moonveil_mermaid", "Moonveil Mermaid", "🧜‍♀️", "mermaid", "moon", "Silver Current", "rare", "medium"),
    ("blackwater_mermaid", "Blackwater Mermaid", "🧜‍♀️", "mermaid", "abyss", "Deepwater Lullaby", "epic", "medium"),
    ("emo_cat", "Emo Cat", "🐈‍⬛", "feline", "emo", "Rainy-Day Pounce", "uncommon", "small"),
    ("midnight_emo_cat", "Midnight Emo Cat", "🐈‍⬛", "feline", "dusk", "Velvet Pawstep", "rare", "small"),
    ("graveyard_raven", "Graveyard Raven", "🐦‍⬛", "bird", "gothic", "Cemetery Chorus", "rare", "small"),
    ("velvet_bat", "Velvet Bat", "🦇", "bat", "gothic", "Velvet Night Flight", "rare", "small"),
    ("phantom_moth", "Phantom Moth", "🦋", "moth", "shadow", "Lantern Drift", "uncommon", "small"),
    ("punk_raccoon", "Punk Raccoon", "🦝", "raccoon", "punk", "Bin-Raid Rebellion", "uncommon", "small"),
    ("neon_axolotl", "Neon Axolotl", "🦎", "sea", "neon", "Glowfin Escape", "uncommon", "small"),
    ("mourning_dove", "Mourning Dove", "🕊️", "bird", "gothic", "Midnight Lament", "uncommon", "small"),
    ("gloam_wolf", "Gloam Wolf", "🐺", "canine", "shadow", "Eclipse Howl", "rare", "large"),
)

def _creature_name(prefix, prefix_trait, animal, species_index, prefix_index):
    stems = NAME_STEMS[prefix]
    stem = stems[(species_index + prefix_index) % len(stems)]
    style = (species_index + prefix_index) % 5
    styles = (
        f"{stem} {animal}",
        f"{animal} of {prefix} Realm",
        f"{prefix_trait} {animal}",
        f"The {stem} {animal}",
        f"{animal} of {stem}",
    )
    return styles[style]

def _build_catalog():
    cards = []
    used_names = set()
    index = 0
    size_power = {"small": 0, "medium": 4, "large": 8, "giant": 12, "mythic": 10}
    rarity_power = {"common": 20, "uncommon": 35, "rare": 50,
                    "epic": 70, "legendary": 90}
    for prefix_index, (prefix, element, prefix_trait, rarity_bonus) in enumerate(PREFIXES):
        for species_index, (key, animal, emoji, family, animal_trait, base_tier, size) in enumerate(SPECIES):
            index += 1
            base_name = f"{prefix} {animal}"
            rarity = _card_rarity(base_tier, rarity_bonus, size)
            creature_name = _creature_name(prefix, prefix_trait, animal, species_index, prefix_index)
            title = LEGENDARY_TITLES.get((prefix, animal)) if rarity == "legendary" else None
            name = f"{title} — {creature_name}" if title else creature_name
            if name.casefold() in used_names:
                name = f"{name} ({base_name})"
            used_names.add(name.casefold())
            power = min(99, rarity_power[rarity] + size_power[size] + ((index * 13) % 7))
            cards.append((key, name, emoji, rarity, f"B{index:04d}",
                          element, f"{prefix_trait} {animal_trait}", power, family, size, base_name))
    for key, name, emoji, family, element, trait, base_tier, size in THEMED_CREATURES:
        index += 1
        rarity = _card_rarity(base_tier, 0, size)
        if name.casefold() in used_names:
            name = f"{name} the Unusual"
        used_names.add(name.casefold())
        power = min(99, rarity_power[rarity] + size_power[size] + ((index * 13) % 7))
        cards.append((key, name, emoji, rarity, f"B{index:04d}",
                      element, trait, power, family, size, name))
    return tuple(cards)

CATALOG = _build_catalog()
CATALOG_BY_BASE_NAME = {card[10].casefold(): card for card in CATALOG}
CATALOG_BY_NAME = dict(CATALOG_BY_BASE_NAME)
CATALOG_BY_NAME.update({card[1].casefold(): card for card in CATALOG})
CATALOG_BY_ID = {card[4].casefold(): card for card in CATALOG}
assert (len(CATALOG) == len({card[1].casefold() for card in CATALOG})
        == len(CATALOG_BY_BASE_NAME) == len(CATALOG_BY_ID) == 1012)

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
                ticket_type = self.rng.choices(
                    list(TICKET_TYPE_WEIGHT), weights=list(TICKET_TYPE_WEIGHT.values()), k=1
                )[0]
            if ticket_type not in TICKET_TYPES:
                return None
            if ticket_type == "sacrifice":
                available_tiers = [name for name in RARITY_WEIGHT if name != "legendary"]
                if tier == "legendary":
                    return None
            else:
                available_tiers = list(RARITY_WEIGHT)
            tier = tier or self.rng.choices(
                available_tiers,
                weights=[RARITY_WEIGHT[name] for name in available_tiers], k=1
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
    def _fortune(cls, card, holder=None):
        name = str(holder or "the next keeper").strip().lstrip("@") or "the next keeper"
        seed = int(card[4][1:]) + sum(ord(ch) for ch in name.casefold())
        sayings = RARITY_SAYINGS[card[3]]
        saying = sayings[seed % len(sayings)]
        return saying.format(holder="@" + name if holder else name, card=card[1])

    @classmethod
    def render_card(cls, card, quantity=1, holder=None):
        rarity, mark = card[3], RARITY_MARK[card[3]]
        art = _ART.get(card[8], _ART["dragon"])
        saying = cls._fortune(card, holder)
        rows = [
            f"{mark} {rarity.upper()} · {card[5].upper()} · {card[4]}",
            f"{card[2]} {card[1]}",
            "",
            f"{art[0]}  {cls._sigil(card)}",
            art[1], art[2], "",
            f"Trait: {card[6]}",
            f"Power: {card[7]} · Copies: x{quantity}",
            "",
            f"Card saying · {rarity.title()}",
            saying,
        ]
        return _render_card_frame(rows, card[3])

    @classmethod
    def render_compact(cls, card, quantity, holder=None):
        art = _ART.get(card[8], _ART["dragon"])
        rows = [
            f"{RARITY_MARK[card[3]]} {card[3].upper()} · {card[4]}",
            f"{card[2]} {card[1]}",
            f"{art[0]}  {cls._sigil(card)}",
            f"{card[5].title()} · POW {card[7]} · x{quantity}",
            "Saying: " + cls._fortune(card, holder),
        ]
        return _render_card_frame(rows, card[3])


    @staticmethod
    def render_ticket(ticket_type, tier, holder=None):
        icons = {"steal": "⚔", "defend": "🛡", "sacrifice": "⚒"}
        titles = {"steal": "STEAL", "defend": "DEFENSE", "sacrifice": "SACRIFICE"}
        icon, title = icons[ticket_type], titles[ticket_type]
        if ticket_type == "steal":
            effect = f"Accepted duel can steal one unshielded card up to {tier.upper()}."
            if tier != "legendary":
                effect += " Legendary cards require a Legendary ticket."
        elif ticket_type == "defend":
            effect = f"Protect one {tier.upper()} creature with !defend <card-id>."
        else:
            next_tier = tuple(RARITY_WEIGHT)[RARITY_RANK[tier] + 1]
            effect = (f"Trade 2 {tier.upper()} cards for a fresh {tier.upper()}, "
                      f"or 3 for 1 {next_tier.upper()}.")
        return (f"╭──── 🎟 {title} TICKET ────╮\n"
                f"│ {icon} TIER: {tier.upper()} │\n"
                f"│ .-========-.           │\n"
                f"│ |  .  *  .  |           │\n"
                f"│ '-========-'           │\n"
                f"│ {effect}\n"
                f"│ To: @{str(holder).lstrip('@') if holder else 'next catcher'}\n"
                f"│ Fortune: May this ticket open a fair path.\n"
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
                return (self.render_ticket(drop["ticket_type"], drop["tier"], username)
                        + f"\n🎉 {username} caught it! See !collection for your tickets.")
            card = drop["card"]
            db.execute("""INSERT INTO collections (player,item,quantity) VALUES (?,?,1)
                          ON CONFLICT(player,item) DO UPDATE SET quantity=quantity+1""",
                       (player, card[1]))
            db.commit()
        return f"🎉 {username} caught a creature card!\n{self.render_card(card, holder=username)}"

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

    def sacrifice_cards(self, username, references):
        """Consume a matching Sacrifice Ticket and 2-3 same-rank cards."""
        player = self._player(username)
        refs = [str(value).strip() for value in (references or []) if str(value).strip()]
        if len(refs) not in (2, 3):
            return "Use !sacrifice <two or three card IDs>."
        chosen = [self.lookup_card(value) for value in refs]
        if any(card is None for card in chosen):
            return "I couldn't find one of those card IDs. Use the B#### ID from !collection."
        tiers = {card[3] for card in chosen}
        if len(tiers) != 1:
            return "Sacrifice cards must all have the same rarity."
        tier = chosen[0][3]
        if tier == "legendary":
            return "Legendary cards cannot be sacrificed; protect their rarity."
        target_tier = tier if len(chosen) == 2 else tuple(RARITY_WEIGHT)[RARITY_RANK[tier] + 1]
        consumed = {}
        for card in chosen:
            consumed[card[1]] = consumed.get(card[1], 0) + 1
        options = [card for card in CATALOG
                   if card[3] == target_tier and card[4] not in {item[4] for item in chosen}]
        if not options:
            options = [card for card in CATALOG if card[3] == target_tier]
        reward = self.rng.choice(options)

        with closing(sqlite3.connect(self.database_path)) as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = db.execute("""SELECT quantity FROM ticket_inventory
                                   WHERE player=? AND ticket_type='sacrifice' AND tier=?""",
                                (player, tier)).fetchone()
            if not ticket or ticket[0] < 1:
                db.rollback()
                return f"You need a {tier.upper()} Sacrifice Card for that exchange."
            for item, amount in consumed.items():
                row = db.execute("""SELECT quantity FROM collections
                                    WHERE player=? AND item=?""", (player, item)).fetchone()
                if not row or row[0] < amount:
                    db.rollback()
                    return f"You don't own enough copies of {item} to sacrifice."
                shielded = db.execute("""SELECT quantity FROM protected_cards
                                         WHERE player=? AND item=?""",
                                      (player, item)).fetchone()
                if row[0] - (shielded[0] if shielded else 0) < amount:
                    db.rollback()
                    return f"Remove {item}'s shield before sacrificing it."
            if ticket[0] == 1:
                db.execute("""DELETE FROM ticket_inventory
                              WHERE player=? AND ticket_type='sacrifice' AND tier=?""",
                           (player, tier))
            else:
                db.execute("""UPDATE ticket_inventory SET quantity=quantity-1
                              WHERE player=? AND ticket_type='sacrifice' AND tier=?""",
                           (player, tier))
            for item, amount in consumed.items():
                remaining = db.execute("""SELECT quantity FROM collections
                                          WHERE player=? AND item=?""",
                                       (player, item)).fetchone()[0] - amount
                if remaining:
                    db.execute("""UPDATE collections SET quantity=?
                                  WHERE player=? AND item=?""", (remaining, player, item))
                else:
                    db.execute("DELETE FROM collections WHERE player=? AND item=?",
                               (player, item))
            db.execute("""INSERT INTO collections (player,item,quantity) VALUES (?,?,1)
                          ON CONFLICT(player,item) DO UPDATE SET quantity=quantity+1""",
                       (player, reward[1]))
            db.commit()
        return (f"⚒ Sacrificed {len(chosen)} {tier.upper()} cards and used your "
                f"{tier.upper()} Sacrifice Card for one {target_tier.upper()} card.\n"
                f"{self.render_card(reward, holder=username)}")

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
            lines.extend((self.render_compact(card, qty, holder=username),
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
