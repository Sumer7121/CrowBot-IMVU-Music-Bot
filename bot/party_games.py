"""Lightweight room games with no external dependencies."""
import random
import secrets
import time


class PartyGames:
    # 50 curated, factual general-knowledge questions and 450 math
    # challenges (addition, subtraction, multiplication, division, percent).
    # The fixed answer key is independent of the randomly selected question.
    FACT_QUESTIONS = (
        ("What is the largest planet in our solar system?", "jupiter"),
        ("Which planet is called the Red Planet?", "mars"),
        ("What star does Earth orbit?", "sun"),
        ("Which planet is closest to the Sun?", "mercury"),
        ("Which planet is famous for its rings?", "saturn"),
        ("Which planet is often called Earth's twin?", "venus"),
        ("How many planets orbit our Sun?", "8"),
        ("What is the natural satellite of Earth called?", "moon"),
        ("What galaxy contains our solar system?", "milky way"),
        ("What force keeps planets in orbit?", "gravity"),
        ("Which animal is known for its black and white stripes?", "zebra"),
        ("What is a baby dog called?", "puppy"),
        ("What is a baby cat called?", "kitten"),
        ("Which animal is the largest living land mammal?", "elephant"),
        ("Which bird is known for mimicking human speech?", "parrot"),
        ("Which ocean animal has eight arms?", "octopus"),
        ("What do bees produce from nectar?", "honey"),
        ("What is the fastest land animal?", "cheetah"),
        ("What is the tallest living land animal?", "giraffe"),
        ("Which mammal can truly fly?", "bat"),
        ("What is the capital of France?", "paris"),
        ("What is the capital of Japan?", "tokyo"),
        ("What is the capital of Italy?", "rome"),
        ("What is the capital of Australia?", "canberra"),
        ("What is the capital of Canada?", "ottawa"),
        ("Which country is home to the Taj Mahal?", "india"),
        ("On which continent is Egypt?", "africa"),
        ("What is the largest ocean on Earth?", "pacific"),
        ("What is the largest hot desert on Earth?", "sahara"),
        ("Which country is famous for the city of Rio de Janeiro?", "brazil"),
        ("How many keys does a standard piano typically have?", "88"),
        ("How many notes are in a standard major scale?", "7"),
        ("What instrument typically has six strings and frets?", "guitar"),
        ("What do you call the speed of a musical piece?", "tempo"),
        ("What instrument is played with two sticks and pedals in a drum kit?", "drums"),
        ("What symbol indicates silence for a duration in music?", "rest"),
        ("What musical term means gradually getting louder?", "crescendo"),
        ("What do you call the repeating beat of music?", "rhythm"),
        ("What is a group of three notes sounded together usually called?", "chord"),
        ("What is the person directing an orchestra called?", "conductor"),
        ("How many sides does a triangle have?", "3"),
        ("How many sides does a hexagon have?", "6"),
        ("What is the chemical symbol for gold?", "au"),
        ("What is the chemical formula for water?", "h2o"),
        ("What gas do humans breathe in to survive?", "oxygen"),
        ("What is the freezing point of water in Celsius?", "0"),
        ("How many minutes are in one hour?", "60"),
        ("How many seconds are in one minute?", "60"),
        ("What device measures temperature?", "thermometer"),
        ("What process do plants use to make food from sunlight?", "photosynthesis"),
    )
    ADDITION = tuple((f"What is {a} + {b}?", str(a+b))
                     for a in range(11, 21) for b in range(2, 11))
    SUBTRACTION = tuple((f"What is {a} - {b}?", str(a-b))
                        for a in range(31, 41) for b in range(2, 11))
    MULTIPLICATION = tuple((f"What is {a} x {b}?", str(a*b))
                           for a in range(3, 13) for b in range(2, 11))
    DIVISION = tuple((f"What is {a*b} divided by {b}?", str(a))
                     for a in range(3, 13) for b in range(2, 11))
    PERCENTAGES = tuple((f"What is {b*10}% of {a*10}?", str(a*b))
                        for a in range(1, 11) for b in range(1, 10))
    QUESTIONS = (FACT_QUESTIONS + ADDITION + SUBTRACTION
                 + MULTIPLICATION + DIVISION + PERCENTAGES)
    assert len(QUESTIONS) == len({question for question, _ in QUESTIONS}) == 500

    RIDDLES = (
        ("What has keys but cannot open locks?", "piano"),
        ("What gets wetter the more it dries?", "towel"),
        ("What has a neck but no head?", "bottle"),
        ("What has teeth but cannot bite?", "comb"),
        ("What has one eye but cannot see?", "needle"),
        ("What has hands but cannot clap?", "clock"),
        ("What has a face and two hands but no arms?", "clock"),
        ("What has cities but no houses?", "map"),
        ("What has pages but is not a newspaper?", "book"),
        ("What goes up but never comes down?", "age"),
        ("What has a head and tail but no body?", "coin"),
        ("What breaks when you say its name?", "silence"),
        ("What can fill a room without taking space?", "light"),
        ("What can you catch but cannot throw?", "cold"),
        ("What has a bed but never sleeps?", "river"),
        ("What gets bigger the more you take away?", "hole"),
        ("What belongs to you but is used more by others?", "name"),
        ("What runs but never walks?", "water"),
        ("What has a bark but no bite?", "tree"),
        ("What has a ring but no finger?", "telephone"),
        ("What has words but never speaks?", "book"),
        ("What goes through towns but never moves?", "road"),
        ("What can travel around the world in a corner?", "stamp"),
        ("What has a spine but no bones?", "book"),
        ("What comes down but never goes up?", "rain"),
        ("What begins with T, ends with T, and has T inside?", "teapot"),
        ("What can be cracked, made, told, and played?", "joke"),
        ("What has four legs but never walks?", "table"),
        ("What can be opened but is not a door?", "book"),
        ("What has branches but no leaves?", "bank"),
        ("What has holes but can hold water?", "sponge"),
        ("What disappears as soon as you name it?", "silence"),
        ("What kind of room has no doors or windows?", "mushroom"),
        ("What has a thumb and fingers but is not alive?", "glove"),
        ("What has many needles but cannot sew?", "pine tree"),
        ("What can be served but cannot be eaten?", "tennis ball"),
        ("What gets shorter the longer it burns?", "candle"),
        ("What goes up when the rain comes down?", "umbrella"),
        ("What has a tongue but cannot talk?", "shoe"),
        ("What has a crown but no kingdom?", "tooth"),
    )

    def __init__(self):
        self.trivia = None
        self.guess = None
        self.riddle = None
        self.scores = {}
        self._trivia_remaining = []
        self._riddle_remaining = []
        self.pending_duel = None

    @staticmethod
    def _key(name):
        return str(name).strip().casefold()

    def _award(self, username):
        name = str(username).strip()
        key = self._key(name)
        current = self.scores.get(key, {"name": name, "points": 0})
        current["points"] += 1
        self.scores[key] = current
        return current["points"]

    def start_trivia(self):
        if not self._trivia_remaining:
            self._trivia_remaining = list(range(len(self.QUESTIONS)))
            random.shuffle(self._trivia_remaining)
        question, answer = self.QUESTIONS[self._trivia_remaining.pop()]
        self.trivia = {"question": question, "answer": answer}
        return f"🧠 TRIVIA | {question}\nAnswer: !a <answer>"

    def answer(self, username, answer):
        if not self.trivia:
            return "No trivia running. Use !quiz."
        if not answer:
            return "Use !a <answer>."
        expected = self.trivia["answer"]
        actual = self._key(answer).strip(" .!?")
        if actual.startswith("the "):
            actual = actual[4:]
        aliases = {
            "pacific": {"pacific ocean"},
            "sahara": {"sahara desert"},
            "sun": {"our sun"},
            "milky way": {"milky way galaxy"},
            "drums": {"drum kit", "drum set"},
            "h2o": {"water"},
        }
        if actual != expected and actual not in aliases.get(expected, set()):
            return "❌ Not quite! Try again."
        self.trivia = None
        points = self._award(username)
        return f"✅ {username} got it! +1 point (total: {points})."

    def start_riddle(self):
        if not self._riddle_remaining:
            self._riddle_remaining = list(range(len(self.RIDDLES)))
            random.shuffle(self._riddle_remaining)
        question, answer = self.RIDDLES[self._riddle_remaining.pop()]
        self.riddle = {"question": question, "answer": answer}
        return f"🧩 RIDDLE | {question}\nAnswer: !ra <answer>"

    def answer_riddle(self, username, answer):
        if not self.riddle:
            return "No riddle running. Use !riddle."
        if not answer:
            return "Use !ra <answer>."
        def normalize(value):
            value = self._key(value).strip(" .!?")
            for article in ("a ", "an ", "the "):
                if value.startswith(article):
                    return value[len(article):]
            return value
        if normalize(answer) != normalize(self.riddle["answer"]):
            return "❌ Not quite! Try again."
        self.riddle = None
        points = self._award(username)
        return f"🧩 {username} solved it! +1 point (total: {points})."

    def duel(self, username, opponent, collectibles=None, tier=None):
        challenger = str(username or "").strip()
        other = str(opponent or "").strip().lstrip("@")
        if not other:
            return "⚔️ Use !duel @username [tier] to challenge for a creature."
        if other.casefold() == challenger.casefold():
            return "⚔️ You cannot duel yourself!"
        if collectibles is None:
            return "Creature duels need the collection system to be active."
        if self.pending_duel and time.monotonic() >= self.pending_duel["expires"]:
            self.pending_duel = None
        if self.pending_duel:
            return "⚔️ A duel challenge is already waiting in this room."
        from bot.collectibles import RARITY_RANK
        tickets = collectibles.ticket_counts(challenger)
        available = [t for (kind, t), qty in tickets.items()
                     if kind == "steal" and qty > 0]
        if tier:
            tier = tier.casefold()
            if tier not in RARITY_RANK:
                return "Choose common, uncommon, rare, epic, or legendary."
            if ("steal", tier) not in tickets:
                return f"You need a {tier.upper()} Steal Ticket."
        elif available:
            tier = max(available, key=lambda value: RARITY_RANK[value])
        else:
            return "🎟 You need a Steal Ticket. Catch one with !catch."
        if not collectibles.has_eligible_pet(challenger, tier):
            return f"You need a creature at {tier.upper()} or lower to risk in this duel."
        if not collectibles.has_eligible_pet(other, tier, unshielded=True):
            return f"{other} has no unshielded creature at {tier.upper()} or lower to win."
        self.pending_duel = {
            "challenger": challenger, "opponent": other, "tier": tier,
            "expires": time.monotonic() + 60,
        }
        return (f"⚔️ CREATURE DUEL: {challenger} challenges {other}! "
                f"Ticket tier: {tier.upper()}. {other}, accept with !duel accept "
                "within 60 seconds. The winner takes one unshielded creature "
                "at or below the ticket tier.")

    def accept_duel(self, username, collectibles):
        challenge = self.pending_duel
        if not challenge:
            return "⚔️ No creature duel is waiting."
        if time.monotonic() >= challenge["expires"]:
            self.pending_duel = None
            return "⌛ The duel challenge expired."
        player = str(username or "").strip()
        if player.casefold() != challenge["opponent"].casefold():
            return f"⚔️ Only {challenge['opponent']} can accept this duel."
        if not collectibles.spend_ticket(
                challenge["challenger"], "steal", challenge["tier"]):
            self.pending_duel = None
            return "🎟 The challenger no longer has that Steal Ticket."
        first = collectibles.choose_owned_card(challenge["challenger"])
        second = collectibles.choose_owned_card(challenge["opponent"])
        self.pending_duel = None
        if not first or not second:
            return "⚔️ Both players need at least one creature card."
        first_roll, second_roll = random.randint(1, 20), random.randint(1, 20)
        first_score, second_score = first[7] + first_roll, second[7] + second_roll
        if first_score == second_score:
            return (f"🤝 DUEL DRAW! {first[4]} {first[1]} ({first_score}) vs "
                    f"{second[4]} {second[1]} ({second_score}). No creature was stolen; "
                    "the ticket was used.")
        winner = challenge["challenger"] if first_score > second_score else challenge["opponent"]
        loser = challenge["opponent"] if first_score > second_score else challenge["challenger"]
        points = self._award(winner)
        stolen = collectibles.steal_random_pet(loser, winner, challenge["tier"])
        result = (f"🏆 {winner} wins with {max(first_score, second_score)}! "
                  f"+1 duel point (total {points}).")
        if stolen:
            result += f" {winner} took {stolen[4]} {stolen[1]} [{stolen[3].upper()}] from {loser}!"
        else:
            result += " The opponent's remaining eligible creatures were shielded."
        return (f"⚔️ PET DUEL · {first[2]} {first[1]} +{first_roll} "
                f"({first_score}) vs {second[2]} {second[1]} +{second_roll} "
                f"({second_score}). {result}")

    def cancel_duel(self, username):
        challenge = self.pending_duel
        if not challenge:
            return "⚔️ No creature duel is waiting."
        player = str(username or "").strip().casefold()
        if player not in {challenge["challenger"].casefold(),
                          challenge["opponent"].casefold()}:
            return "🔒 Only duel participants can cancel this challenge."
        self.pending_duel = None
        return "⚔️ Duel challenge cancelled. No ticket was used."

    def start_guess(self):
        self.guess = {"number": secrets.randbelow(20) + 1, "attempts": 0}
        return "🎲 GUESS | I'm thinking of 1–20.\nUse !g <number>."

    def try_guess(self, username, raw):
        if not self.guess:
            return "No guessing game. Use !guess."
        try:
            number = int(str(raw).strip())
        except (TypeError, ValueError):
            return "Choose a whole number 1–20."
        if number < 1 or number > 20:
            return "Choose a number from 1 to 20."
        self.guess["attempts"] += 1
        target = self.guess["number"]
        if number != target:
            return "⬆️ Higher!" if number < target else "⬇️ Lower!"
        attempts = self.guess["attempts"]
        self.guess = None
        points = self._award(username)
        return f"🎉 {username} guessed it in {attempts} tries! +1 point (total: {points})."

    def rps(self, username, choice):
        moves = {"r": "rock", "p": "paper", "s": "scissors"}
        choice = str(choice).strip().lower()
        choice = moves.get(choice, choice)
        if choice not in moves.values():
            return "✊ RPS | Use !rps rock, paper, or scissors."
        bot = random.choice(tuple(moves.values()))
        if bot == choice:
            outcome = "🤝 Draw!"
        elif (choice, bot) in {("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")}:
            points = self._award(username)
            outcome = f"🏆 You win! +1 point (total: {points})."
        else:
            outcome = "😈 CrowBot wins!"
        return f"✊ {choice.title()} vs {bot.title()} | {outcome}"

    def leaderboard(self):
        if not self.scores:
            return "🏆 No scores yet. Play !quiz, !guess or !rps."
        leaders = sorted(self.scores.values(), key=lambda r: (-r["points"], r["name"].casefold()))[:5]
        return "🏆 TOP PLAYERS\n" + "\n".join(
            f"{i}. {row['name']} — {row['points']} pt" for i, row in enumerate(leaders, 1)
        )
