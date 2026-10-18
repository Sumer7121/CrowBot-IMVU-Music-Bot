# CrowBot cloud audio test service

This server reuses CrowBot's actual YouTube resolver, master-song cache and FFmpeg radio encoder without loading the desktop Qt app. It supports two concurrent rooms and ten listeners total, with a one-hour track limit. Run exactly one Gunicorn process; station state is in memory.

`CROWBOT_SERVICE_TOKEN` must be a securely generated secret of at least 32 characters. The website backend authenticates users and sends this credential as a Bearer token plus a server-derived `X-Crowbot-Tenant`. Never send the service token to browsers. Listener URLs are opaque bearer links: anyone given a link can listen until the station stops. Do not log them.

- `GET /healthz`: dependency/configuration readiness (does not claim IMVU readiness).
- `GET /v1/rooms/{room-id}`: tenant-scoped station state.
- `POST /v1/rooms/{room-id}`: start with `{"tracks":["artist song"]}`.
- `DELETE /v1/rooms/{room-id}`: stop and revoke listener link.
- `GET /listen/{opaque-token}.mp3`: audio stream.

A reserved `__crowbot_audio_check__` query generates a short tone for verifying the encoder and HTTP stream without relying on an external music provider. Production source availability must be tested separately.

Deploy using `cloud/Dockerfile`, repo-root context, free Render web service for testing. Configure the secret through Render and the website's runtime secret store. No paid plan or disk is required for this test. Free Render instances sleep and lose local files; this is not always-on hosting. The cache reuses music during an instance's lifetime, while uploaded originals are retained by the website’s R2 storage. No cloud browser, IMVU login, automatic room joining, chat commands or moderation are enabled in this service yet. The existing desktop app remains the full bot.

## Uploaded MP3 playback

`PUT /v1/uploads/{uuid}` accepts authenticated MP3 bytes, verifies them with ffprobe and stores a tenant-isolated, evictable playback copy. `GET` on the same route reports cache presence. `X-Track-Title` is URI-encoded display text. Queue `upload:{uuid}` to play that local copy without calling YouTube. Durable originals live in the website's R2 storage; the website authorizes ownership and restores missing playback copies before starting. Maximum upload 20 MiB, maximum duration one hour, playback cache approximately 250 MiB. These limits do not establish a provider billing guarantee.

### Account-free YouTube compatibility trial
The cloud image includes bgutil-ytdlp-pot-provider 2.0.2 and its matching
Node script (upstream commit 26475e9d3665b972c4aeb83b4dbaafcf64b88438).
yt-dlp uses the mweb client and generates PO tokens on demand, with no
account cookies or additional public service. Tokens/cache are temporary.
This is a compatibility attempt, not a guarantee of access: upstream can
still require verification or reject the server. Desktop configuration is unchanged.

### Browser guest-token trial outcome (2026-10-18)
Commit 8eb8212 tested yt-dlp-getpot-wpc 1.1.2 with Chromium, Xvfb,
the sandbox helper, explicit player-token requests, and redacted diagnostics.
On the existing free Render instance the provider loaded and requested a
browser launch, but Chromium startup failed before any token was minted.
A separate blank-page startup check timed out. The real song request still
returned YouTube verification. This does not establish whether valid browser
tokens would work. The experimental browser runtime was removed from the
active image to avoid overhead; the implementation remains in Git history.
No account cookies or paid infrastructure were used.

### Optional downloader proxy

Set `CROWBOT_YTDLP_PROXY_URL` privately in the Render service's Environment page,
then redeploy. Use the full provider URL (HTTP, HTTPS, SOCKS5 or SOCKS5H), including
an explicit port and percent-encoded credentials where needed. Do not commit the
value, paste it into chat, or put it in frontend settings. Leave it unset for
existing direct requests. Invalid settings fail closed.

Search, metadata and download subprocesses all receive the same setting through
a temporary private configuration file, removed after completion or cancellation.
Raw downloader errors are suppressed when proxying. Radio and upload traffic do
not use this setting. Choose a stable/sticky session at the provider so requests
use the same outgoing IP; this code does not rotate IPs. No provider is included,
and proxy support does not guarantee YouTube access. Test a real song after
configuring it. The current website radio route accepts saved MP3 uploads only;
this backend setting alone does not reconnect its separate YouTube player.
