import unittest
from bot import party_prompts as prompts


class PromptBankTests(unittest.TestCase):
    def test_requested_counts(self):
        self.assertEqual(len(prompts.TOD_TRUTHS) + len(prompts.TOD_DARES), 1000)
        self.assertEqual(len(prompts.ROASTS), 100)
        self.assertEqual(len(prompts.JOKES_SFW), 50)
        self.assertEqual(len(prompts.JOKES_ADULT), 50)
        self.assertEqual(len(prompts.QUESTIONS), 500)
        self.assertEqual(len(prompts.WOULD_YOU_RATHER), 500)
        self.assertEqual(len(prompts.NEVER_HAVE_I_EVER), 500)

    def test_roasts_format_with_target(self):
        for line in prompts.ROASTS:
            self.assertIn("Alex", line.format(name="Alex"))

    def test_prompts_are_nonempty(self):
        for bank in (prompts.TOD_TRUTHS, prompts.TOD_DARES,
                     prompts.ROASTS, prompts.JOKES_SFW,
                     prompts.JOKES_ADULT, prompts.QUESTIONS):
            self.assertTrue(all(isinstance(s, str) and s.strip() for s in bank))


if __name__ == "__main__":
    unittest.main()
