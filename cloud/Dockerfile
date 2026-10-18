FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY cloud/requirements.txt cloud/requirements.txt
RUN pip install --no-cache-dir -r cloud/requirements.txt
COPY cloud cloud
COPY config config
COPY music music
COPY radio_server radio_server
RUN useradd --create-home --uid 10001 crowbot && chown -R crowbot:crowbot /app
USER crowbot
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 16 --timeout 120 --graceful-timeout 20 --access-logfile /dev/null cloud.server:app"]
