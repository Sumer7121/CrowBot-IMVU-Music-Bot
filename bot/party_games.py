"""Lightweight room games with no external dependencies."""
import random
import secrets
import time


from bot.trivia_questions import TRIVIA_TOPICS


class PartyGames:
    TRIVIA_TOPICS = TRIVIA_TOPICS

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
        self._last_trivia_topic = None
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

    def start_trivia(self, prefix="!"):
        if not self._trivia_remaining:
            decks = {topic: list(questions)
                     for topic, questions in self.TRIVIA_TOPICS.items()}
            for deck in decks.values():
                random.shuffle(deck)
            rounds = []
            last_topic = self._last_trivia_topic
            while decks:
                topics = list(decks)
                random.shuffle(topics)
                if len(topics) > 1 and topics[0] == last_topic:
                    topics[0], topics[1] = topics[1], topics[0]
                for topic in topics:
                    deck = decks[topic]
                    rounds.append((topic, *deck.pop()))
                    if not deck:
                        del decks[topic]
                last_topic = topics[-1]
            self._trivia_remaining = list(reversed(rounds))
        topic, question, answer = self._trivia_remaining.pop()
        self._last_trivia_topic = topic
        accepted = (answer,) if isinstance(answer, str) else answer
        distractors = set()
        for _, other_answer in self.TRIVIA_TOPICS[topic]:
            candidate = other_answer if isinstance(other_answer, str) else other_answer[0]
            if candidate not in accepted:
                distractors.add(candidate)
        matching = [candidate for candidate in sorted(distractors)
                    if candidate.isdecimal() == accepted[0].isdecimal()]
        if len(matching) < 2:
            matching = sorted(distractors)
        choices = [accepted[0], *random.sample(matching, min(2, len(matching)))]
        random.shuffle(choices)
        options = dict(zip("abc", choices))
        self.trivia = {"topic": topic, "question": question, "answer": answer,
                       "options": options}
        lines = [f"🧠 TRIVIA · {topic}", question]
        if len(options) > 1:
            lines.extend(f"{letter.upper()}) {choice}" for letter, choice in options.items())
            lines.append(f"Answer: {prefix}a <letter or answer>")
        else:
            lines.append(f"Answer: {prefix}a <answer>")
        return "\n".join(lines)

    def answer(self, username, answer, prefix="!"):
        if not self.trivia:
            return f"No trivia running. Use {prefix}quiz."
        if not answer:
            return f"Use {prefix}a <answer>."
        expected = self.trivia["answer"]
        accepted = (expected,) if isinstance(expected, str) else expected
        actual = self._key(answer).strip(" .!?").removeprefix("the ")
        actual = " ".join(actual.split())
        if actual not in accepted:
            actual = self.trivia.get("options", {}).get(actual)
        if actual not in accepted:
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
            return "⚔️ Use !duel @username to start a friendly creature arena match."
        if other.casefold() == challenger.casefold():
            return "⚔️ You cannot duel yourself!"
        if collectibles is None:
            return "Creature arena duels need the collection system to be active."
        if self.pending_duel and time.monotonic() >= self.pending_duel["expires"]:
            self.pending_duel = None
        if self.pending_duel:
            return "⚔️ A duel challenge is already waiting in this room."
        if not collectibles.has_eligible_pet(challenger, "legendary"):
            return "You need a creature card before you can enter the arena."
        if not collectibles.has_eligible_pet(other, "legendary"):
            return f"{other} needs a creature card before entering the arena."
        self.pending_duel = {
            "challenger": challenger, "opponent": other,
            "expires": time.monotonic() + 60,
        }
        return (f"⚔️ ARENA CHALLENGE: {challenger} challenges {other}! "
                f"{other}, accept with !duel accept within 60 seconds. "
                "Arena matches award points; they never spend tickets or transfer cards.")

    def accept_duel(self, username, collectibles):
        challenge = self.pending_duel
        if not challenge:
            return "⚔️ No arena duel is waiting."
        if time.monotonic() >= challenge["expires"]:
            self.pending_duel = None
            return "⌛ The arena challenge expired."
        player = str(username or "").strip()
        if player.casefold() != challenge["opponent"].casefold():
            return f"⚔️ Only {challenge['opponent']} can accept this duel."
        first = collectibles.choose_owned_card(challenge["challenger"])
        second = collectibles.choose_owned_card(challenge["opponent"])
        self.pending_duel = None
        if not first or not second:
            return "⚔️ Both players need at least one creature card."
        first_roll, second_roll = random.randint(1, 20), random.randint(1, 20)
        first_score, second_score = first[7] + first_roll, second[7] + second_roll
        if first_score == second_score:
            return (f"🤝 ARENA DRAW! {first[1]} ({first_score}) vs "
                    f"{second[1]} ({second_score}). No ticket or card changed hands.")
        winner = challenge["challenger"] if first_score > second_score else challenge["opponent"]
        points = self._award(winner)
        return (f"⚔️ ARENA · {first[1]} +{first_roll} ({first_score}) vs "
                f"{second[1]} +{second_roll} ({second_score}). "
                f"🏆 {winner} wins +1 duel point (total {points})!")

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
