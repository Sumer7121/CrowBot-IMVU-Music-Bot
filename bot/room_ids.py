"""Validate and normalize IMVU room IDs without selecting arbitrary tabs."""
import re
from urllib.parse import urlparse

ROOM_ID_PATTERN = re.compile(r"^\\d+-\\d+$")
ROOM_URL_PREFIX = "https://www.imvu.com/next/chat/room-"


def normalize_room_id(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("Enter a room ID such as 391169385-9.")
    if "://" in text:
        parsed = urlparse(text)
        if parsed.scheme != "https" or parsed.netloc.casefold() not in {
            "imvu.com", "www.imvu.com"
        }:
            raise ValueError("Only https://www.imvu.com room links are supported.")
        path = parsed.path.strip("/")
        matched = re.fullmatch(r"next/chat/room-(\\d+-\\d+)", path)
        if not matched:
            raise ValueError("The IMVU link must be a specific /next/chat/room-ID/ URL.")
        text = matched.group(1)
    else:
        if text.startswith("room-"):
            text = text[5:]
        text = text.strip("/")
    if not ROOM_ID_PATTERN.fullmatch(text):
        raise ValueError("Room ID must look like 391169385-9.")
    return text


def make_room_url(room_id):
    return ROOM_URL_PREFIX + normalize_room_id(room_id) + "/"
