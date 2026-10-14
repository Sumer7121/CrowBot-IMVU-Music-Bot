import unittest
from bot.five_in_a_row import FiveInARow


class FiveInARowTests(unittest.TestCase):
    def setUp(self):
        self.game = FiveInARow()
        self.game.start("Alice")
        self.game.accept("Bob")

    def test_inviter_cannot_accept_own_challenge(self):
        game = FiveInARow()
        game.start("Alice")
        self.assertIn("Another player", game.accept("alice"))
        self.assertIsNone(game.game)

    def test_turn_and_occupied_cell(self):
        self.assertIn("Not your turn", self.game.move("Bob", "A1"))
        self.game.move("Alice", "A1")
        self.assertIn("already occupied", self.game.move("Bob", "A1"))
        self.assertIn("Next: Alice", self.game.move("Bob", "B1"))

    def test_horizontal_win(self):
        for x in "ABCD":
            self.game.move("Alice", x + "1")
            self.game.move("Bob", x + "2")
        result = self.game.move("Alice", "E1")
        self.assertIn("winner: Alice", result)
        self.assertIsNone(self.game.game)

    def test_vertical_win(self):
        for y in range(1, 5):
            self.game.move("Alice", "A" + str(y))
            self.game.move("Bob", "B" + str(y))
        self.assertIn("winner: Alice", self.game.move("Alice", "A5"))

    def test_diagonal_win(self):
        for y, x in enumerate("ABCD", 1):
            self.game.move("Alice", x + str(y))
            self.game.move("Bob", "I" + str(y))
        self.assertIn("winner: Alice", self.game.move("Alice", "E5"))

    def test_end_restricted_to_players(self):
        self.assertIn("Only a player", self.game.end("Guest"))
        self.assertIn("ended", self.game.end("Alice"))

    def test_invalid_coordinates(self):
        self.assertIn("Choose a square", self.game.move("Alice", "Z90"))


if __name__ == "__main__":
    unittest.main()
