import json
import time
import urllib.parse
import urllib.request


class JamendoResolver:
    API_URL = "https://api.jamendo.com/v3.0/tracks/"

    def __init__(
        self,
        client_id="2c99fb24",
        timeout=10,
        max_attempts=3,
        retry_delay=0.75,
    ):
        self.client_id = (client_id or "").strip()
        self.timeout = timeout
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay = max(0.0, float(retry_delay))

    def search(self, query):
        query = (query or "").strip()

        if not query:
            raise ValueError("Song search cannot be empty.")

        if not self.client_id:
            raise RuntimeError("Jamendo Client ID is not configured.")

        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = self._search_once(query)

                if result is not None:
                    if attempt > 1:
                        print(
                            "JAMENDO: Search succeeded on "
                            f"attempt {attempt}/{self.max_attempts}: "
                            f"{query}"
                        )

                    return result

                print(
                    "JAMENDO: No results on "
                    f"attempt {attempt}/{self.max_attempts}: "
                    f"{query}"
                )

            except Exception as error:
                last_error = error

                print(
                    "JAMENDO: Search attempt "
                    f"{attempt}/{self.max_attempts} failed: "
                    f"{error}"
                )

            if attempt < self.max_attempts:
                time.sleep(self.retry_delay)

        if last_error is not None:
            raise RuntimeError(
                f"Jamendo search failed after "
                f"{self.max_attempts} attempts: "
                f"{last_error}"
            ) from last_error

        return None

    def _search_once(self, query):
        params = {
            "client_id": self.client_id,
            "format": "json",
            "limit": 1,
            "search": query,
            "audioformat": "mp32",
        }

        url = (
            self.API_URL
            + "?"
            + urllib.parse.urlencode(params)
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "IMVU-Music-Bot/1.0",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw_data = response.read()

        except Exception as error:
            raise RuntimeError(
                f"Jamendo request failed: {error}"
            ) from error

        try:
            data = json.loads(
                raw_data.decode("utf-8")
            )

        except Exception as error:
            raise RuntimeError(
                "Jamendo returned invalid JSON."
            ) from error

        headers = data.get("headers", {})

        if headers.get("status") != "success":
            raise RuntimeError(
                headers.get(
                    "error_message",
                    "Jamendo search failed.",
                )
            )

        results = data.get("results", [])

        if not results:
            return None

        for result in results:
            track = self._build_track(
                result,
                query,
            )

            if track is not None:
                return track

        return None

    def _build_track(
        self,
        result,
        query,
    ):
        if not isinstance(result, dict):
            return None

        audio_url = (
            result.get("audio")
            or ""
        ).strip()

        if not audio_url:
            return None

        title = (
            result.get("name")
            or "Unknown"
        ).strip()

        artist = (
            result.get("artist_name")
            or "Unknown"
        ).strip()

        display_title = (
            f"{artist} - {title}"
            if artist
            and artist != "Unknown"
            else title
        )

        return {
            "id": result.get("id", ""),
            "title": display_title,
            "track_title": title,
            "artist": artist,
            "duration": result.get(
                "duration",
                0,
            ),
            "url": audio_url,
            "source": "jamendo",
            "search_query": query,
        }
