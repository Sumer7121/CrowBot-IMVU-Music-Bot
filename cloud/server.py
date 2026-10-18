"""Single-process cloud radio API; authenticated control and opaque listener URLs.

Website identity is verified by the Sites server, which forwards a tenant ID
with a server-only bearer credential. Never expose that credential in a browser.
"""
import atexit
import hashlib
import hmac
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from flask import Flask, Response, abort, jsonify, request
from config.ffmpeg import get_ffmpeg_path
from music.youtube_owned import get_shared_youtube_provider
from radio_server.server import RadioStreamServer

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 65536
stations = {}
guard = threading.RLock()
MAX_STATIONS = 2
MAX_LISTENERS = 10


class Station:
    def __init__(self, tenant, room, tracks):
        self.tenant, self.room, self.tracks = tenant, room, tracks
        self.token = secrets.token_urlsafe(32)
        self.session_key = secrets.token_hex(12)
        self.key = hashlib.sha256((tenant + ':' + room).encode()).hexdigest()
        self.cancel = threading.Event()
        self.advance = threading.Event()
        self.lock = threading.RLock()
        self.status, self.title, self.error = 'starting', '', ''
        self.listeners = 0
        self.radio = RadioStreamServer(port=0)
        self.radio.track_finished_callback = lambda *_: self.advance.set()
        self.radio.start()
        self.radio.port = self.radio.server.server_address[1]
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        provider = get_shared_youtube_provider()
        try:
            for query in self.tracks:
                if self.cancel.is_set(): break
                self.advance.clear()
                self.status, self.title = 'resolving', query
                if query == '__crowbot_audio_check__':
                    path = provider.library.room_path(self.key, self.session_key) / 'tone.mp3'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run([get_ffmpeg_path(), '-nostdin', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=15', str(path)], check=True, timeout=30)
                    song = {'url': str(path), 'title': 'Audio connection test'}
                else:
                    song = provider.search(query, requested_by='Cloud host', room_id=self.key, session_key=self.session_key, cancel_check=self.cancel.is_set)
                if self.cancel.is_set(): break
                if not song or not song.get('url'):
                    raise RuntimeError('No playable audio was returned.')
                self.title = song.get('title', query)
                self.radio.set_source(song['url'], force_restart=True)
                self.status = 'playing'
                began = time.monotonic()
                while not self.cancel.is_set() and not self.advance.wait(.5):
                    if self.radio.last_song_error:
                        raise RuntimeError('The audio encoder could not play this track.')
                    # Bound malformed/missing EOF and overlong tracks.
                    if time.monotonic() - began > 3600:
                        raise RuntimeError('Track exceeded the one-hour test limit.')
            if not self.cancel.is_set():
                self.status = 'finished'
        except Exception:
            if not self.cancel.is_set():
                self.status = 'error'
                self.error = 'Could not load this track. The music provider may be unavailable from the cloud server. Try another track.'
        finally:
            self.radio.stop()
            provider.cleanup_room_files(self.key, self.session_key)

    def stop(self):
        self.cancel.set()
        self.advance.set()
        self.status = 'stopped'
        self.radio.stop()

    def snapshot(self):
        return {'status': self.status, 'title': self.title, 'error': self.error,
                'listeners': self.listeners, 'stream_path': '/listen/' + self.token + '.mp3',
                'storage': 'temporary', 'imvu_connected': False}


@app.before_request
def authorize():
    if not request.path.startswith('/v1/'):
        return
    secret = os.environ.get('CROWBOT_SERVICE_TOKEN', '')
    supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
    if len(secret) < 32 or not hmac.compare_digest(secret, supplied):
        abort(401)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', request.headers.get('X-Crowbot-Tenant', '')):
        abort(400)


@app.get('/')
@app.get('/healthz')
def health():
    ready = bool(get_ffmpeg_path()) and len(os.environ.get('CROWBOT_SERVICE_TOKEN', '')) >= 32
    return jsonify(service='CrowBot cloud audio', ready=ready, imvu_connected=False, storage='temporary'), 200 if ready else 503


@app.route('/v1/rooms/<room>', methods=['GET', 'POST', 'DELETE'])
def control(room):
    if not re.fullmatch(r'\d+-\d+', room): abort(400)
    tenant = request.headers['X-Crowbot-Tenant']
    key = (tenant, room)
    with guard:
        station = stations.get(key)
        if request.method == 'GET':
            return jsonify(station.snapshot() if station else {'status': 'offline', 'imvu_connected': False, 'storage': 'temporary'})
        if request.method == 'DELETE':
            if station:
                station.stop()
                del stations[key]
            return jsonify(status='stopped')
        body = request.get_json(silent=True)
        tracks = body.get('tracks') if isinstance(body, dict) else None
        if not isinstance(tracks, list) or not 1 <= len(tracks) <= 100 or any(not isinstance(q, str) or not q.strip() or len(q) > 300 for q in tracks):
            return jsonify(error='Add between 1 and 100 tracks to the queue.'), 400
        if station and station.thread.is_alive():
            return jsonify(error='Stop the current radio before starting a new queue.'), 409
        for k, old in list(stations.items()):
            if not old.thread.is_alive():
                del stations[k]
        if len(stations) >= MAX_STATIONS:
            return jsonify(error='This test server supports two active rooms. Stop another room first.'), 429
        station = Station(tenant, room, tracks)
        stations[key] = station
        return jsonify(station.snapshot()), 202


@app.get('/listen/<token>.mp3')
def listen(token):
    with guard:
        station = next((s for s in stations.values() if hmac.compare_digest(s.token, token)), None)
        if not station or station.cancel.is_set() or not station.radio.is_running(): abort(404)
        if sum(s.listeners for s in stations.values()) >= MAX_LISTENERS: abort(429)
        station.listeners += 1
    def audio():
        try:
            with urllib.request.urlopen(station.radio.get_local_stream_url(), timeout=15) as source:
                while not station.cancel.is_set():
                    data = source.read(4096)
                    if not data: break
                    yield data
        finally:
            with guard:
                station.listeners -= 1
    return Response(audio(), mimetype='audio/mpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


def shutdown():
    with guard:
        for station in stations.values(): station.stop()

atexit.register(shutdown)
