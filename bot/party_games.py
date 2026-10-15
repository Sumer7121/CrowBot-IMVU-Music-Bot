"""Lightweight room games with no external dependencies."""
import random
import secrets


class PartyGames:
    # 500 arithmetic challenges with deterministic, independently checked answers.
    # Generated once; shuffle-bag selection prevents a repeat until exhausted.
    QUESTIONS = tuple(
        (
            f"What is {left} + {right}?",
            str(left + right),
        )
        for left in range(11, 36)
        for right in range(14, 34)
    )

    def __init__(self):
        self.trivia = None
        self.guess = None
        self.scores = {}
        self._trivia_remaining = []

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
        if self._key(answer) != expected:
            return "❌ Not quite! Try again."
        self.trivia = None
        points = self._award(username)
        return f"✅ {username} got it! +1 point (total: {points})."

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
