FROM node:24-bookworm-slim AS javascript
FROM python:3.12-slim-bookworm
COPY --from=javascript /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates chromium chromium-sandbox xvfb && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY cloud/requirements.txt cloud/requirements.txt
RUN pip install --no-cache-dir -r cloud/requirements.txt
# Ask for Player as well as GVS tokens so the guest-browser provider is tested
# before an upstream player request can fail. Never print raw tokens/cookies.
RUN printf '%s\n' '--js-runtimes node' '--verbose' \
    '--extractor-args "youtube:player_client=mweb;fetch_pot=always;pot_trace=true"' \
    '--extractor-args "youtubepot-wpc:browser_path=/usr/bin/chromium"' > /etc/yt-dlp.conf
RUN node --version && chromium --version && python -c "import yt_dlp, yt_dlp_ejs; from yt_dlp_plugins.extractor import getpot_wpc; print('WPC provider', getpot_wpc.__version__)"
COPY cloud cloud
COPY config config
COPY music music
COPY radio_server radio_server
RUN useradd --create-home --uid 10001 crowbot && chown -R crowbot:crowbot /app
USER crowbot
ENV PYTHONUNBUFFERED=1 DISPLAY=:99 CROWBOT_YTDLP_DIAGNOSTICS=1
CMD ["python", "-m", "cloud.start"]
