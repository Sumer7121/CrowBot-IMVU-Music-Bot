import unittest
from unittest.mock import patch
from bot.party_games import PartyGames


class PartyGamesTests(unittest.TestCase):
    def setUp(self):
        self.games = PartyGames()

    def test_trivia_correct_answer_awards_point(self):
        self.games.TRIVIA_TOPICS = {"Geography": (("Capital of Japan?", ("tokyo", "tokyo city")),)}
        self.assertIn("Answer: ?a", self.games.start_trivia("?"))
        self.assertIn("Not quite", self.games.answer("Alex", "Osaka"))
        self.assertIn("+1 point", self.games.answer("Alex", "TOKYO CITY"))
        self.assertIn("Alex", self.games.leaderboard())

    def test_trivia_accepts_correct_letter_and_rejects_wrong_letter(self):
        self.games.TRIVIA_TOPICS = {"Geography": (
            ("Capital of Japan?", "tokyo"),
            ("Capital of Italy?", "rome"),
            ("Capital of France?", "paris"),
        )}
        prompt = self.games.start_trivia()
        self.assertIn("Answer: !a <letter or answer>", prompt)
        options = self.games.trivia["options"]
        self.assertEqual(set(options), {"a", "b", "c"})
        expected = self.games.trivia["answer"]
        correct = next(letter for letter, choice in options.items() if choice == expected)
        incorrect = next(letter for letter in options if letter != correct)
        self.assertIn("Not quite", self.games.answer("Alex", incorrect))
        self.assertIn("+1 point", self.games.answer("Alex", correct.upper()))

    def test_guess_higher_lower_and_win(self):
        with patch("bot.party_games.secrets.randbelow", return_value=9):
            self.games.start_guess()
        self.assertIn("Higher", self.games.try_guess("Alex", "5"))
        self.assertIn("Lower", self.games.try_guess("Alex", "15"))
        self.assertIn("+1 point", self.games.try_guess("Alex", "10"))

    def test_guess_range_and_invalid_input(self):
        self.games.start_guess()
        self.assertIn("1 to 20", self.games.try_guess("Alex", "100"))
        self.assertIn("whole number", self.games.try_guess("Alex", "banana"))

    def test_rps_scoring(self):
        with patch("bot.party_games.random.choice", return_value="scissors"):
            self.assertIn("You win", self.games.rps("Alex", "rock"))
        self.assertIn("Alex", self.games.leaderboard())
        self.assertIn("Use !rps", self.games.rps("Alex", "banana"))


if __name__ == "__main__":
    unittest.main()
