import sys
from pathlib import Path


def get_application_directory():
    """
    Returns the correct application directory.

    Development:
        D:\\IMVU-Music-Bot

    Packaged EXE:
        Folder containing IMVU Music Bot.exe
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def get_ffmpeg_path():
    """
    Locate FFmpeg.

    Packaged layout:
        IMVU Music Bot/
            IMVU Music Bot.exe
            bin/
                ffmpeg.exe

    Development fallback:
        D:\\ffmpeg\\ffmpeg-9.0.2-essentials_build\\bin\\ffmpeg.exe
    """

    app_directory = get_application_directory()

    # Bundled / installed version
    bundled_path = (
        app_directory
        / "bin"
        / "ffmpeg.exe"
    )

    if bundled_path.exists():
        return str(bundled_path)

    # Development fallback
    development_path = Path(
        r"D:\ffmpeg\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"
    )

    if development_path.exists():
        return str(development_path)

    return None


def ffmpeg_available():
    return get_ffmpeg_path() is not None