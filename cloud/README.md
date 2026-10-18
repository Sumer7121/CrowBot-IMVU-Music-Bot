# CrowBot cloud audio test service

This server reuses CrowBot's actual YouTube resolver, master-song cache and FFmpeg radio encoder without loading the desktop Qt app. It supports two concurrent rooms and ten listeners total, with a one-hour track limit. Run exactly one Gunicorn process; station state is in memory.

`CROWBOT_SERVICE_TOKEN` must be a securely generated secret of at least 32 characters. The website backend authenticates users and sends this credential as a Bearer token plus a server-derived `X-Crowbot-Tenant`. Never send the service token to browsers. Listener URLs are opaque bearer links: anyone given a link can listen until the station stops. Do not log them.

- `GET /healthz`: dependency/configuration readiness (does not claim IMVU readiness).
- `GET /v1/rooms/{room-id}`: tenant-scoped station state.
- `POST /v1/rooms/{room-id}`: start with `{"tracks":["artist song"]}`.
- `DELETE /v1/rooms/{room-id}`: stop and revoke listener link.
- `GET /listen/{opaque-token}.mp3`: audio stream.

A reserved `__crowbot_audio_check__` query generates a short tone for verifying the encoder and HTTP stream without relying on an external music provider. Production source availability must be tested separately.

Deploy using `cloud/Dockerfile`, repo-root context, free Render web service for testing. Configure the secret through Render and the website's runtime secret store. No paid plan or disk is required for this test. Free Render instances sleep and lose local files; this is not always-on hosting. The cache reuses music during an instance's lifetime, but durable R2 storage is NOT configured. No cloud browser, IMVU login, automatic room joining, chat commands or moderation are enabled in this service yet. The existing desktop app remains the full bot.
