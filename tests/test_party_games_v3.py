"""CrowBot V3 game-deck and answer regression tests."""
import unittest
from unittest.mock import patch

from bot.party_games import PartyGames
from bot.party_prompts import (
    QUESTIONS, TOD_TRUTHS, TOD_DARES,
    WOULD_YOU_RATHER, NEVER_HAVE_I_EVER, MAGIC_EIGHT_BALL,
)
from bot.social_reactions import SocialReactions


class GameDeckTests(unittest.TestCase):
    def test_all_large_decks_have_500_distinct_prompts(self):
        for deck in (
            QUESTIONS, TOD_TRUTHS, TOD_DARES,
            WOULD_YOU_RATHER, NEVER_HAVE_I_EVER,
        ):
            self.assertEqual(len(deck), 500)
            self.assertEqual(len(set(deck)), 500)

    def test_shuffle_bag_never_repeats_until_exhausted(self):
        social = SocialReactions()
        for key, deck in (
            ("questions", QUESTIONS),
            ("wyr", WOULD_YOU_RATHER),
            ("nhie", NEVER_HAVE_I_EVER),
            ("8ball", MAGIC_EIGHT_BALL),
        ):
            drawn = [social.pick(key, deck) for _ in range(len(deck))]
            self.assertEqual(len(set(drawn)), len(deck))

    def test_trivia_has_500_unique_mixed_questions(self):
        games = PartyGames()
        self.assertEqual(len(games.QUESTIONS), 500)
        self.assertEqual(len(set(q for q, _ in games.QUESTIONS)), 500)
        self.assertTrue(any("capital" in q.lower() for q, _ in games.QUESTIONS))
        self.assertTrue(any("divided by" in q.lower() for q, _ in games.QUESTIONS))
        drawn = []
        for _ in range(500):
            games.start_trivia()
            drawn.append(games.trivia["question"])
        self.assertEqual(len(set(drawn)), 500)

    def test_riddles_do_not_repeat_within_deck(self):
        games = PartyGames()
        seen = set()
        for _ in range(len(games.RIDDLES)):
            games.start_riddle()
            seen.add(games.riddle["question"])
        self.assertEqual(len(seen), len(games.RIDDLES))

    def test_riddle_answer_awards_point(self):
        games = PartyGames()
        games.riddle = {"question": "Test?", "answer": "clock"}
        self.assertIn("solved it", games.answer_riddle("Alice", "A Clock"))
        self.assertIsNone(games.riddle)
        self.assertEqual(games.scores["alice"]["points"], 1)

    def test_wrong_riddle_answer_preserves_game(self):
        games = PartyGames()
        games.riddle = {"question": "Test?", "answer": "clock"}
        self.assertIn("Not quite", games.answer_riddle("Alice", "piano"))
        self.assertIsNotNone(games.riddle)

    def test_duel_winner_and_self_duel(self):
        games = PartyGames()
        with patch("bot.party_games.random.randint", side_effect=[5, 2]):
            self.assertIn("Alice wins", games.duel("Alice", "Bob"))
        self.assertEqual(games.scores["alice"]["points"], 1)
        self.assertIn("cannot duel yourself", games.duel("Alice", "alice"))


if __name__ == "__main__":
    unittest.main()
