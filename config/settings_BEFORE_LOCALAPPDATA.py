import json
import sys
from pathlib import Path


def get_data_directory():
    """
    Returns the application's data directory.

    Development:
        D:\\IMVU-Music-Bot\\data

    Packaged application:
        <application folder>\\data
    """

    if getattr(sys, "frozen", False):
        base_directory = Path(
            sys.executable
        ).resolve().parent
    else:
        base_directory = Path(
            __file__
        ).resolve().parent.parent

    return base_directory / "data"


SETTINGS_FILE = (
    get_data_directory()
    / "settings.json"
)


DEFAULT_SETTINGS = {
    "username": "",
    "room_id": "",
    "bot_name": "",
    "prefix": "!",
    "music_mode": "Radio Stream",
    "imvu_client": "Auto Detect",
}


def load_settings():
    """
    Load bot settings.

    Also migrates the old 'room' setting
    to the newer 'room_id' setting.
    """

    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            saved = json.load(file)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)

        # Backward compatibility for older settings.
        if (
            not settings.get("room_id")
            and saved.get("room")
        ):
            settings["room_id"] = saved.get(
                "room",
                ""
            )

        settings.pop(
            "room",
            None
        )

        return settings

    except (
        json.JSONDecodeError,
        OSError
    ):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """
    Save complete bot settings.
    """

    SETTINGS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    complete_settings = (
        DEFAULT_SETTINGS.copy()
    )

    complete_settings.update(
        settings
    )

    complete_settings.pop(
        "room",
        None
    )

    with open(
        SETTINGS_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            complete_settings,
            file,
            indent=4
        )