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

    def test_trivia_rotates_topics_without_repeating_questions(self):
        games = PartyGames()
        topics = set(games.TRIVIA_TOPICS)
        self.assertTrue({"History", "Geography", "Currencies", "Arithmetic"} <= topics)
        drawn = set()
        last_topic = None
        self.assertEqual(len(topics), 25)
        for _ in range(20):
            current_topics = set()
            for _ in topics:
                games.start_trivia()
                topic = games.trivia["topic"]
                question = games.trivia["question"]
                self.assertNotEqual(topic, last_topic)
                self.assertNotIn(question, drawn)
                drawn.add(question)
                current_topics.add(topic)
                last_topic = topic
            self.assertEqual(current_topics, topics)
        self.assertEqual(len(drawn), 500)
        games.start_trivia()
        self.assertNotEqual(games.trivia["topic"], last_topic)

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
