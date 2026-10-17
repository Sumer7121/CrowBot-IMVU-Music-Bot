# CrowBot multi-room setup (room-first design)

CrowBot has **no primary room** in this interface. One Windows application
controls as many independently connected IMVU room tabs as your PC can handle.
Every room has a separate `RoomSession`, `MusicController`, `MusicQueue`,
`CommandHandler`, local `RadioStreamServer` port, and
`CloudflareTunnel` URL.

## Start

1. Log in to the **dedicated bot Chrome profile** as your bot account. Chrome
   must support CDP on `127.0.0.1:9222` (CrowBot starts this profile if needed).
2. Start the Windows app: `python main.py`.
3. Enter a room ID, e.g. `391169385-9`, and click **ADD ROOM**.
4. In that room's table row, click **CONNECT**.
5. Watch its status: Opening tab → Joining room → Starting private station →
   Loading IMVU radio → Connected/Ready.
6. Add another room ID, e.g. `379262025-12`. Click **CONNECT** on *its own row*.
7. Choose either room to view **its** public HTTPS radio URL, song queue and
   filtered logs; request a song with **PLAY IN SELECTED ROOM**.
8. Use the table row's **DISCONNECT** to stop only that room's chat listener,
   FFmpeg station and Cloudflare tunnel. Other connected rooms keep running.

Your saved room IDs appear when CrowBot is restarted, **offline until you click
CONNECT**. Remove one using **REMOVE SELECTED**. All rooms use one application,
one dedicated Chrome profile, and their own room tabs.

## Artist DJ, autoplay and music language

Select a connected room in the table. All these actions affect **only that
room**; other rooms keep their songs, queues and DJ settings.

- In **DJ ARTIST**, enter e.g. `Arijit Singh` and choose **START ARTIST DJ**.
  CrowBot discovers additional songs by that artist from available YouTube
  search results, downloads/prepares the next supported track in the
  background and keeps one song ready ahead of time.
- Choose **AUTOPLAY ON** for continuous YouTube song discovery (even with
  nothing manually added to the queue). A currently playing song becomes a
  recommendation seed when possible. **AUTOPLAY OFF** stops future DJ
  discoveries; your current song continues.
- Select a **DJ MUSIC LANGUAGE** and choose **SET LANGUAGE**. Hindi, Telugu,
  Tamil, Malayalam, English, Punjabi, Spanish, and several other languages
  are supported. The selection guides **upcoming automatic songs**.
- **Match Current** attempts to infer the next song's language from the
  current song's YouTube language metadata, title or distinctive script.
  When no reliable language can be inferred, discovery falls back to a
  broader search. Music tagging is imperfect, so choose a language
  explicitly if you require a stricter playlist.
- **DJ OFF** disables artist radio and autoplay for the selected room.
- Requested songs take priority over automatic selections; stale
  AutoDJ-prefetched tracks are removed when changing modes or language.
- **STOP MUSIC** stops the current song and disables autoplay in that room.

IMVU chat supports the same controls:

```
!dj Arijit Singh
!dj off
!autoplay on
!autoplay off
!language Hindi
!language Telugu
!language match
!language off
!djstatus
```

**Limits:** "Artist DJ" searches the YouTube catalog; it cannot guarantee an
artist's entire discography. Songs unavailable to the resolver, deleted,
restricted or mismatched to the requested artist/language may be skipped.
AutoDJ does not bypass YouTube availability or access restrictions. YouTube
music-language labels are not guaranteed to reflect the actual sung language.
The bot and its local media server must remain running for autoplay to work.

## Troubleshooting a room with no audio

- The public URL is unique per connected room; never paste the same URL into
  two rooms.
- Confirm the bot is allowed to manage **Radio Streaming** in every room.
- `Connected` means the IMVU radio LOAD was acknowledged, **not proof that a
  listener heard music**.
- Select the room and check **ROOM LOGS** for Cloudflare errors, FFmpeg errors,
  `First song MP3 bytes received`, and `Connected radio listeners`.
- `Playing · no listeners` means FFmpeg has audio but no active HTTP listener;
  inspect IMVU Radio in *that room*.
- `Audio stalled` means the song source produced no recent MP3 bytes.
- Use **RELOAD RADIO** on that room if the tunnel exists but radio is silent.
- Ports are allocated independently starting at 8765. Distinct ports
  correspond to distinct Cloudflare quick tunnels and MP3 streams.
- You can test isolation with two different songs, one per room; stopping or
  skipping one room must leave the other untouched.

This implementation requires the Windows app and its Chrome/FFmpeg/tunnel
processes to remain running. It is not unattended cloud hosting.

## Developer regression tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

If tests fail, do not infer live dual-room operation from code alone. Save
the trace and the corresponding room's logs for diagnosis.
