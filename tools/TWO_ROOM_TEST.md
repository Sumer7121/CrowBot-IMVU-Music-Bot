# CrowBot: two-room browser experiment

This is a **separate diagnostic program**, not full multi-room support yet.

1. Start the dedicated CrowBot Chrome with remote debugging on port 9222 and log into your bot account.
2. Open **two different** IMVU room URLs in two tabs. Join both rooms. Leave CHAT visible in both.
3. Close the normal CrowBot GUI while running this probe.
4. In PowerShell, in the repository root, run:

```powershell
python tools/two_room_probe.py --list
python tools/two_room_probe.py --rooms
```

The console should show READY once per room. Send `!ping` in each room from another avatar and watch the logs. To test outgoing room-specific replies, stop the probe and run:

```powershell
python tools/two_room_probe.py --rooms --reply-ping
```

**Success:** Both room URLs log their own messages, and each `!ping` receives a reply **in the same room only**. If IMVU allows multiple tabs but only one active scene session, one tab may fail; that is useful to learn before implementing cloud multi-room support.

No credentials are requested or stored. This probe does not enable games, AI, music, moderation, or reliable background listening when IMVU hides the CHAT interface. It uses the existing visible chat listener and does not promise to fix missed commands yet.

Note: Run from the project root so Python can import `bot`.
