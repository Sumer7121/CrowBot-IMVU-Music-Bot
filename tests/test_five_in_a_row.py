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

    def test_gravity_and_stacking(self):
        self.game.move("Alice", "5")
        self.assertEqual(self.game.game["board"][8][4], "X")
        self.game.move("Bob", "5")
        self.assertEqual(self.game.game["board"][7][4], "O")

    def test_turn_and_invalid_column(self):
        self.assertIn("Not your turn", self.game.move("Bob", "1"))
        self.assertIn("Choose a column", self.game.move("Alice", "Z9"))
        self.assertIn("Next: Bob", self.game.move("Alice", "1"))

    def test_horizontal_win(self):
        for x in "1234":
            self.game.move("Alice", x)
            self.game.move("Bob", "9")
        self.assertIn("winner: Alice", self.game.move("Alice", "5"))

    def test_vertical_win(self):
        for _ in range(4):
            self.game.move("Alice", "1")
            self.game.move("Bob", "9")
        self.assertIn("winner: Alice", self.game.move("Alice", "1"))

    def test_diagonal_detection(self):
        board = [["."] * 9 for _ in range(9)]
        for i in range(5):
            board[8-i][i] = "X"
        self.assertTrue(self.game._won(board, 4, 4, "X"))

    def test_column_full(self):
        board = self.game.game["board"]
        for row in board:
            row[0] = "X"
        self.assertIn("column is full", self.game.move("Alice", "1"))

    def test_graphical_board(self):
        board = self.game.render()
        self.assertIn("⚪", board)
        self.game.move("Alice", "1")
        self.assertIn("🔴", self.game.render())

    def test_end_restricted_to_players(self):
        self.assertIn("Only a player", self.game.end("Guest"))
        self.assertIn("ended", self.game.end("Alice"))


if __name__ == "__main__":
    unittest.main()
