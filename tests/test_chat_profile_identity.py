"""Execute the chat reader's JavaScript against representative DOM fields."""
import json
import shutil
import subprocess
import unittest
from unittest.mock import MagicMock

from bot.imvu_web_controller import IMVUWebController


@unittest.skipUnless(shutil.which("node"), "Node is needed to execute reader JavaScript")
class ChatProfileIdentityTests(unittest.TestCase):
    def read(self, row_attrs=None, nested_attrs=None):
        controller = IMVUWebController()
        controller.page = MagicMock()

        def evaluate(script):
            setup = """
                const attrs = INPUT;
                const node = a => ({
                    getAttribute: k => a[k] || null,
                    innerText: "",
                    querySelector: () => null,
                    querySelectorAll: () => []
                });
                const nested = node(attrs.nested);
                const profile = node({});
                profile.querySelectorAll = () => [nested];
                const row = node(attrs.row);
                row.classList = {contains: () => false};
                row.querySelector = s => s === ".chat-row-profile" ? profile :
                    s === ".display-name-text" ? {innerText: "Fancy Name",
                        getAttribute: () => null} : null;
                row.querySelectorAll = s => s === ".user-text" ?
                    [{innerText: "!linkowner"}] : [];
            """.replace("INPUT", json.dumps({
                "row": row_attrs or {}, "nested": nested_attrs or {}
            }))
            result = subprocess.run(
                ["node", "-e", setup + "console.log(JSON.stringify((" +
                 script + ")([row])));"],
                text=True, capture_output=True, check=True,
            )
            return json.loads(result.stdout)

        controller.page.locator.return_value.evaluate_all.side_effect = evaluate
        return controller.get_visible_chat_messages()[0]

    def test_explicit_customer_id_on_chat_row(self):
        self.assertEqual(self.read({"data-user-id": "123456"})["user_id"], "123456")

    def test_nested_profile_fields(self):
        event = self.read(nested_attrs={
            "data-customer-id": "123456", "data-account-username": "Owner123"
        })
        self.assertEqual(event["user_id"], "123456")
        self.assertEqual(event["account_username"], "Owner123")

    def test_message_id_is_never_customer_id(self):
        event = self.read({"data-id": "123456", "data-chat-entry": "654321"})
        self.assertEqual(event["user_id"], "")
        self.assertEqual(event["account_username"], "")
        self.assertEqual(event["chat_actor_id"], "legacy-chat:123456")

    def test_missing_metadata_does_not_invent_owner_identity(self):
        event = self.read()
        self.assertEqual(event["username"], "Fancy Name")
        self.assertEqual(event["user_id"], "")
        self.assertEqual(event["account_username"], "")
        self.assertEqual(event["chat_actor_id"], "")
