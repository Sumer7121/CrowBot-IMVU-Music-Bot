# CrowBot review — 2026-10-18

Reviewed branch: crowbot-ai-v2, starting at a50a4b7.

## Checks completed

- Python compilation passed for app, bot, config, database, music, radio_server and tests.
- Full automated suite: 144 tests passed in the review environment.
- Desktop startup and shutdown passed with Qt offscreen and isolated settings.
  No live IMVU rooms were connected during that check.
- Two actual local HTTP radio stations streamed MP3 bytes using FFmpeg.
  A generated one-second audio file reached the public EOF callback.
  Stopping one station left the other station streaming.
- Existing tests cover room isolation/reconnects, owner linking, moderator
  approval/removal, artist/language DJ selection, cache isolation, games and pets.
- Regression coverage was added for the changes below.

## Fixes in this review

1. Equivalent command aliases now share command locks.
2. Radio reload updates the generation used to recognize public track completion.
3. Public radio EOF drives queue advancement while streaming, preventing a
   second local Qt EOF from skipping another song.
4. Chat and dashboard stop cancel pending manual downloads. Clear cancels
   unfinished requests too. New requests can still start afterwards.
5. Late canceled results are discarded and their room files released.
6. YouTube URLs use the downloader; direct audio URLs retain direct playback.
7. YouTube search runs in the background request queue instead of blocking
   the application and other rooms.
8. Prefix settings apply immediately to connected room handlers.
9. Whoami no longer reports ownership just because a display name matches
   the configured owner's username.
10. Radio FFmpeg discovery supports an executable installed on PATH, while
    retaining the bundled and existing Windows development locations.

## Live checks still required

This environment has no access to the user's local Chrome/IMVU session.
The checks above do not prove live owner identity extraction, IMVU JOIN/LOAD
selectors, Cloudflare tunnel availability, current YouTube extraction, or
audio delivery to actual IMVU listeners.

In each connected room:

1. The configured owner sends !linkowner, the operator approves in the app,
   and the owner sends !whoami followed by a restricted command.
2. A member sends !requestmod; the owner approves the exact display name.
   Confirm that the mod can lock/unlock commands and cannot appoint mods.
3. Request a song by name and a YouTube URL. Stop while another request
   is preparing; playback must remain stopped.
4. Reload radio during a song and confirm that the next song starts at EOF.
5. Connect two rooms with different queues. Disconnect one and confirm the
   other room's audio and commands continue.

The legacy owner link uses an app-approved opaque chat identifier. Its
stability between real IMVU messages remains a live-session check.
