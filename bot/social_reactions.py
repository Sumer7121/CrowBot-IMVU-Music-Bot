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
    "Present! Need a song, a game, or a tiny bit of bird wisdom?",
    "Hey {name}! Your feathered DJ is tuned in. 🎧",
    "Did somebody summon the room's resident songbird?",
    "Bot online. Chaos optional, good music mandatory. 😎",
    "Yes, {name}? My circuits are doing a little happy dance.",
    "I heard my name and flew right over. What's happening?",
    "At your service! The playlist and I are both listening.",
    "CrowBot here, perched and ready. 🪶",
    "I was just practicing my dramatic entrance. You rang?",
    "What's the mission, {name}: music, games, or friendly nonsense?",
    "Squawk! That was my very professional notification sound.",
    "I may be a bot, but I have excellent room-listening skills.",
    "Reporting from the DJ nest. What can I do for you?",
    "You summoned the bird. I brought absolutely no worms, just vibes.",
    "I'm all ears. Well, technically, all feathers and speaker cones.",
    "A wild CrowBot appeared! What's the next move?",
    "I heard 'bot' and perked up like a bird near snack time.",
    "Ready when you are, {name}. The room's yours.",
    "The DJ booth is awake. Tell me what's on your mind.",
    "I have landed in the chat. How may I brighten the room?",
    "A message for the bot? This bird is listening. 🐦",
    "CrowBot checking in: playlist loaded, personality online.",
    "You found me! I was hiding behind the shuffle button.",
    "The room's feathered sidekick has entered the conversation.",
    "Hello, {name}! I brought a fresh reply and absolutely no repeats.",
)


class SocialReactions:
    def __init__(self, rng=None, clock=None, cooldown=0):
        self.rng = rng or random.Random()
        self.clock = clock or time.monotonic
        self.cooldown = cooldown
        self.last_reply = {}
        self.bags = {}
        self.last_picked_index = {}

    def pick(self, category, options):
        """Shuffle-bag: exhaust each pool before repeating items."""
        options = tuple(options)
        if not options:
            return ""
        bag = self.bags.get(category)
        if not bag:
            bag = list(range(len(options)))
            self.rng.shuffle(bag)
            previous = self.last_picked_index.get(category)
            # Avoid repeating the final item of the old deck as the very
            # first item of the newly shuffled deck, when possible.
            if len(bag) > 1 and bag[-1] == previous:
                bag[-1], bag[0] = bag[0], bag[-1]
            self.bags[category] = bag
        index = bag.pop()
        self.last_picked_index[category] = index
        return options[index]

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
        return self.mention_reply(name)

    def mention_reply(self, username):
        """Return the next line in the no-repeat CrowBot reply deck."""
        name = str(username or "friend").strip()
        return self.pick("mention", REPLIES).format(name=name)
