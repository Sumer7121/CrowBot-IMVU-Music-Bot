"""Memes, mention replies and non-repeating random selection."""
import random
import re
import time

MEMES = (
    ("Me: one more song", "Also me: it's 4 AM"),
    ("When the DJ says last song", "The queue: 47 tracks remaining"),
    ("Me trying to be normal", "My avatar: starts dancing"),
    ("Internet: stable", "IMVU loading screen: challenge accepted"),
    ("When somebody says 'quick game'", "Three hours later: rematch?"),
    ("My brain during work", "CrowBot playlist during work: LOUD"),
    ("When the room goes quiet", "One person: !roast"),
    ("I joined for five minutes", "The sunrise: hello"),
    ("When someone steals your favorite song", "You: !p it again"),
    ("Me: I'm not competitive", "Also me after losing Connect 4: RUN IT BACK"),
    ("Wi-Fi at 99 percent", "That one message: still sending"),
    ("Everyone: be chill", "The group chat: chaos"),
    ("My plans: sleep early", "My playlist: not tonight"),
    ("When the DJ drops the beat", "My chair: becomes a dance floor"),
    ("Me opening the app", "Every notification: welcome back"),
    ("Bot: ready for requests", "Room: asks for 17 songs at once"),
    ("My fashion budget: zero", "My avatar outfits: infinite"),
    ("When your joke gets no reaction", "CrowBot: laugh track activated"),
    ("Me checking the queue", "Queue: it's complicated"),
    ("I only came to say hi", "Now I'm hosting game night"),
)
REPLIES = (
    "You called, {name}? 🐦",
    "CrowBot reporting for duty, {name}. 🎵",
    "I'm listening, {name}. What's up?",
    "Present! Need a song, game, or joke?",
    "Hey {name}! Try !h for commands.",
    "Did somebody summon the DJ? 🎧",
    "Bot online. Chaos optional. 😎",
    "Yes, {name}? My circuits are listening.",
)


class SocialReactions:
    def __init__(self, rng=None, clock=None, cooldown=30):
        self.rng = rng or random.Random()
        self.clock = clock or time.monotonic
        self.cooldown = cooldown
        self.last_reply = {}
        self.bags = {}

    def pick(self, category, options):
        """Shuffle-bag: exhaust each pool before repeating items."""
        options = tuple(options)
        if not options:
            return ""
        bag = self.bags.get(category)
        if not bag:
            bag = list(range(len(options)))
            self.rng.shuffle(bag)
            self.bags[category] = bag
        return options[bag.pop()]

    def meme(self):
        top, bottom = self.pick("memes", MEMES)
        return f"😂 MEME\n— {top}\n— {bottom}"

    def mention(self, username, message, prefix="!"):
        text = str(message or "").strip()
        if not text or text.startswith(prefix):
            return None
        if not re.search(r"(?i)(?<!\w)(?:crow[\s-]?bot|bot)(?!\w)", text):
            return None
        name = str(username or "friend").strip()
        now = self.clock()
        key = name.casefold()
        if now - self.last_reply.get(key, float("-inf")) < self.cooldown:
            return None
        self.last_reply[key] = now
        return self.pick("mention", REPLIES).format(name=name)
