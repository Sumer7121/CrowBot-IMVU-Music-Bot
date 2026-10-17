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
