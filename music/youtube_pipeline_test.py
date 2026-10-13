import json
import subprocess
import sys
import threading
from http.server import (
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
from urllib.parse import quote


PROJECT_ROOT = Path(r"D:\IMVU-Music-Bot")

TEMP_DIR = (
    PROJECT_ROOT
    / "data"
    / "youtube_temp"
)

FFMPEG_DIR = (
    PROJECT_ROOT
    / "bin"
)

PYTHON_EXE = Path(sys.executable)

HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8766


class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class MusicFileHandler(SimpleHTTPRequestHandler):

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            directory=str(TEMP_DIR),
            **kwargs,
        )

    def log_message(
        self,
        format,
        *args,
    ):
        print(
            "HTTP:",
            format % args,
        )


class YouTubePipelineTest:

    def __init__(self):
        TEMP_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.http_server = None
        self.http_thread = None

    # =========================================================
    # yt-dlp base command
    # =========================================================

    def _ytdlp(self):
        return [
            str(PYTHON_EXE),
            "-m",
            "yt_dlp",
        ]

    # =========================================================
    # Search YouTube
    # =========================================================

    def search(
        self,
        query,
    ):
        query = str(
            query or ""
        ).strip()

        if not query:
            raise ValueError(
                "Search cannot be empty."
            )

        print()
        print(
            f"YOUTUBE: Searching for: {query}"
        )

        command = self._ytdlp() + [
            f"ytsearch1:{query}",
            "--dump-single-json",
            "--skip-download",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ]

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if process.returncode != 0:
            raise RuntimeError(
                process.stderr.strip()
                or "YouTube search failed."
            )

        try:
            data = json.loads(
                process.stdout
            )

        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Could not parse YouTube search result."
            ) from error

        entries = data.get(
            "entries",
            [],
        )

        if not entries:
            raise RuntimeError(
                "No YouTube results found."
            )

        result = entries[0]

        video_id = str(
            result.get(
                "id",
                "",
            )
        ).strip()

        if not video_id:
            raise RuntimeError(
                "YouTube result had no video ID."
            )

        title = str(
            result.get(
                "title",
                "Unknown",
            )
        ).strip()

        channel = str(
            result.get("channel")
            or result.get("uploader")
            or "Unknown"
        ).strip()

        webpage_url = (
            result.get("webpage_url")
            or result.get("original_url")
        )

        if not webpage_url:
            webpage_url = (
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

        track = {
            "id": video_id,
            "title": title,
            "channel": channel,
            "youtube_url": webpage_url,
        }

        print()
        print(
            "========================================"
        )
        print(
            "YOUTUBE RESULT"
        )
        print(
            "========================================"
        )
        print(
            f"Title  : {title}"
        )
        print(
            f"Channel: {channel}"
        )
        print(
            f"ID     : {video_id}"
        )
        print(
            f"URL    : {webpage_url}"
        )
        print(
            "========================================"
        )

        return track

    # =========================================================
    # Download + convert to MP3
    # =========================================================

    def download_mp3(
        self,
        track,
    ):
        video_id = track["id"]

        youtube_url = track[
            "youtube_url"
        ]

        final_mp3 = (
            TEMP_DIR
            / f"{video_id}.mp3"
        )

        # Remove old copy of the same test video.
        if final_mp3.exists():
            try:
                final_mp3.unlink()
            except OSError:
                pass

        output_template = str(
            TEMP_DIR
            / f"{video_id}.%(ext)s"
        )

        print()
        print(
            "YTDLP: Downloading audio..."
        )

        command = self._ytdlp() + [
            youtube_url,

            "--extract-audio",

            "--audio-format",
            "mp3",

            "--audio-quality",
            "192K",

            "--ffmpeg-location",
            str(FFMPEG_DIR),

            "--output",
            output_template,

            "--no-playlist",
        ]

        process = subprocess.run(
            command,
            text=True,
        )

        if process.returncode != 0:
            raise RuntimeError(
                "yt-dlp download/conversion failed."
            )

        if not final_mp3.exists():
            candidates = list(
                TEMP_DIR.glob(
                    f"{video_id}*.mp3"
                )
            )

            if candidates:
                final_mp3 = candidates[0]

        if not final_mp3.exists():
            raise RuntimeError(
                "MP3 was not created."
            )

        print()
        print(
            "YTDLP: MP3 ready:"
        )
        print(
            final_mp3
        )

        return final_mp3

    # =========================================================
    # Temporary HTTP server
    # =========================================================

    def start_http_server(self):

        if self.http_server:
            return

        self.http_server = (
            ReusableHTTPServer(
                (
                    HTTP_HOST,
                    HTTP_PORT,
                ),
                MusicFileHandler,
            )
        )

        self.http_thread = threading.Thread(
            target=(
                self.http_server
                .serve_forever
            ),
            daemon=True,
        )

        self.http_thread.start()

        print()
        print(
            "TEMP SERVER: Running at:"
        )
        print(
            f"http://{HTTP_HOST}:{HTTP_PORT}/"
        )

    # =========================================================
    # Build playable localhost URL
    # =========================================================

    def build_stream_url(
        self,
        mp3_path,
    ):
        filename = quote(
            mp3_path.name
        )

        return (
            f"http://{HTTP_HOST}:"
            f"{HTTP_PORT}/"
            f"{filename}"
        )

    # =========================================================
    # Cleanup
    # =========================================================

    def cleanup_file(
        self,
        mp3_path,
    ):
        try:
            if (
                mp3_path
                and mp3_path.exists()
            ):
                mp3_path.unlink()

                print()
                print(
                    "CLEANUP: Deleted:"
                )
                print(
                    mp3_path
                )

        except OSError as error:
            print()
            print(
                "CLEANUP WARNING:"
            )
            print(
                error
            )

    def stop_server(self):

        if not self.http_server:
            return

        try:
            self.http_server.shutdown()
            self.http_server.server_close()

        finally:
            self.http_server = None

        print()
        print(
            "TEMP SERVER: Stopped."
        )


def main():

    pipeline = YouTubePipelineTest()

    mp3_path = None

    print()
    print(
        "========================================"
    )
    print(
        "IMVU YouTube Pipeline Test"
    )
    print(
        "========================================"
    )
    print()
    print(
        "Search -> URL -> yt-dlp -> MP3 -> HTTP"
    )
    print()

    try:

        query = input(
            "YouTube search: "
        ).strip()

        if not query:
            print(
                "No search entered."
            )
            return

        track = pipeline.search(
            query
        )

        mp3_path = (
            pipeline.download_mp3(
                track
            )
        )

        pipeline.start_http_server()

        stream_url = (
            pipeline.build_stream_url(
                mp3_path
            )
        )

        print()
        print(
            "========================================"
        )
        print(
            "READY FOR IMVU TEST"
        )
        print(
            "========================================"
        )
        print(
            f"Title : {track['title']}"
        )
        print(
            f"Source: {track['youtube_url']}"
        )
        print()
        print(
            "PLAYABLE LOCAL URL:"
        )
        print(
            stream_url
        )
        print()
        print(
            "Send this in IMVU:"
        )
        print()
        print(
            f"!play {stream_url}"
        )
        print()
        print(
            "Leave this window running "
            "while the song is playing."
        )
        print()
        print(
            "After the song finishes, "
            "press ENTER here."
        )

        input()

    except Exception as error:

        print()
        print(
            "PIPELINE ERROR:"
        )
        print(
            error
        )

    finally:

        pipeline.stop_server()

        if mp3_path:
            pipeline.cleanup_file(
                mp3_path
            )


if __name__ == "__main__":
    main()
