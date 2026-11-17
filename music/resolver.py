import time

from music.youtube_owned import get_shared_youtube_provider


class MusicResolver:
    """
    CrowBot music resolver.

    yt-dlp / YouTube is the only active music provider.

    There is no Jamendo fallback and no direct raw HTTP
    streaming path. Search terms and supported media URLs
    are handled through YouTubeOwnedProvider / yt-dlp.
    """

    def __init__(
        self,
        timeout=10,
    ):
        self.timeout = timeout

        self.youtube = (
            get_shared_youtube_provider()
        )

    def resolve(
        self,
        query,
        requested_by=None,
        room_id="legacy",
        session_key="legacy",
        cancel_check=None,
        progress_callback=None,
    ):
        # Full searches can involve several YouTube metadata requests. Bound
        # the *whole* request, including download, to a reasonable deadline.
        deadline = time.monotonic() + 180

        def interrupted():
            return (bool(cancel_check and cancel_check())
                    or time.monotonic() >= deadline)

        query = str(
            query or ""
        ).strip()

        if not query:
            raise ValueError(
                "Song request cannot be empty."
            )

        print()
        print(
            f"RESOLVER: Request: {query}"
        )

        print(
            "RESOLVER: Searching with yt-dlp..."
        )

        try:
            track = self.youtube.search(
                query, requested_by=requested_by,
                room_id=room_id, session_key=session_key,
                cancel_check=interrupted,
                progress_callback=progress_callback,
            )

        except Exception as error:
            print("RESOLVER: yt-dlp or local MP3 preparation failed: " + str(error))
            raise RuntimeError("Song preparation failed: " + str(error)) from error

        if not track:
            print(
                "RESOLVER: No yt-dlp result."
            )
            return None

        track = dict(
            track
        )

        track.setdefault(
            "provider",
            "youtube",
        )

        track.setdefault(
            "source",
            "youtube",
        )

        track.setdefault(
            "search_query",
            query,
        )

        if requested_by:
            track[
                "requested_by"
            ] = requested_by

        print(
            "RESOLVER: Selected yt-dlp result: "
            f"{track.get('title', 'Unknown')}"
        )

        return track

    def search(
        self,
        query,
        requested_by=None,
    ):
        return self.resolve(
            query,
            requested_by=requested_by,
        )

    def close(self):
        """
        Release the yt-dlp provider and its temporary
        local HTTP server when CrowBot shuts down.
        """

        # Shared for the lifetime of the process; do not shut down the
        # temporary media server while another room still streams from it.
        return None
