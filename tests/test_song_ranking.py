import unittest
from music.song_ranking import candidate_score, ranked_candidates, query_parts


class SongRankingTests(unittest.TestCase):
    def test_artist_title_order(self):
        self.assertEqual(query_parts("goddess by xana"), ("goddess", "xana"))

    def test_exact_artist_track_accepted(self):
        song = {"title": "XANA - goddess (Official Audio)", "channel": "XANA", "duration": 215}
        self.assertIsNotNone(candidate_score(song, "goddess by xana"))

    def test_movie_rejected(self):
        movie = {"title": "Goddess Full Movie (2024)", "channel": "XANA Movies", "duration": 7200}
        self.assertIsNone(candidate_score(movie, "goddess by xana"))

    def test_unrelated_song_rejected(self):
        other = {"title": "Goddess - official audio", "channel": "Other Artist", "duration": 211}
        self.assertIsNone(candidate_score(other, "goddess by xana"))

    def test_reject_long_reaction_and_trailer(self):
        self.assertIsNone(candidate_score(
            {"title": "Goddess reaction video", "channel": "XANA Fans", "duration": 250}, "goddess by xana"
        ))
        self.assertIsNone(candidate_score(
            {"title": "Goddess movie trailer", "channel": "XANA", "duration": 130}, "goddess by xana"
        ))

    def test_rank_song_ahead_of_cover(self):
        candidates = [
            {"title": "Goddess Karaoke Cover", "channel": "XANA Fan", "duration": 216},
            {"title": "XANA - Goddess (Official Audio)", "channel": "XANA", "duration": 218},
        ]
        self.assertEqual(ranked_candidates(candidates, "goddess by xana")[0], candidates[1])


if __name__ == "__main__":
    unittest.main()
