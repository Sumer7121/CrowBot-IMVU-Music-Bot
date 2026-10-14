"""Fast, dependency-free Five in a Row (Gomoku) game for IMVU chat.

One instance belongs to one room's CommandHandler.
"""
class FiveInARow:
    SIZE = 9
    WIN_LENGTH = 5

    def __init__(self):
        self.pending = None
        self.game = None

    @staticmethod
    def _same(a, b):
        return str(a).strip().casefold() == str(b).strip().casefold()

    def start(self, username):
        if self.game:
            return "Five in a Row is already running. Type !fiveboard."
        if self.pending:
            return f"Challenge from {self.pending} is waiting. Another player can type !fiveaccept."
        self.pending = str(username).strip()
        return f"Five in a Row! {self.pending} challenges the room. Type !fiveaccept to join."

    def accept(self, username):
        if self.game:
            return "A Five in a Row game is already running."
        if not self.pending:
            return "No challenge pending. Type !five to start."
        if self._same(username, self.pending):
            return "Another player must accept your challenge."
        first = self.pending
        self.game = {
            "players": (first, str(username).strip()),
            "board": [["."] * self.SIZE for _ in range(self.SIZE)],
            "turn": 0,
            "moves": 0,
        }
        self.pending = None
        return f"Five in a Row: X {first} vs O {username}. X starts! Use !fivemove A1-I9.\n{self.render()}"

    def render(self):
        if not self.game:
            return "No active Five in a Row game."
        rows = ["  A B C D E F G H I"]
        for y, row in enumerate(self.game["board"], 1):
            rows.append(f"{y} " + " ".join(row))
        return "\n".join(rows)

    def move(self, username, position):
        game = self.game
        if not game:
            return "No active game. Type !five to start."
        current = game["turn"]
        if not self._same(username, game["players"][current]):
            return f"Not your turn. Waiting for {game['players'][current]}."
        position = str(position).strip().upper()
        if len(position) != 2 or position[0] not in "ABCDEFGHI" or position[1] not in "123456789":
            return "Choose a square A1-I9, for example !fivemove E5."
        x, y = ord(position[0]) - ord("A"), int(position[1]) - 1
        board = game["board"]
        if board[y][x] != ".":
            return "That square is already occupied."
        mark = "X" if current == 0 else "O"
        board[y][x] = mark
        game["moves"] += 1
        board_text = self.render()
        if self._won(board, x, y, mark):
            winner = game["players"][current]
            self.game = None
            return f"Five in a Row winner: {winner}!\n{board_text}"
        if game["moves"] == self.SIZE * self.SIZE:
            self.game = None
            return f"Five in a Row is a draw!\n{board_text}"
        game["turn"] = 1 - current
        return f"{username} played {position}. Next: {game['players'][game['turn']]}\n{board_text}"

    def _won(self, board, x, y, mark):
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            count = 1
            for direction in (-1, 1):
                nx, ny = x + dx * direction, y + dy * direction
                while 0 <= nx < self.SIZE and 0 <= ny < self.SIZE and board[ny][nx] == mark:
                    count += 1
                    nx += dx * direction
                    ny += dy * direction
            if count >= self.WIN_LENGTH:
                return True
        return False

    def end(self, username):
        if self.game:
            if not any(self._same(username, p) for p in self.game["players"]):
                return "Only a player can end the game."
            self.game = None
            return "Five in a Row ended."
        if self.pending:
            if not self._same(username, self.pending):
                return "Only the challenger can cancel."
            self.pending = None
            return "Five in a Row challenge cancelled."
        return "No active Five in a Row game."
