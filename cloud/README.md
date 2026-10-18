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
