import json

from config.runtime_paths import get_users_file


USERS_FILE = get_users_file()


class UserManager:

    VALID_ROLES = {
        "User",
        "DJ",
        "Moderator",
        "Owner",
    }

    def __init__(self):

        self.users = {}

        self.load_users()

    # ==========================
    # Load Users
    # ==========================

    def load_users(self):

        if not USERS_FILE.exists():
            return

        try:

            with open(
                USERS_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                saved_users = json.load(file)

            if isinstance(
                saved_users,
                dict
            ):

                self.users = saved_users

        except (
            json.JSONDecodeError,
            OSError
        ):

            self.users = {}

    # ==========================
    # Save Users
    # ==========================

    def save_users(self):

        USERS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            USERS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                self.users,
                file,
                indent=4
            )

    # ==========================
    # Add / Update User
    # ==========================

    def add_user(
        self,
        username,
        role="User"
    ):

        username = username.strip()

        if not username:
            return False

        if role not in self.VALID_ROLES:
            return False

        self.users[
            username.lower()
        ] = {
            "username": username,
            "role": role,
        }

        self.save_users()

        return True

    # ==========================
    # Remove User
    # ==========================

    def remove_user(
        self,
        username
    ):

        username = (
            username
            .strip()
            .lower()
        )

        if username in self.users:

            del self.users[username]

            self.save_users()

            return True

        return False

    # ==========================
    # Get User
    # ==========================

    def get_user(
        self,
        username
    ):

        username = (
            username
            .strip()
            .lower()
        )

        return self.users.get(
            username
        )

    # ==========================
    # Get Role
    # ==========================

    def get_role(
        self,
        username
    ):

        user = self.get_user(
            username
        )

        if user:

            return user["role"]

        return "User"

    # ==========================
    # Change Role
    # ==========================

    def set_role(
        self,
        username,
        role
    ):

        if role not in self.VALID_ROLES:
            return False

        username_key = (
            username
            .strip()
            .lower()
        )

        if username_key not in self.users:
            return False

        self.users[
            username_key
        ]["role"] = role

        self.save_users()

        return True

    # ==========================
    # Check Permission
    # ==========================

    def has_permission(
        self,
        username,
        required_role
    ):

        role_levels = {
            "User": 1,
            "DJ": 2,
            "Moderator": 3,
            "Owner": 4,
        }

        user_role = self.get_role(
            username
        )

        user_level = role_levels.get(
            user_role,
            1
        )

        required_level = role_levels.get(
            required_role,
            1
        )

        return (
            user_level >= required_level
        )

    # ==========================
    # Get All Users
    # ==========================

    def get_users(self):

        return list(
            self.users.values()
        )
