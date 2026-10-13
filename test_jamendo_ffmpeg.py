import json
import subprocess
import urllib.parse
import urllib.request


JAMENDO_CLIENT_ID = "2c99fb24"
JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks/"
FFMPEG_PATH = r"D:\IMVU-Music-Bot\bin\ffmpeg.exe"


def get_test_track():

    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": 1,
        "search": "rock",
        "audioformat": "mp32",
    }

    url = (
        JAMENDO_API_URL
        + "?"
        + urllib.parse.urlencode(params)
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "IMVU-Music-Bot/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:

        data = json.loads(
            response.read().decode("utf-8")
        )

    results = data.get("results", [])

    if not results:
        raise RuntimeError(
            "Jamendo returned no tracks."
        )

    track = results[0]

    return {
        "title": track.get("name", "Unknown"),
        "artist": track.get(
            "artist_name",
            "Unknown",
        ),
        "url": track.get("audio", ""),
    }


def main():

    print()
    print("========================================")
    print(" IMVU Music Bot - FFmpeg Jamendo Test")
    print("========================================")
    print()

    try:

        track = get_test_track()

        print(
            f"Track : {track['artist']} - "
            f"{track['title']}"
        )

        print()
        print("Testing Jamendo audio with FFmpeg...")
        print()

        command = [
            FFMPEG_PATH,

            "-hide_banner",

            "-loglevel",
            "warning",

            "-i",
            track["url"],

            "-t",
            "10",

            "-vn",

            "-f",
            "null",

            "-",
        ]

        result = subprocess.run(
            command,
            timeout=30,
        )

        print()

        if result.returncode == 0:

            print(
                "SUCCESS: FFmpeg can decode "
                "the Jamendo audio stream."
            )

        else:

            print(
                "FAILED: FFmpeg returned code "
                f"{result.returncode}."
            )

    except Exception as error:

        print()
        print("ERROR:")
        print(error)


if __name__ == "__main__":
    main()
