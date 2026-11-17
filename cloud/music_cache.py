"""Durable per-tenant MP3 cache, served by the private website's R2 binding."""
import hashlib
import os
import urllib.request
import urllib.error
from urllib.parse import urlencode, quote, unquote
from music.track_library import is_valid_mp3

LIMIT=20*1024*1024

def configured():
    return bool(os.environ.get('CROWBOT_CACHE_URL') and os.environ.get('CROWBOT_SITES_BEARER'))

def request(tenant, query, method='GET', data=None, title=''):
    base=os.environ['CROWBOT_CACHE_URL']
    key=hashlib.sha256(query.strip().casefold().encode()).hexdigest()
    headers={'Authorization':'Bearer '+os.environ['CROWBOT_SERVICE_TOKEN'],
             'OAI-Sites-Authorization':'Bearer '+os.environ['CROWBOT_SITES_BEARER'],
             'Content-Type':'audio/mpeg','X-Track-Title':quote(title)}
    req=urllib.request.Request(base+'?'+urlencode({'tenant':tenant,'key':key}),data=data,headers=headers,method=method)
    return urllib.request.urlopen(req,timeout=40)

def restore(tenant,query,path):
    if not configured():return None
    try:
        with request(tenant,query) as response:
            data=response.read(LIMIT+1)
            if len(data)>LIMIT:raise RuntimeError('Saved song exceeds the cloud cache limit.')
            title=unquote(response.headers.get('X-Track-Title','Saved song'))
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        if not is_valid_mp3(path):
            path.unlink(missing_ok=True)
            raise RuntimeError('Saved cloud song failed audio validation.')
        return {'url':str(path),'title':title,'temporary_file':str(path),'cloud_cache_hit':True}
    except urllib.error.HTTPError as error:
        if error.code==404:return None
        raise RuntimeError('Cloud song storage is unavailable (HTTP '+str(error.code)+').') from None
    except (urllib.error.URLError,TimeoutError):
        raise RuntimeError('Cloud song storage could not be reached.') from None

def save(tenant,query,song):
    if not configured():return 'not_configured'
    from pathlib import Path
    path=Path(song['temporary_file'])
    if path.stat().st_size>LIMIT:return 'too_large'
    try:
        with request(tenant,query,'PUT',path.read_bytes(),song.get('title','Song')) as response:
            return 'saved' if response.status in (200,201) else 'failed'
    except urllib.error.HTTPError as error:
        return 'quota_or_busy' if error.code==409 else 'failed'
    except (urllib.error.URLError,TimeoutError):return 'failed'
