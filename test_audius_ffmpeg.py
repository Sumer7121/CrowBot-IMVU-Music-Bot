import subprocess
from pathlib import Path

from music.audius import AudiusResolver


PROJECT_ROOT = Path(__file__).resolve().parent
FFMPEG = PROJECT_ROOT / "bin" / "ffmpeg.exe"
OUTPUT = PROJECT_ROOT / "audius_test.mp3"


def main():
    print()
    print("========================================")
    print("Audius -> FFmpeg Compatibility Test")
    print("========================================")
    print()

    if not FFMPEG.exists():
        raise RuntimeError(
            f"FFmpeg was not found: {FFMPEG}"
        )

    resolver = AudiusResolver()

    query = input(
        "Search Audius: "
    ).strip()

    if not query:
        print("Search cancelled.")
        return

    track = resolver.search(query)

    if not track:
        print("No playable Audius track found.")
        return

    print()
    print(f"Selected: {track['title']}")
    print(f"Stream:   {track['url']}")
    print()

    if OUTPUT.exists():
        OUTPUT.unlink()

    headers = resolver.get_stream_headers()

    ffmpeg_headers = ""

    for name, value in headers.items():
        ffmpeg_headers += (
            f"{name}: {value}\r\n"
        )

    command = [
        str(FFMPEG),

        "-hide_banner",
        "-loglevel",
        "warning",

        "-headers",
        ffmpeg_headers,

        "-i",
        track["url"],

        "-t",
        "20",

        "-vn",

        "-codec:a",
        "libmp3lame",

        "-b:a",
        "128k",

        "-ar",
        "44100",

        "-ac",
        "2",

        "-y",

        str(OUTPUT),
    ]

    print(
        "Starting FFmpeg..."
    )

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    print()
    print(
        f"FFmpeg exit code: {result.returncode}"
    )

    if result.stderr:
        print()
        print("FFmpeg output:")
        print(result.stderr)

    if (
        result.returncode == 0
        and OUTPUT.exists()
        and OUTPUT.stat().st_size > 0
    ):
        print()
        print("SUCCESS")
        print(
            "Audius audio was successfully "
            "processed by FFmpeg."
        )
        print(
            f"Output: {OUTPUT}"
        )
        print(
            f"Size:   {OUTPUT.stat().st_size} bytes"
        )

    else:
        print()
        print("FAILED")
        print(
            "Audius audio could not be "
            "processed by FFmpeg."
        )


if __name__ == "__main__":
    main()
