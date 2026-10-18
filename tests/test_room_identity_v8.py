"""Regression tests for IMVU username-only moderator settings and account linking."""
import copy
import os
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bot.room_permissions import RoomPermissions


class RoomIdentityTests(unittest.TestCase):
    def setUp(self):
        self.state = {"room_policies": {}}
        def save(value):
            self.state = copy.deepcopy(value)
        self.read_patch = patch(
            "bot.room_permissions.load_settings",
            side_effect=lambda: copy.deepcopy(self.state),
        )
        self.save_patch = patch(
            "bot.room_permissions.save_settings", side_effect=save
        )
        self.read_patch.start()
        self.save_patch.start()
        self.addCleanup(self.read_patch.stop)
        self.addCleanup(self.save_patch.stop)

    def test_owner_username_can_bind_chat_account_id_without_using_nickname(self):
        p = RoomPermissions("389249882-6")
        p.set_owner_from_dashboard("Sleepyhead222")
        self.assertFalse(p.is_owner("Sleepy"))
        self.assertEqual(p.resolve_account("", "id-111"), "")
        p.link_owner_from_dashboard("id-111")
        self.assertEqual(p.resolve_account("", "id-111"), "Sleepyhead222")
        self.assertTrue(p.may_run("lock", p.resolve_account("", "id-111")))
        self.assertFalse(p.may_run("lock", p.resolve_account("", "id-222")))
        self.assertTrue(p.is_owner("Sleepyhead222"))
        self.assertFalse(p.is_owner("Sleepy"))
        restarted = RoomPermissions("389249882-6")
        self.assertEqual(restarted.resolve_account("", "id-111"), "Sleepyhead222")

    def test_new_owner_reassignment_revokes_old_chat_binding(self):
        p = RoomPermissions("111-1")
        p.set_owner_from_dashboard("FirstOwner")
        p.link_owner_from_dashboard("id-first")
        p.set_owner_from_dashboard("SecondOwner")
        self.assertEqual(p.resolve_account("", "id-first"), "")
        self.assertEqual(p.owner, "SecondOwner")

    def test_admins_are_saved_by_username_without_any_id_linking(self):
        p = RoomPermissions("111-1")
        p.set_owner_from_dashboard("Owner123")
        p.link_owner_from_dashboard("id-owner")
        self.assertTrue(p.add_mod("Alice_42"))
        self.assertEqual(p.resolve_account("Alice_42"), "Alice_42")
        self.assertEqual(p.resolve_account("", "id-admin"), "")
        self.assertTrue(p.is_mod(p.resolve_account("Alice_42")))
        self.assertFalse(p.is_owner("Alice_42"))
        self.assertFalse(p.add_mod("Alice_42"))
        with self.assertRaises(ValueError):
            p.add_mod("✨ decorative nickname")
        again = RoomPermissions("111-1")
        self.assertTrue(again.is_mod("Alice_42"))
        self.assertTrue(p.remove_mod("alice_42"))
        self.assertFalse(p.is_mod("Alice_42"))

    def test_admin_lock_is_room_specific_and_aliases_are_enforced(self):
        first = RoomPermissions("111-1")
        second = RoomPermissions("222-2")
        first.set_owner_from_dashboard("Owner123")
        first.link_owner_from_dashboard("owner-id")
        first.lock_command("p", ["play", "p", "lock", "unlock"])
        self.assertTrue(first.is_locked("play"))
        self.assertTrue(first.is_locked("p"))
        self.assertFalse(first.may_run("p", "RegularMember"))
        self.assertTrue(first.may_run("p", first.resolve_account("", "owner-id")))
        self.assertTrue(second.may_run("p", "RegularMember"))
        first.unlock_command("play", ["play", "p", "lock", "unlock"])
        self.assertTrue(first.may_run("p", "RegularMember"))

    def test_admin_can_manage_welcome_but_cannot_grant_other_admins(self):
        p = RoomPermissions("111-1")
        p.set_owner_from_dashboard("RoomOwner")
        p.add_mod("Alice")
        actor = p.resolve_account("Alice")
        self.assertTrue(p.is_mod(actor))
        self.assertFalse(p.is_owner(actor))
        p.set_welcome("Hello {user}, enjoy {room}!")
        self.assertEqual(
            p.welcome_message("Fancy Display"), "Hello Fancy Display, enjoy 111-1!"
        )
        self.assertTrue(p.may_run("welcome", actor))

    def test_room_session_routes_mapped_owner_into_command_handler(self):
        from bot.room_session import RoomSession
        with patch("bot.room_session.CommandHandler") as handler_cls, patch(
            "bot.room_session.MusicController"
        ), patch("bot.room_session.AutoDJ"):
            handler = handler_cls.return_value
            handler.prefix = "!"
            handler.handle.return_value = "OK"
            session = RoomSession(
                "https://www.imvu.com/next/chat/room-111-1", radio_port=None
            )
            session.permissions.set_owner_from_dashboard("Sleepyhead222")
            response = session.process(
                "Sleepy", "!lock p", account_username="", user_id="imvu-id-12"
            )
            self.assertIn("!linkowner", response)
            claim = session.process("Sleepy", "!linkowner", user_id="imvu-id-12")
            self.assertIn("verification requested", claim)
            session.permissions.link_owner_from_dashboard(
                session.pending_owner_link["user_id"]
            )
            self.assertEqual(
                session.process("Sleepy", "!lock p", user_id="imvu-id-12"),
                "OK",
            )
            handler.handle.assert_called_with("!lock p", "Sleepyhead222")

    def test_member_request_owner_approval_and_admin_commands(self):
        from bot.commands import CommandHandler
        from bot.room_session import RoomSession
        p = RoomPermissions("111-1")
        p.set_owner_from_dashboard("Owner123")
        p.link_owner_from_dashboard("id-owner")
        with patch("bot.commands.MusicResolver"), patch(
            "bot.commands.get_shared_youtube_provider"
        ), patch("bot.commands.CollectibleDrops"):
            handler = CommandHandler(MagicMock(), MagicMock())
            handler.room_permissions = p
            handler.pending_admin_links = {}
            denied = handler.handle("!approvemod Alice", "SomeoneElse")
            self.assertIn("Only the registered room owner", denied)
            expired = handler.handle("!approvemod Alice", "Owner123")
            self.assertIn("must send !requestmod", expired)
            handler.pending_admin_links["alice"] = {
                "username": "Alice", "display": "Fancy Alice",
                "created_at": time.monotonic(),
            }
            accepted = handler.handle("!approvemod Alice", "Owner123")
            self.assertIn("now a room admin", accepted)
            self.assertTrue(p.is_mod("Alice"))
            self.assertFalse(p.is_owner("Alice"))
            self.assertEqual(p.resolve_account("", "id-admin"), "")
            handler.handle("!lock p", "Alice")
            self.assertFalse(p.may_run("p", "Random"))
            handler.handle("!unlock play", "Alice")
            self.assertTrue(p.may_run("p", "Random"))
            self.assertIn("updated", handler.handle(
                "!welcome Hello {user}!", "Alice"
            ))
            self.assertIn("Only the registered room owner", handler.handle(
                "!removemod Alice", "Alice"
            ))
            self.assertIn("Removed", handler.handle(
                "!removemod Alice", "Owner123"
            ))

    def test_requestmod_requires_verified_username_not_display_name(self):
        from bot.room_session import RoomSession
        with patch("bot.room_session.CommandHandler") as handler_cls, patch(
            "bot.room_session.MusicController"
        ), patch("bot.room_session.AutoDJ"):
            handler = handler_cls.return_value
            handler.prefix = "!"
            room = RoomSession("https://www.imvu.com/next/chat/room-111-1")
            room.permissions.set_owner_from_dashboard("Owner123")
            rejected = room.process("Decorated Nickname", "!requestmod")
            self.assertIn("username is not available", rejected)
            accepted = room.process(
                "Decorated Nickname", "!requestmod",
                account_username="Alice_42",
            )
            self.assertIn("@Alice_42 requested", accepted)
            self.assertEqual(
                room.pending_admin_links["alice_42"]["username"], "Alice_42"
            )
            self.assertNotIn("alice_42", room.permissions.mods)



if __name__ == "__main__":
    unittest.main()
