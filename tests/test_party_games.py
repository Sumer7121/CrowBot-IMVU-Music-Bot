import unittest
from unittest.mock import patch
from bot.party_games import PartyGames


class PartyGamesTests(unittest.TestCase):
    def setUp(self):
        self.games = PartyGames()

    def test_trivia_correct_answer_awards_point(self):
        with patch("bot.party_games.random.choice", return_value=("Capital of Japan?", "tokyo")):
            self.games.start_trivia()
        self.assertIn("Not quite", self.games.answer("Alex", "Osaka"))
        self.assertIn("+1 point", self.games.answer("Alex", "TOKYO"))
        self.assertIn("Alex", self.games.leaderboard())

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
