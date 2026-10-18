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

## IMVU chat identity verification for room owners and admins

CrowBot stores and assigns **real IMVU usernames only** (e.g.
`Sleepyhead222`), never arbitrary decorated display names (e.g.
`Sleepy`). IMVU sometimes hides a user's account handle in the room's
chat HTML. A matching display name is not enough to authorize `!lock`,
`!welcome` or `!addmod`.

When `!whoami` says that the account username is hidden but a chat
account ID was detected:

1. In the desktop app, select the room and set the verified room owner
   username (`Sleepyhead222`, for example).
2. The actual owner types `!linkowner` inside that IMVU room.
3. The CrowBot app displays **Owner link pending** with the chat display
   name. The trusted app operator confirms the person's real identity in
   IMVU and clicks **APPROVE OWNER LINK**; the confirmation dialog also
   displays the IMVU chat account ID. Requests expire after five minutes.
4. The owner can use `!lock p`, `!welcome ...`, `!addmod username`,
   `!removemod username` etc. All these commands now share the same
   verified account authorization path.

When an appointed admin's IMVU username is also hidden, the room owner
first appoints their username using `!addmod Username`. Then the admin
types `!linkmod Username`, and the owner approves from chat with
`!approvemod Username` within five minutes. The bot internally pairs
the chat account ID with that **app-approved username**; it never adds a
display nickname to the admin roster.

These ID pairings survive reconnects. Reassigning the room owner revokes
the old owner ID, and removing an admin revokes its linked ID. If both
the IMVU account username **and** a stable chat account ID are absent,
CrowBot cannot securely grant privileged access based on chat markup alone.
In that case `!whoami` explains the blocker; new IMVU identity data or
an authenticated provider integration would be required.

## Room owner and moderation

The **room owner** is registered in the CrowBot desktop app using their
verified IMVU account username. If the IMVU chat hides the owner's username,
they can request `!linkowner` and the trusted operator can approve the
owner's chat account ID in the app. **Only owners have this linking flow.**

All other moderators use their **regular IMVU account username**:

```text
!requestmod             Member requests admin privileges
!approvemod username    Verified room owner approves that member's request
!removemod username     Verified room owner removes an admin
!mods                   Show room owner and all admins
```

The owner must approve a request within **15 minutes**. Admins cannot
approve requests or appoint other admins. Once approved, admins can run
`!lock`, `!unlock`, `!welcome`, music and drop administration without
any moderator-specific account-ID linking. Room settings persist separately.
`!h sys` contains only the main moderation commands, while advanced
owner linking and optional welcome previews remain available separately.

**Identity security:** IMVU display nicknames are *not* account usernames.
Requests use only a username from IMVU profile metadata or a direct public
IMVU account lookup from a profile CID. If neither source is available, the
request fails safely rather than granting permissions to a nickname.
The direct IMVU profile API is not a guaranteed public contract, so some
room layouts may not provide enough identity evidence.

Automatic drops continue independently of room activity. A new person's
welcome message appears when CrowBot first observes their chat message,
not necessarily immediately on a silent entry.

## Automatic cat/dog drops and Now Playing announcements

Each joined IMVU room now runs its **own drop timer**, independent of the
room's music queue and other connected rooms.

- The first automatic wild cat/dog appears approximately **1–1.5 minutes**
  after JOIN. Subsequent drops happen approximately every **6–10 minutes**.
- CrowBot announces a wild pet in that room's IMVU chat, with a **90-second**
  catch window. Type `!catch` there to collect the pet.
- Send `!drops` to see the room's active pet or the time until the next
  automatic drop. Use `!petdrop` to create a manual drop immediately for
  testing (once per room every three minutes).
- `!drop <column>` remains the Connect Four move command; it is *not* a
  collectible drop command.
- Drop timers stop when the room disconnects or the chat monitor ends.
  Drops are room-specific; a pet in Room A cannot be caught in Room B.
  Collected pets are saved in the shared user-collection database.

The room's **Now Playing** signal now also announces songs in that exact
IMVU room via the outgoing chat queue:

```text
🎧 DJ NOW PLAYING: Arijit Singh - Song Title | Artist: Arijit Singh
🎵 NOW PLAYING: Manually Requested Song
```

A single selected track is announced once per playback event, with no
cross-room fallback. These messages confirm CrowBot selected the track;
listen in IMVU and inspect the radio's FFmpeg logs to confirm audio.

**Testing:** connect two rooms, send `!petdrop` in each, and verify
`!catch` succeeds independently. Start `!dj Arijit Singh` in one room and
verify the next downloaded song is announced there, not in the other room.

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

## Troubleshooting Artist DJ / AutoDJ

After each room's radio has loaded in IMVU, select the room and click
**START ARTIST DJ**, or send `!dj Arijit Singh` in that room. The room's
logs should show:

1. `AutoDJ discovering next track`, then `Searching YouTube: ...`
2. `Checking candidate ...` (the first flat result may not have duration;
   CrowBot now checks the **full metadata** before rejecting it)
3. `Preparing song: ...`, then `ROOM MUSIC READY` and
   `AutoDJ selected: ...`
4. `Now playing: ...`; when the stream's FFmpeg process finishes naturally,
   the matching room advances its queue even if local Qt media playback
   doesn't report EndOfMedia

Run `!djstatus` to show the mode, selected artist, preparation stage, and last
failure. You can also read the same DJ activity/error next to the selected
room's song list. `!autoplay on` enables continuous discoveries without
selecting a specific artist. `!dj off` ends future automatic requests.

**What changed in the DJ fix:**

- YouTube flat search results with missing duration are no longer rejected
  before checking full video metadata. Full video duration must still be
  65–900 seconds.
- Search pages are scanned incrementally and a promising artist track is
  prepared immediately, instead of fetching 70+ search entries first.
- Background yt-dlp metadata calls can be cancelled, and full DJ search has
  a 120-second limit. Failures are reported and retried after 25 seconds.
- Qt signals from downloader threads safely update each room's song queue.
- Finished public radio tracks can advance the queue even if muted
  local playback doesn't send its completion event.
- Unused downloads from switching artists/languages are removed from the
  room-specific folder while reusable master MP3s are preserved.

Artist matching still excludes movie clips, advertisements, trailers and
unrelated artists; YouTube restrictions can prevent some songs from being
prepared. The UI indicates actual errors instead of silently waiting.

## Shared MP3 master cache and isolated room copies

Song downloads are stored under the current Windows user's local app data,
not inside your Git working tree:

```text
%LOCALAPPDATA%\\IMVU-Music-Bot\\youtube_temp\\
├── master\\
│   ├── song_index.json          # Request-to-video lookup
│   ├── VIDEO_ID.mp3             # Persistent, validated 192-kbps MP3
│   └── ...
├── incoming\\                 # Temporary incomplete downloads
└── rooms\\
    ├── 389249882-6\\
    │   └── SESSION_ID\\
    │       └── VIDEO_ID-random.mp3
    └── 379262025-12\\
        └── SESSION_ID\\
            └── VIDEO_ID-random.mp3
```

For `!play <song>` and AutoDJ:

1. Search the saved request index. If an indexed master MP3 exists and passes
   validation, skip the YouTube search and download. Otherwise search YouTube,
   inspect the result and check its video ID against the master cache.
2. On a cache miss, yt-dlp downloads/converts once to a unique **incoming**
   directory, validates MP3 content and atomically publishes the **master**.
   Simultaneous requests for the same video ID use one lock, so only one
   download occurs.
3. Copy the validated master into the **requesting room session's directory**.
   Room A and Room B receive **different playback files**, even for the same
   song. They still have independent radio ports and Cloudflare URLs.
4. The local YouTube HTTP server uses its own dynamically allocated port;
   each track URL contains its complete room/session file path. An HTTP
   **HEAD check** must return the staged MP3 before CrowBot announces it
   as ready. Missing files fail preparation instead of producing a silent
   radio with a 404.
5. When a song finishes, its room copy is removed after a short delay so
   FFmpeg can release any file handles. On room disconnect, stop that
   room's radio and music workers, then delete **only that session folder**.
   Other room folders and songs remain untouched.
6. Master MP3s are reusable between rooms and restarts. The cache is
   age/size bounded (up to 30 days / approximately 2 GiB); the least
   recently used masters are evicted first. Deleting a master **does not
   delete a room's already copied audio**.

Room dashboard logs show **MASTER CACHE HIT** or **MASTER CACHE SAVED**, plus
the room-specific copy used for playback. The server checks downloaded MP3s,
not merely the presence of a filename.

Note: the storage cache speeds up *previously downloaded songs*. A new song
still takes time to search, download and transcode, and the availability of
music from YouTube isn't guaranteed. An IMVU radio listener reconnect is
not automatically evidence of a failed MP3. Troubleshoot actual FFmpeg
`HTTP 404`, `without MP3 output` and `Audio stalled` status entries.

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
