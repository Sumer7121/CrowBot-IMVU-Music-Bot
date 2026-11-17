"""Rank YouTube music candidates before downloading any media.

Conservative filtering: unknown duration/title may be inspected using full
metadata, but cannot be downloaded unless duration and relevance pass.
"""
import re
import unicodedata

BAD_PHRASES = (
    "full movie", "full film", "movie trailer", "official trailer",
    "short film", "feature film", "movie recap", "movie explained",
    "full episode", "full series", "documentary", "behind the scenes",
    "reaction video", "reaction to", "interview", "podcast",
    "walkthrough", "gameplay", "livestream", "live stream",
    "audiobook", "movie scene", "film scene", "teaser trailer",
)
GOOD_PHRASES = ("official audio", "official music video", "official video",
                "lyric video", "lyrics", "audio", "visualizer", "topic")


def normalized(text):
    text = unicodedata.normalize("NFKD", str(text or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", text)


def query_parts(query):
    text = str(query or "").strip()
    # "goddess by xana" -> requested title "goddess", artist "xana".
    parts = re.split(r"\s+by\s+", text, maxsplit=1, flags=re.I)
    if len(parts) == 2 and all(part.strip() for part in parts):
        return parts[0].strip(), parts[1].strip()
    return text, ""


def candidate_score(candidate, query):
    """Return a numeric rank or None when demonstrably not a song."""
    title = str(candidate.get("title") or "")
    channel = str(candidate.get("channel") or "")
    duration = candidate.get("duration")
    try:
        duration = int(duration or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration > 900:  # reject films, hour-long mixes, and long videos
        return None
    title_words = set(normalized(title))
    title_text = " ".join(normalized(title))
    if any(phrase in title_text for phrase in BAD_PHRASES):
        return None

    requested_title, artist = query_parts(query)
    song_tokens = set(normalized(requested_title))
    artist_tokens = set(normalized(artist))
    if not song_tokens:
        return None
    # A result must include every nontrivial word of the requested title.
    significant = {t for t in song_tokens if len(t) > 2} or song_tokens
    if not significant.issubset(title_words):
        return None

    channel_words = set(normalized(channel))
    score = 60.0
    if artist_tokens:
        matching = artist_tokens & (title_words | channel_words)
        if not matching:
            return None
        score += 30 * len(matching) / len(artist_tokens)
        if artist_tokens.issubset(channel_words):
            score += 15
    if duration:
        if duration < 45:
            return None
        if 90 <= duration <= 420:
            score += 15
        elif duration <= 600:
            score += 7
    if any(phrase in title_text for phrase in GOOD_PHRASES):
        score += 8
    if "topic" in channel_words:
        score += 10
    if "cover" in title_words or "karaoke" in title_words:
        score -= 12
    if "sped" in title_words or "slowed" in title_words or "remix" in title_words:
        score -= 6
    return score


def ranked_candidates(candidates, query):
    scored = []
    for item in candidates:
        score = candidate_score(item, query)
        if score is not None:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]
