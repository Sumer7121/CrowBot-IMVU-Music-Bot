import os
from pathlib import Path


APP_NAME = "IMVU-Music-Bot"


def get_local_app_data():
    """
    Return the application's writable per-user data directory.

    Windows:
        %LOCALAPPDATA%\IMVU-Music-Bot

    Fallback:
        ~/.IMVU-Music-Bot
    """
    local_app_data = os.environ.get(
        "LOCALAPPDATA",
        ""
    ).strip()

    if local_app_data:
        root = Path(local_app_data) / APP_NAME
    else:
        root = Path.home() / f".{APP_NAME}"

    root.mkdir(
        parents=True,
        exist_ok=True
    )

    return root


def get_chrome_profile_dir():
    path = (
        get_local_app_data()
        / "chrome_bot_profile"
    )

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    return path


def get_youtube_temp_dir():
    path = (
        get_local_app_data()
        / "youtube_temp"
    )

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    return path
