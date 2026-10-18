FROM node:24-bookworm-slim AS javascript
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch 2.0.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil \
    && test "$(git -C /opt/bgutil rev-parse HEAD)" = "26475e9d3665b972c4aeb83b4dbaafcf64b88438"
WORKDIR /opt/bgutil/server
RUN npm ci --no-audit --no-fund && npx tsc && npm prune --omit=dev --no-audit --no-fund
FROM python:3.12-slim-bookworm
COPY --from=javascript /usr/local/bin/node /usr/local/bin/node
COPY --from=javascript /opt/bgutil/server/build /opt/bgutil/server/build
COPY --from=javascript /opt/bgutil/server/node_modules /opt/bgutil/server/node_modules
COPY --from=javascript /opt/bgutil/server/package.json /opt/bgutil/server/package.json
COPY --from=javascript /opt/bgutil/LICENSE /opt/bgutil/LICENSE
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY cloud/requirements.txt cloud/requirements.txt
RUN pip install --no-cache-dir -r cloud/requirements.txt
# Account-free mobile-web extraction with an on-demand PO token provider.
# Script mode exposes no extra network port and runs only during resolution.
RUN printf '%s\n' '--js-runtimes node' \
    '--extractor-args "youtube:player_client=mweb"' \
    '--extractor-args "youtubepot-bgutilscript:server_home=/opt/bgutil/server"' > /etc/yt-dlp.conf
RUN node /opt/bgutil/server/build/generate_once.js --version
RUN node --version && python -c "import yt_dlp, yt_dlp_ejs; print(yt_dlp.version.__version__)"
COPY cloud cloud
COPY config config
COPY music music
COPY radio_server radio_server
RUN useradd --create-home --uid 10001 crowbot && chown -R crowbot:crowbot /app
USER crowbot
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 16 --timeout 120 --graceful-timeout 20 --access-logfile /dev/null cloud.server:app"]
