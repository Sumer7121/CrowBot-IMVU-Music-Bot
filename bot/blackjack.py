"""Blackjack game engine for CrowBot IMVU rooms.

Optional fictional CrowCoins wagers. One independent hand per IMVU user.
The dealer stands on all 17s, including soft 17.
"""
import random
from collections import Counter

SUITS = ("♠", "♥", "♦", "♣")
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")


def hand_value(cards):
    total = sum(11 if rank == "A" else 10 if rank in ("J", "Q", "K") else int(rank)
                for rank, _ in cards)
    aces = sum(rank == "A" for rank, _ in cards)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def format_hand(cards):
    return " ".join(rank + suit for rank, suit in cards)


class Blackjack:
    """Stateful, room-chat-friendly Blackjack with per-player sessions."""

    def __init__(self, rng=None, wallet=None):
        self.rng = rng or random.SystemRandom()
        self.wallet = wallet
        self.games = {}
        self.stats = {}

    @staticmethod
    def player_key(username):
        return str(username or "").strip().lower()

    def _record(self, player, outcome):
        self.stats.setdefault(player, Counter())[outcome] += 1

    def _deck(self):
        deck = [(rank, suit) for suit in SUITS for rank in RANKS]
        self.rng.shuffle(deck)
        return deck

    def _display(self, username, game, reveal=False):
        player = game["player"]
        dealer = game["dealer"]
        if reveal:
            dealer_line = f"Dealer: {format_hand(dealer)} ({hand_value(dealer)})"
        else:
            dealer_line = f"Dealer: {dealer[0][0]}{dealer[0][1]} [hidden]"
        return (f"🃏 Blackjack — {username}\n"
                f"Your hand: {format_hand(player)} ({hand_value(player)})\n"
                + dealer_line)

    def start(self, username, prefix="!", bet=50):
        key = self.player_key(username)
        if not key:
            return "A valid IMVU username is required."
        if key in self.games:
            return (self._display(username, self.games[key]) +
                    f"\nYour game is active. Use {prefix}hit or {prefix}stand.")
        if self.wallet is not None:
            if isinstance(bet, bool) or not isinstance(bet, int) or not 1 <= bet <= 10000:
                return "Bet must be 1–10,000 CrowCoins."
            if not self.wallet.withdraw(username, bet):
                return (f"Not enough CrowCoins for a {bet:,} bet. "
                        f"Use {prefix}coins; +200 coins arrive every hour.")
        else:
            bet = 0
        deck = self._deck()
        # Deal alternately, player then dealer.
        game = {"deck": deck, "player": [deck.pop(), deck.pop()],
                "dealer": [deck.pop(), deck.pop()]}
        game["bet"] = bet
        self.games[key] = game
        player_bj = hand_value(game["player"]) == 21
        dealer_bj = hand_value(game["dealer"]) == 21
        if player_bj or dealer_bj:
            if player_bj and dealer_bj:
                return self._finish(username, key, "push", "Both have Blackjack. Push!")
            if player_bj:
                return self._finish(username, key, "wins", "Natural Blackjack! You win!", natural=True)
            return self._finish(username, key, "losses", "Dealer has Blackjack. You lose.")
        return (self._display(username, game) +
                (f"\nStake: {bet:,} CrowCoins." if bet else "") +
                f"\nType {prefix}hit to draw or {prefix}stand to hold.")

    def _finish(self, username, key, outcome, result, natural=False):
        game = self.games.pop(key)
        self._record(key, outcome)
        bet = game.get("bet", 0)
        payout = 0
        if self.wallet is not None and bet:
            if outcome == "wins":
                payout = (5 * bet // 2) if natural else (2 * bet)
            elif outcome == "push":
                payout = bet
            if payout:
                self.wallet.deposit(username, payout)
        summary = self._display(username, game, reveal=True) + "\n" + result
        if self.wallet is not None and bet:
            summary += (f"\nStake: {bet:,} | Returned: {payout:,} | "
                        f"Balance: {self.wallet.balance(username):,} CrowCoins")
        return summary

    def hit(self, username, prefix="!"):
        key = self.player_key(username)
        game = self.games.get(key)
        if game is None:
            return f"No active Blackjack game. Type {prefix}blackjack to start."
        game["player"].append(game["deck"].pop())
        value = hand_value(game["player"])
        if value > 21:
            return self._finish(username, key, "losses", "Bust! You lose.")
        if value == 21:
            return self.stand(username, prefix)
        return (self._display(username, game) +
                f"\nType {prefix}hit or {prefix}stand.")

    def stand(self, username, prefix="!"):
        key = self.player_key(username)
        game = self.games.get(key)
        if game is None:
            return f"No active Blackjack game. Type {prefix}blackjack to start."
        dealer = game["dealer"]
        while hand_value(dealer) < 17:
            dealer.append(game["deck"].pop())
        player_total = hand_value(game["player"])
        dealer_total = hand_value(dealer)
        if dealer_total > 21:
            return self._finish(username, key, "wins", "Dealer busts! You win!")
        if player_total > dealer_total:
            return self._finish(username, key, "wins", "You win!")
        if player_total < dealer_total:
            return self._finish(username, key, "losses", "Dealer wins.")
        return self._finish(username, key, "push", "Push! It's a tie.")

    def double(self, username, prefix="!"):
        """A single final draw, without wagering or changing any stake."""
        key = self.player_key(username)
        game = self.games.get(key)
        if game is None:
            return f"No active Blackjack game. Type {prefix}blackjack to start."
        if len(game["player"]) != 2:
            return "Double is only available on your first two cards."
        bet = game.get("bet", 0)
        if self.wallet is not None and bet:
            if not self.wallet.withdraw(username, bet):
                return f"Not enough CrowCoins to double. Need {bet:,} more."
            game["bet"] = bet * 2
        game["player"].append(game["deck"].pop())
        if hand_value(game["player"]) > 21:
            return self._finish(username, key, "losses", "Double draw — bust! You lose.")
        return self.stand(username, prefix)

    def hand(self, username, prefix="!"):
        key = self.player_key(username)
        game = self.games.get(key)
        if game is None:
            return f"No active Blackjack game. Type {prefix}blackjack to start."
        return self._display(username, game) + f"\n{prefix}hit | {prefix}stand | {prefix}double | {prefix}bjquit"

    def quit(self, username, prefix="!"):
        key = self.player_key(username)
        game = self.games.pop(key, None)
        if game is None:
            return f"No active Blackjack game. Type {prefix}blackjack to start."
        if self.wallet is not None and game.get("bet"):
            self.wallet.deposit(username, game["bet"])
            return "Blackjack hand closed; your stake was refunded."
        return "Blackjack hand closed. No result recorded."

    def player_stats(self, username):
        key = self.player_key(username)
        stat = self.stats.get(key, Counter())
        return (f"🃏 {username} — Blackjack: {stat['wins']} wins, "
                f"{stat['losses']} losses, {stat['push']} pushes "
                "(this bot session).")

    def leaderboard(self):
        if not self.stats:
            return "🃏 No Blackjack results yet this session."
        top = sorted(self.stats.items(), key=lambda item: (-item[1]["wins"], item[0]))[:5]
        return "🃏 Blackjack leaders (this session): " + " | ".join(
            f"{index}. {name}: {stat['wins']} wins"
            for index, (name, stat) in enumerate(top, 1))
