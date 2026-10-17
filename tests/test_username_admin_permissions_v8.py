"""Regressions for IMVU username-only owner/mod authorization."""
import copy
import unittest
from unittest.mock import patch

from bot.room_permissions import RoomPermissions


class UsernameAdminPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.saved = {"room_policies": {}}

        def read():
            return copy.deepcopy(self.saved)

        def write(value):
            self.saved = copy.deepcopy(value)

        self.read_patch = patch("bot.room_permissions.load_settings", side_effect=read)
        self.write_patch = patch("bot.room_permissions.save_settings", side_effect=write)
        self.read_patch.start()
        self.write_patch.start()

    def tearDown(self):
        self.write_patch.stop()
        self.read_patch.stop()

    def test_owner_username_works_but_decorative_chat_name_does_not(self):
        policy = RoomPermissions("389249882-6")
        policy.set_owner_from_dashboard("Darione2")
        self.assertTrue(policy.is_owner("Darione2"))
        self.assertTrue(policy.is_owner("@darione2"))
        self.assertTrue(policy.is_mod("DARIONE2"))
        self.assertFalse(policy.is_owner("🖤 ✌🏻𝕯𝖆𝖗𝖎🖕🏻 🖤"))
        self.assertFalse(policy.is_mod("🖤 ✌🏻𝕯𝖆𝖗𝖎🖕🏻 🖤"))
        self.assertTrue(policy.may_run("lock", "Darione2"))
        self.assertFalse(policy.may_run("lock", "🖤 ✌🏻𝕯𝖆𝖗𝖎🖕🏻 🖤"))

    def test_registered_mod_can_lock_play_and_set_welcome(self):
        policy = RoomPermissions("389249882-6")
        policy.set_owner_from_dashboard("Darione2")
        self.assertTrue(policy.add_mod("AnotherUser"))
        self.assertTrue(policy.may_run("welcome", "AnotherUser"))
        self.assertTrue(policy.may_run("dj", "anotheruser"))
        name = policy.lock_command("p", {"play", "p", "lock"})
        self.assertEqual(name, "play")
        self.assertFalse(policy.may_run("play", "Visitor"))
        self.assertFalse(policy.may_run("p", "Visitor"))
        self.assertTrue(policy.may_run("play", "AnotherUser"))
        self.assertTrue(policy.may_run("play", "Darione2"))
        self.assertEqual(policy.unlock_command("play", {"play", "p", "lock"}), "play")
        self.assertTrue(policy.may_run("p", "Visitor"))

    def test_only_account_usernames_can_be_added_as_admins(self):
        policy = RoomPermissions("389249882-6")
        policy.set_owner_from_dashboard("Darione2")
        with self.assertRaises(ValueError):
            policy.add_mod("🌸 Pretty Nick 🌸")
        with self.assertRaises(ValueError):
            policy.set_owner_from_dashboard("😀 Nickname")
        self.assertFalse(policy.is_mod("🌸 Pretty Nick 🌸"))
        self.assertTrue(policy.add_mod("@Valid_Name9"))

    def test_migration_ignores_legacy_display_name_override(self):
        self.saved["room_policies"]["389249882-6"] = {
            "owner": "Darione2",
            "owner_chat_name": "FakeOtherPerson",
            "mods": ["AnotherUser", "🌸 Decorated 🌸"],
        }
        policy = RoomPermissions("389249882-6")
        self.assertTrue(policy.is_owner("Darione2"))
        self.assertFalse(policy.is_owner("FakeOtherPerson"))
        self.assertFalse(policy.is_mod("🌸 Decorated 🌸"))
        self.assertTrue(policy.is_mod("AnotherUser"))

    def test_room_policies_persist_independently(self):
        first = RoomPermissions("389249882-6")
        second = RoomPermissions("379262025-12")
        first.set_owner_from_dashboard("Darione2")
        second.set_owner_from_dashboard("OtherRoomOwner")
        first.add_mod("AdminOne")
        first.set_welcome("Welcome {user} to {room}")
        fresh_first = RoomPermissions("389249882-6")
        fresh_second = RoomPermissions("379262025-12")
        self.assertTrue(fresh_first.is_mod("AdminOne"))
        self.assertFalse(fresh_second.is_mod("AdminOne"))
        self.assertIn("Darione2", self.saved["room_policies"]["389249882-6"]["owner"])
        self.assertEqual(fresh_second.owner, "OtherRoomOwner")
        self.assertEqual(
            fresh_first.welcome_message("🌸 Display Nick"),
            "Welcome 🌸 Display Nick to 389249882-6",
        )


if __name__ == "__main__":
    unittest.main()
