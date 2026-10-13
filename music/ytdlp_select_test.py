import json
import subprocess
import sys


PYTHON_EXE = sys.executable


class YTDLPSearchSelector:

    def _ytdlp(self):
        return [
            PYTHON_EXE,
            "-m",
            "yt_dlp",
        ]

    def search(
        self,
        query,
        limit=5,
    ):
        query = str(
            query or ""
        ).strip()

        if not query:
            return []

        print()
        print(
            "========================================"
        )
        print(
            f"YTDLP SEARCH: {query}"
        )
        print(
            "========================================"
        )

        command = (
            self._ytdlp()
            + [
                f"ytsearch{limit}:{query}",

                "--flat-playlist",

                "--dump-json",

                "--skip-download",

                "--no-warnings",

                "--socket-timeout",
                "15",
            ]
        )

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        )

        if process.returncode != 0:
            raise RuntimeError(
                process.stderr.strip()
                or
                "yt-dlp search failed."
            )

        results = []

        for line in (
            process.stdout.splitlines()
        ):

            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(
                    line
                )

            except json.JSONDecodeError:
                continue

            video_id = str(
                data.get(
                    "id",
                    "",
                )
            ).strip()

            if not video_id:
                continue

            title = str(
                data.get(
                    "title",
                    "Unknown",
                )
            ).strip()

            channel = str(
                data.get("channel")
                or data.get("uploader")
                or "Unknown"
            ).strip()

            duration = data.get(
                "duration",
                0,
            )

            try:
                duration = int(
                    duration or 0
                )

            except (
                TypeError,
                ValueError,
            ):
                duration = 0

            youtube_url = (
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

            results.append(
                {
                    "id": video_id,
                    "title": title,
                    "channel": channel,
                    "duration": duration,
                    "youtube_url": youtube_url,
                }
            )

        return results

    def select_best(
        self,
        query,
    ):
        results = self.search(
            query,
            limit=5,
        )

        if not results:
            return None

        print()
        print(
            "SEARCH RESULTS"
        )
        print(
            "----------------------------------------"
        )

        for index, result in enumerate(
            results,
            start=1,
        ):
            print(
                f"{index}. "
                f"{result['title']}"
            )

            print(
                "   Channel: "
                f"{result['channel']}"
            )

            print(
                "   URL: "
                f"{result['youtube_url']}"
            )

            print()

        selected = results[0]

        print(
            "========================================"
        )
        print(
            "SELECTED RESULT"
        )
        print(
            "========================================"
        )

        print(
            "Title   : "
            f"{selected['title']}"
        )

        print(
            "Channel : "
            f"{selected['channel']}"
        )

        print(
            "Video ID: "
            f"{selected['id']}"
        )

        print(
            "URL     : "
            f"{selected['youtube_url']}"
        )

        print(
            "========================================"
        )

        return selected


def main():

    selector = (
        YTDLPSearchSelector()
    )

    print()
    print(
        "IMVU Bot - yt-dlp "
        "Fast Search Selector"
    )
    print()

    while True:

        try:
            query = input(
                "Search "
                "(blank to stop): "
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

            selector.select_best(
                query
            )

        except Exception as error:

            print()
            print(
                f"ERROR: {error}"
            )
            print()


if __name__ == "__main__":
    main()
