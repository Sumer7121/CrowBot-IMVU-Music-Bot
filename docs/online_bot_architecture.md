# Online CrowBot and Music Library Plan

## Goal

Keep CrowBot live without leaving the owner's everyday PC running. Host the web control panel separately, and keep the IMVU session, music stream, and bot worker on an always-on runtime.

## Deployment options

1. **Windows cloud VM — best fit for the current app.** Move CrowBot, Chrome/IMVU, its radio/tunnel process, and Ollama to a Windows VM. The web panel sends authenticated commands to a small bot agent on that VM. The owner's PC can be off.
2. **Dedicated mini PC — simplest local alternative.** Run the current app and Ollama on a low-power computer at home. It still stays on, but the main PC does not.
3. **Headless cloud rewrite — most engineering.** Split the site/API, queue, music worker, and room connection into services. Keep an always-on Windows/browser runtime if IMVU automation still needs a desktop session.

## Music request and storage order

1. Ollama interprets the request and extracts the song/artist search terms; it must not invent a playable URL.
2. Search a cloud object-storage library first. Store only tracks the owner has permission to use.
3. Keep searchable metadata in a database: normalized title, artist, duration, object key, checksum, and rights/source note.
4. If a library match is selected, fetch it from object storage into the bot VM's local cache and play it through CrowBot's existing radio pipeline. Use expiring signed access and keep the bucket private.
5. If no authorized file matches, use only a source that permits the intended playback. YouTube search may return metadata/links for users to open with YouTube's player; do not extract/download audio or bypass anti-bot blocks.

## Local AI

Ollama must run on the always-on VM for a fully online bot, or be replaced with a hosted AI endpoint. Never expose the VM's Ollama port directly to the public internet. The hosted website should communicate through an authenticated API or a bot-initiated outbound connection.

## Current project constraint

CrowBot is currently a desktop Python/Qt app with IMVU browser automation and a radio stream process. Hosting only the website or a short-lived serverless function will not keep the bot in the room.
