"""Connect Four: seven columns, six rows, gravity, four in a row."""
class ConnectFour:
    WIDTH = 7
    HEIGHT = 6
    WIN_LENGTH = 4

    def __init__(self):
        self.pending = None
        self.game = None

    @staticmethod
    def _same(a, b):
        return str(a).strip().casefold() == str(b).strip().casefold()

    def start(self, username):
        if self.game:
            return "🎮 Connect 4 is active. Use !board."
        if self.pending:
            return f"🎮 {self.pending} is waiting! Use !join."
        self.pending = str(username).strip()
        return f"🎮 CONNECT 4 | {self.pending} challenges the room!\nType !join to play."

    def accept(self, username):
        if self.game:
            return "🎮 Game already in progress."
        if not self.pending:
            return "No challenge. Type !c4."
        if self._same(username, self.pending):
            return "Another player must accept your challenge."
        first = self.pending
        self.game = {
            "players": (first, str(username).strip()),
            "board": [["."] * self.WIDTH for _ in range(self.HEIGHT)],
            "turn": 0,
            "moves": 0,
        }
        self.pending = None
        return f"🔴 {first} vs 🟡 {username}\n🔴 goes first — !drop 1-7\n{self.render()}"

    def render(self):
        if not self.game:
            return "No Connect 4 game. Type !c4."
        symbols = {".": "⚪", "X": "🔴", "O": "🟡"}
        rows = ["🎮 CONNECT 4"]
        rows.extend("".join(symbols[v] for v in row) for row in self.game["board"])
        rows.append("1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣")
        return "\n".join(rows)

    def move(self, username, position):
        game = self.game
        if not game:
            return "No game. Type !c4."
        current = game["turn"]
        if not self._same(username, game["players"][current]):
            return f"⏳ Waiting for {game['players'][current]}."
        position = str(position).strip()
        if len(position) != 1 or position not in "1234567":
            return "Choose a column: !drop 1-7."
        x = int(position) - 1
        board = game["board"]
        y = next((r for r in range(self.HEIGHT - 1, -1, -1) if board[r][x] == "."), None)
        if y is None:
            return "⚠️ Column full. Pick another."
        mark = "X" if current == 0 else "O"
        board[y][x] = mark
        game["moves"] += 1
        result = self.render()
        if self._won(board, x, y, mark):
            self.game = None
            return f"🏆 {game['players'][current]} wins CONNECT 4!\n{result}"
        if game["moves"] == self.WIDTH * self.HEIGHT:
            self.game = None
            return f"🤝 Draw! GG.\n{result}"
        game["turn"] = 1 - current
        return f"{username} dropped {position} • {game['players'][game['turn']]} next\n{result}"

    def _won(self, board, x, y, mark):
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            count = 1
            for sign in (-1, 1):
                nx, ny = x + sign * dx, y + sign * dy
                while 0 <= nx < self.WIDTH and 0 <= ny < self.HEIGHT and board[ny][nx] == mark:
                    count += 1
                    nx += sign * dx
                    ny += sign * dy
            if count >= self.WIN_LENGTH:
                return True
        return False

    def end(self, username):
        if self.game:
            if not any(self._same(username, p) for p in self.game["players"]):
                return "Only a player can end the game."
            self.game = None
            return "🛑 Connect 4 ended."
        if self.pending:
            if not self._same(username, self.pending):
                return "Only the challenger can cancel."
            self.pending = None
            return "🛑 Challenge cancelled."
        return "No Connect 4 game."

# Keep existing imports compatible while transitioning.
FiveInARow = ConnectFour
