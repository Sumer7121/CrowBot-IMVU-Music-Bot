"""No accidental fallback to another room when controlling IMVU Web tabs."""
import unittest
from types import SimpleNamespace

from bot.imvu_web_controller import IMVUWebController


class RoomTargetingTests(unittest.TestCase):
    def setUp(self):
        self.first = SimpleNamespace(
            url="https://www.imvu.com/next/chat/room-111-1/?some=value",
            title=lambda: "Room One",
        )
        self.second = SimpleNamespace(
            url="https://www.imvu.com/next/chat/room-222-2/",
            title=lambda: "Room Two",
        )
        self.controller = IMVUWebController()
        self.controller.context = SimpleNamespace(
            pages=[self.first, self.second]
        )

    def test_exact_target_ignores_query_parameters(self):
        matched = self.controller.find_imvu_room(
            "https://www.imvu.com/next/chat/room-111-1/"
        )
        self.assertIs(matched, self.first)

    def test_missing_target_never_falls_back_to_another_room(self):
        matched = self.controller.find_imvu_room(
            "https://www.imvu.com/next/chat/room-333-3/"
        )
        self.assertIsNone(matched)
        self.assertIsNone(self.controller.page)

    def test_discovered_urls_are_canonical(self):
        rooms = self.controller.list_imvu_rooms()
        self.assertEqual(
            [r["url"] for r in rooms],
            [
                "https://www.imvu.com/next/chat/room-111-1/",
                "https://www.imvu.com/next/chat/room-222-2/",
            ],
        )


if __name__ == "__main__":
    unittest.main()
