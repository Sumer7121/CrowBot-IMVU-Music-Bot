import json
import urllib.parse
import urllib.request


JAMENDO_CLIENT_ID = "2c99fb24"
JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks/"


def search_song(query):
    query = (query or "").strip()

    if not query:
        raise ValueError("Song search cannot be empty.")

    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": 5,
        "search": query,
        "audioformat": "mp32",
    }

    url = (
        JAMENDO_API_URL
        + "?"
        + urllib.parse.urlencode(params)
    )

    print()
    print("Searching Jamendo...")
    print(f"Query: {query}")
    print()

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

    headers = data.get("headers", {})

    status = headers.get("status")

    if status != "success":
        error_message = headers.get(
            "error_message",
            "Jamendo search failed.",
        )

        raise RuntimeError(error_message)

    results = data.get("results", [])

    if not results:
        print("No tracks found.")
        return None

    print(f"Found {len(results)} result(s).")
    print("----------------------------------------")

    for index, track in enumerate(
        results,
        start=1,
    ):

        title = track.get(
            "name",
            "Unknown",
        )

        artist = track.get(
            "artist_name",
            "Unknown",
        )

        duration = track.get(
            "duration",
            0,
        )

        audio = track.get(
            "audio",
            "",
        )

        print(f"{index}. {artist} - {title}")
        print(f"   Duration: {duration} seconds")
        print(f"   Audio: {audio}")
        print()

    first = results[0]

    return {
        "id": first.get("id", ""),
        "title": first.get(
            "name",
            "Unknown",
        ),
        "artist": first.get(
            "artist_name",
            "Unknown",
        ),
        "duration": first.get(
            "duration",
            0,
        ),
        "url": first.get(
            "audio",
            "",
        ),
    }


def main():

    print()
    print("========================================")
    print(" IMVU Music Bot - Jamendo Search Test")
    print("========================================")
    print()

    query = input(
        "Enter song or artist: "
    ).strip()

    try:

        track = search_song(query)

        if not track:
            return

        print("========================================")
        print("SELECTED TRACK")
        print("========================================")

        print(f"Title : {track['title']}")
        print(f"Artist: {track['artist']}")
        print(f"Length: {track['duration']} seconds")
        print(f"Audio : {track['url']}")

        print()

        if track["url"]:
            print(
                "SUCCESS: Jamendo returned "
                "a playable audio URL."
            )
        else:
            print(
                "ERROR: Track did not contain "
                "an audio URL."
            )

    except Exception as error:

        print()
        print("ERROR:")
        print(error)


if __name__ == "__main__":
    main()
