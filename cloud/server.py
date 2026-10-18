"""Single-process cloud radio API; authenticated control and opaque listener URLs.

Website identity is verified by the Sites server, which forwards a tenant ID
with a server-only bearer credential. Never expose that credential in a browser.
"""
import atexit
import hashlib
import json
import hmac
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.request
from urllib.parse import unquote
from pathlib import Path
from flask import Flask, Response, abort, jsonify, request
from config.ffmpeg import get_ffmpeg_path
from music.youtube_owned import get_shared_youtube_provider
from radio_server.server import RadioStreamServer
from cloud import music_cache

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
stations = {}
guard = threading.RLock()
MAX_STATIONS = 2
MAX_LISTENERS = 10
UPLOAD_ROOT = Path(os.environ.get('CROWBOT_UPLOAD_DIR', '/tmp/crowbot-uploads'))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
UPLOAD_LOCK = threading.Lock()


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
        self.progress = 'Starting cloud radio…'
        self.listeners = 0
        self.cache_status = 'not_requested'
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
                if query.startswith('upload:'):
                    file_id = query.removeprefix('upload:')
                    path = upload_path(self.tenant, file_id)
                    if not path.exists():
                        raise RuntimeError('Uploaded music copy is missing. Restart the queue to restore it from storage.')
                    title = json.loads(path.with_suffix('.json').read_text())['title']
                    song = {'url': str(path), 'title': title}
                    path.touch()
                elif query == '__crowbot_audio_check__':
                    path = provider.library.room_path(self.key, self.session_key) / 'tone.mp3'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run([get_ffmpeg_path(), '-nostdin', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=15', str(path)], check=True, timeout=30)
                    song = {'url': str(path), 'title': 'Audio connection test'}
                else:
                    deadline = time.monotonic() + 100
                    def cancelled():
                        return self.cancel.is_set() or time.monotonic() > deadline
                    self.progress = 'Checking saved cloud songs…'
                    cache_path = provider.library.room_path(self.key, self.session_key) / 'cloud-cache.mp3'
                    song = music_cache.restore(self.tenant, query, cache_path)
                    if song:
                        self.cache_status = 'hit'
                    else:
                        song = provider.search(query, requested_by='Cloud host', room_id=self.key, session_key=self.session_key, cancel_check=cancelled, progress_callback=lambda message: setattr(self, 'progress', message))
                        if song and not self.cancel.is_set():
                            self.progress = 'Saving downloaded song to cloud storage…'
                            self.cache_status = music_cache.save(self.tenant, query, song)
                if self.cancel.is_set(): break
                if not song or not song.get('url'):
                    raise RuntimeError('No playable audio was returned.')
                self.title = song.get('title', query)
                self.radio.set_source(song['url'], force_restart=True)
                self.status = 'buffering'
                self.progress = 'Waiting for decoded song audio…'
                began = time.monotonic()
                while not self.cancel.is_set() and not self.advance.wait(.5):
                    health = self.radio.get_health()
                    if health['has_song_bytes']:
                        self.status, self.progress = 'playing', 'Song audio is ready. Press play below to listen.'
                    elif time.monotonic() - began > 20:
                        raise RuntimeError('The audio encoder did not produce song audio.')
                    if self.radio.last_song_error:
                        raise RuntimeError('The audio encoder could not play this track.')
                    # Bound malformed/missing EOF and overlong tracks.
                    if time.monotonic() - began > 3600:
                        raise RuntimeError('Track exceeded the one-hour test limit.')
            if not self.cancel.is_set():
                self.status = 'finished'
        except Exception as error:
            if not self.cancel.is_set():
                self.status = 'error'
                self.error = 'Could not load this track from the cloud music provider. No song audio was played.'
                if any(word in str(error).lower() for word in ('requires verification', 'rate-limiting', 'proxy', '429', '403', '407')):
                    self.error = str(error)
                print('CLOUD RESOLVE FAILED: ' + type(error).__name__ + ': ' + str(error)[:500])
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
                'cache_status': self.cache_status, 'listeners': self.listeners, 'stream_path': '/listen/' + self.token + '.mp3',
                'storage': 'temporary', 'imvu_connected': False,
                'progress': self.progress, 'audio_ready': self.status == 'playing' and self.radio.get_health()['has_song_bytes']}


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


def upload_path(tenant, file_id):
    if not re.fullmatch(r'[a-f0-9-]{36}', file_id): abort(400)
    tenant_dir = UPLOAD_ROOT / hashlib.sha256(tenant.encode()).hexdigest()
    tenant_dir.mkdir(exist_ok=True)
    return tenant_dir / (file_id + '.mp3')


@app.route('/v1/uploads/<file_id>', methods=['GET', 'PUT'])
def upload(file_id):
    tenant = request.headers['X-Crowbot-Tenant']
    path = upload_path(tenant, file_id)
    if request.method == 'GET':
        return (jsonify(ready=True), 200) if path.exists() else (jsonify(error='Not cached'), 404)
    with UPLOAD_LOCK:
        if path.exists(): return jsonify(ready=True)
        # Evict only inactive playback copies. The durable original stays in R2.
        with guard:
            protected = {upload_path(s.tenant, q[7:]) for s in stations.values() if s.thread.is_alive() for q in s.tracks if q.startswith('upload:')}
        cached = sorted(UPLOAD_ROOT.glob('*/*.mp3'), key=lambda f: f.stat().st_mtime)
        total = sum(f.stat().st_size for f in cached)
        for old in cached:
            if total <= 230 * 1024 * 1024: break
            if old in protected: continue
            total -= old.stat().st_size
            old.unlink(missing_ok=True)
            old.with_suffix('.json').unlink(missing_ok=True)
        if total > 230 * 1024 * 1024: return jsonify(error='Playback cache is full. Stop an active room and retry.'), 507
        temp = path.with_suffix('.part')
        try:
            with temp.open('wb') as output:
                while chunk := request.stream.read(65536): output.write(chunk)
            if temp.stat().st_size < 2048: return jsonify(error='The audio file is empty or invalid.'), 400
            probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries', 'format=duration,format_name:stream=codec_type,codec_name', '-of', 'json', str(temp)], capture_output=True, text=True, timeout=15)
            if probe.returncode != 0: return jsonify(error='This MP3 could not be decoded.'), 400
            info = json.loads(probe.stdout)
            if info.get('format', {}).get('format_name') != 'mp3' or not any(s.get('codec_type')=='audio' and s.get('codec_name')=='mp3' for s in info.get('streams', [])):
                return jsonify(error='Only valid MP3 audio is supported.'), 400
            if not 0 < float(info['format'].get('duration', 0)) <= 3600:
                return jsonify(error='Tracks must be shorter than one hour.'), 400
            title = unquote(request.headers.get('X-Track-Title', 'Uploaded track'))[:180]
            path.with_suffix('.json').write_text(json.dumps({'title': title}))
            temp.replace(path)
            return jsonify(ready=True), 201
        except (subprocess.TimeoutExpired, ValueError, KeyError):
            return jsonify(error='The MP3 could not be verified.'), 400
        finally:
            temp.unlink(missing_ok=True)


@app.get('/listen/<token>.mp3')
def listen(token):
    with guard:
        station = next((s for s in stations.values() if hmac.compare_digest(s.token, token)), None)
        if not station or station.cancel.is_set() or not station.radio.is_running(): abort(404)
        if station.status != 'playing' or not station.radio.get_health()['has_song_bytes']:
            return jsonify(error='The song is still loading. No music audio is ready yet.'), 425
        if sum(s.listeners for s in stations.values()) >= MAX_LISTENERS: abort(429)
        station.listeners += 1
    def audio():
        try:
            with urllib.request.urlopen(station.radio.get_local_stream_url(), timeout=15) as source:
                while not station.cancel.is_set():
                    data = source.read(4096)
                    if not data: break
                    yield data
        except (TimeoutError, ConnectionError, OSError):
            return
        finally:
            with guard:
                station.listeners -= 1
    return Response(audio(), mimetype='audio/mpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


def shutdown():
    with guard:
        for station in stations.values(): station.stop()

atexit.register(shutdown)


@app.get('/v1/diagnostics/proxy')
def proxy_diagnostic():
    from music.download_proxy import proxy_arguments, private_proxy_error
    proxy = os.environ.get('CROWBOT_YTDLP_PROXY_URL', '')
    if not proxy:
        return jsonify(configured=False), 200
    try:
        with proxy_arguments():
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': proxy}))
            with opener.open('https://ipv4.webshare.io/', timeout=15) as response:
                return jsonify(configured=True, connected=response.status == 200, status=response.status)
    except Exception as error:
        # Exception text can include credentials: expose only fixed categories.
        return jsonify(configured=True, connected=False, status=getattr(error, 'code', None),
                       error_type=type(error).__name__, error=private_proxy_error(str(error))), 502
