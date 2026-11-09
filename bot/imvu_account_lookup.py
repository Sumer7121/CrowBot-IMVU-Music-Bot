"""Optional direct IMVU public-profile lookup for stable chat CIDs.

The IMVU website currently exposes an undocumented GET /user/user-{cid}
endpoint. Treat failure as "unknown" and never authorize from a nickname.
Only use identity values explicitly tagged as profile/customer IDs.
"""
import json
import re
import time
from urllib.request import Request, urlopen

_CACHE = {}
_TTL_SECONDS = 1800


def lookup_username(customer_id):
    identity = str(customer_id or "").strip()
    if not re.fullmatch(r"[1-9][0-9]{0,14}", identity):
        return ""
    now = time.monotonic()
    existing = _CACHE.get(identity)
    if existing and now < existing[0]:
        return existing[1]
    url = "https://api.imvu.com/user/user-" + identity
    username = ""
    try:
        req = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": "CrowBot/1.0"})
        with urlopen(req, timeout=3) as response:
            payload = json.load(response)
        # API uses denormalized resource keys and may change without notice.
        nodes = payload.get("denormalized", {})
        node = nodes.get(url)
        if node is None:
            # Some versions append a query string to the denormalized key.
            node = next((v for k, v in nodes.items()
                         if k.split("?", 1)[0] == url), {})
        data = (node or {}).get("data", {})
        result = str(data.get("username") or "").strip().lstrip("@")
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", result):
            username = result
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        # Public IMVU REST response is not a guaranteed API contract.
        pass
    _CACHE[identity] = (now + (_TTL_SECONDS if username else 90), username)
    return username
