import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(r"D:\IMVU-Music-Bot")
PYTHON_EXE = Path(sys.executable)


class YouTubeSearchTest:
    def __init__(self):
        self.ytdlp_command = [
            str(PYTHON_EXE),
            "-m",
            "yt_dlp",
        ]

    def search(self, query, limit=5):
        query = str(query or "").strip()

        if not query:
            return []

        search_value = f"ytsearch{limit}:{query}"

        command = self.ytdlp_command + [
            search_value,
            "--dump-json",
            "--skip-download",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ]

        print()
        print(f"YOUTUBE: Searching for: {query}")

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if process.returncode != 0:
            error = process.stderr.strip()

            raise RuntimeError(
                error or "yt-dlp search failed."
            )

        results = []

        for line in process.stdout.splitlines():
            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)

            except json.JSONDecodeError:
                continue

            video_id = data.get(
                "id",
                "",
            )

            webpage_url = data.get(
                "webpage_url"
            )

            if not webpage_url and video_id:
                webpage_url = (
                    "https://www.youtube.com/watch?v="
                    f"{video_id}"
                )

            result = {
                "id": video_id,

                "title": data.get(
                    "title",
                    "Unknown",
                ),

                "channel": (
                    data.get("channel")
                    or data.get("uploader")
                    or "Unknown"
                ),

                "channel_id": (
                    data.get("channel_id")
                    or data.get("uploader_id")
                    or ""
                ),

                "duration": data.get(
                    "duration",
                    0,
                ),

                "url": webpage_url,

                "provider": "youtube",

                "source": "youtube_search",
            }

            results.append(
                result
            )

        return results


def format_duration(seconds):
    try:
        seconds = int(
            seconds or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return "Unknown"

    minutes = seconds // 60
    remaining = seconds % 60

    return (
        f"{minutes}:"
        f"{remaining:02d}"
    )


def main():
    print()
    print(
        "========================================"
    )
    print(
        "IMVU Music Bot - YouTube Search Test"
    )
    print(
        "========================================"
    )
    print()
    print(
        "Search test only."
    )
    print(
        "No video/audio is downloaded by this file."
    )
    print()

    searcher = YouTubeSearchTest()

    while True:
        try:
            query = input(
                "Search (blank to stop): "
            ).strip()

        except (
            KeyboardInterrupt,
            EOFError,
        ):
            print()
            break

        if not query:
            break

        try:
            results = searcher.search(
                query,
                limit=5,
            )

        except Exception as error:
            print()
            print(
                f"Search failed: {error}"
            )
            print()
            continue

        if not results:
            print()
            print(
                "No YouTube results found."
            )
            print()
            continue

        print()
        print(
            "========================================"
        )
        print(
            "SEARCH RESULTS"
        )
        print(
            "========================================"
        )

        for index, result in enumerate(
            results,
            start=1,
        ):
            print()
            print(
                f"{index}. "
                f"{result['title']}"
            )

            print(
                "   Channel : "
                f"{result['channel']}"
            )

            print(
                "   Duration: "
                f"{format_duration(result['duration'])}"
            )

            print(
                "   URL     : "
                f"{result['url']}"
            )

        best = results[0]

        print()
        print(
            "========================================"
        )
        print(
            "BEST MATCH"
        )
        print(
            "========================================"
        )

        print(
            f"Title   : "
            f"{best['title']}"
        )

        print(
            f"Channel : "
            f"{best['channel']}"
        )

        print(
            f"Video ID: "
            f"{best['id']}"
        )

        print(
            f"URL     : "
            f"{best['url']}"
        )

        print(
            "========================================"
        )


if __name__ == "__main__":
    main()
