import unittest
from bot.five_in_a_row import ConnectFour


class ConnectFourTests(unittest.TestCase):
    def setUp(self):
        self.game = ConnectFour()
        self.game.start("Alice")
        self.game.accept("Bob")

    def test_standard_board(self):
        board = self.game.game["board"]
        self.assertEqual((len(board), len(board[0])), (6, 7))

    def test_cannot_accept_own_game(self):
        game = ConnectFour()
        game.start("Alice")
        self.assertIn("Another player", game.accept("alice"))

    def test_gravity_and_stack(self):
        self.game.move("Alice", "4")
        self.assertEqual(self.game.game["board"][5][3], "X")
        self.game.move("Bob", "4")
        self.assertEqual(self.game.game["board"][4][3], "O")

    def test_turn_and_column_validation(self):
        self.assertIn("Waiting for", self.game.move("Bob", "2"))
        self.assertIn("Choose a column", self.game.move("Alice", "8"))
        self.assertIn("Bob next", self.game.move("Alice", "2"))

    def test_horizontal_win(self):
        for x in "123":
            self.game.move("Alice", x)
            self.game.move("Bob", "7")
        self.assertIn("wins CONNECT 4", self.game.move("Alice", "4"))

    def test_vertical_win(self):
        for _ in range(3):
            self.game.move("Alice", "1")
            self.game.move("Bob", "7")
        self.assertIn("wins CONNECT 4", self.game.move("Alice", "1"))

    def test_diagonal_win_detection(self):
        board = [["."] * 7 for _ in range(6)]
        for i in range(4):
            board[5 - i][i] = "X"
        self.assertTrue(self.game._won(board, 3, 2, "X"))

    def test_full_column(self):
        for row in self.game.game["board"]:
            row[0] = "X"
        self.assertIn("Column full", self.game.move("Alice", "1"))

    def test_emoji_board(self):
        self.assertIn("⚪", self.game.render())
        self.game.move("Alice", "1")
        self.assertIn("🔴", self.game.render())

    def test_end_only_players(self):
        self.assertIn("Only a player", self.game.end("Guest"))
        self.assertIn("ended", self.game.end("Alice"))


if __name__ == "__main__":
    unittest.main()
