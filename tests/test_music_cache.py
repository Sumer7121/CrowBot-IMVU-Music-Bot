import io,os,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from cloud import music_cache
class Reply(io.BytesIO):
 headers={'X-Track-Title':'Saved%20track'}
 status=200
class CacheTests(unittest.TestCase):
 def test_restore_validates_and_reuses_cloud_bytes(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(music_cache,'configured',return_value=True),patch.object(music_cache,'request',return_value=Reply(b'mp3-bytes')),patch.object(music_cache,'is_valid_mp3',return_value=True):
   result=music_cache.restore('tenant','query',Path(folder)/'track.mp3')
   self.assertTrue(result['cloud_cache_hit']);self.assertEqual(result['title'],'Saved track')
 def test_cache_miss_is_distinct_from_service_failure(self):
  with patch.object(music_cache,'configured',return_value=True):
   with patch.object(music_cache,'request',side_effect=urllib.error.HTTPError('https://example',404,'missing',{},None)):
    self.assertIsNone(music_cache.restore('a','b',Path('unused')))
   with patch.object(music_cache,'request',side_effect=urllib.error.HTTPError('https://example',401,'secret',{},None)):
    with self.assertRaisesRegex(RuntimeError,'HTTP 401'):music_cache.restore('a','b',Path('unused'))
 def test_tenants_get_distinct_storage_requests(self):
  with patch.dict(os.environ,{'CROWBOT_CACHE_URL':'https://cache.example/api','CROWBOT_SERVICE_TOKEN':'test','CROWBOT_SITES_BEARER':'test'}),patch('urllib.request.urlopen',return_value=Reply()) as send:
   music_cache.request('host-a','Song');a=send.call_args.args[0].full_url
   music_cache.request('host-b','Song');b=send.call_args.args[0].full_url
   self.assertNotEqual(a,b);self.assertNotIn('test',a)
 def test_invalid_audio_removed(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(music_cache,'configured',return_value=True),patch.object(music_cache,'request',return_value=Reply(b'bad')),patch.object(music_cache,'is_valid_mp3',return_value=False):
   path=Path(folder)/'track.mp3'
   with self.assertRaises(RuntimeError):music_cache.restore('a','b',path)
   self.assertFalse(path.exists())
