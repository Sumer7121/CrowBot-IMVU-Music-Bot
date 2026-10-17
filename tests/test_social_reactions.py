import unittest
import random
from bot.social_reactions import SocialReactions, MEMES


class SocialReactionsTests(unittest.TestCase):
    def test_memes_use_dashes(self):
        social = SocialReactions(rng=random.Random(0))
        for _ in range(len(MEMES)):
            result = social.meme()
            self.assertEqual(result.count("\n— "), 2)

    def test_shuffled_memes_no_repeat_until_exhausted(self):
        social = SocialReactions(rng=random.Random(4))
        outputs = [social.meme() for _ in MEMES]
        self.assertEqual(len(set(outputs)), len(MEMES))

    def test_mention_and_cooldown(self):
        clock = [100.0]
        social = SocialReactions(clock=lambda: clock[0])
        self.assertIsNotNone(social.mention("Alex", "hey CrowBot"))
        self.assertIsNone(social.mention("Alex", "bot?"))
        clock[0] += 31
        self.assertIsNotNone(social.mention("Alex", "bot?"))

    def test_no_command_or_false_positive(self):
        social = SocialReactions()
        self.assertIsNone(social.mention("Alex", "!p bot song"))
        self.assertIsNone(social.mention("Alex", "robotics"))
        self.assertIsNone(social.mention("Alex", "bottle"))

    def test_shuffled_pool(self):
        social = SocialReactions(rng=random.Random(5))
        values = [social.pick("test", ["a", "b", "c"]) for _ in range(3)]
        self.assertEqual(set(values), {"a", "b", "c"})


if __name__ == "__main__":
    unittest.main()
