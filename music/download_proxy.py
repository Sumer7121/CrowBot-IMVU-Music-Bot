"""Optional downloader-only proxy configuration; never log provider credentials."""
import os
import shlex
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit


@contextmanager
def proxy_arguments():
    value = os.environ.get('CROWBOT_YTDLP_PROXY_URL', '')
    if not value:
        yield []
        return
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ('http', 'https', 'socks5', 'socks5h')
                 and parsed.hostname and parsed.port
                 and parsed.path in ('', '/') and not parsed.query
                 and not parsed.fragment
                 and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value))
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError('Invalid downloader proxy configuration. Check the private Render environment setting.')
    # Private directory and file disappear even after cancellation or timeout.
    with tempfile.TemporaryDirectory(prefix='crowbot-proxy-') as directory:
        path = Path(directory) / 'yt-dlp.conf'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as config:
            config.write('--proxy ' + shlex.quote(value) + '\n')
        yield ['--config-locations', str(path)]


def private_proxy_error(stderr):
    """Return categories only: upstream diagnostics can contain proxy passwords."""
    reason = str(stderr or '').lower()
    if '407' in reason or 'proxy authentication' in reason:
        return 'Proxy authentication failed (407). Check the configured proxy account.'
    if '403' in reason or 'forbidden' in reason:
        return 'Proxy or upstream access was refused (403).'
    if 'timed out' in reason or 'timeout' in reason:
        return 'The configured proxy request timed out.'
    if 'name resolution' in reason or 'getaddrinfo' in reason:
        return 'The proxy connection failed during DNS resolution.'
    if 'confirm' in reason and 'bot' in reason:
        return 'YouTube asks to confirm you are not a bot even through the configured proxy.'
    if '429' in reason or 'too many requests' in reason:
        return 'YouTube returned 429 through the configured proxy.'
    return 'Download request failed through the configured proxy. Check proxy access and availability.'
