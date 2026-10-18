import unittest
from unittest.mock import Mock, patch
from music.youtube_owned import YouTubeOwnedProvider
from music.download_proxy import private_proxy_error

class ResolutionTests(unittest.TestCase):
 def provider(self):
  p=YouTubeOwnedProvider.__new__(YouTubeOwnedProvider)
  p.library=Mock();p.library.find_query.return_value=None
  p._get_video_metadata=Mock(return_value={'duration':180,'id':'abcdefghijk'})
  p._prepare_track=Mock(return_value={'url':'local','title':'Test'})
  return p
 def test_direct_link_skips_title_search(self):
  p=self.provider();p.search_candidates=Mock(side_effect=AssertionError('must not search URL'))
  self.assertEqual(p.search('https://youtu.be/abcdefghijk')['title'],'Test')
  p.library.index_query.assert_called_once()
 def test_other_hosts_rejected(self):
  p=self.provider()
  for url in ['http://127.0.0.1/private','https://youtube.com.evil.example/watch?v=abcdefghijk']:
   with self.assertRaises(RuntimeError):p.search(url)
  p._get_video_metadata.assert_not_called()
 def test_search_error_is_preserved(self):
  p=self.provider();p.search_candidates=Mock(side_effect=RuntimeError('Proxy authentication failed (407).'))
  with self.assertRaisesRegex(RuntimeError,'407'):p.search('A song')
 def test_secret_safe_categories(self):
  for detail,expected in [('407 pass=secret','407'),('403 password=secret','403'),('timeout secret','timed out')]:
   result=private_proxy_error(detail);self.assertIn(expected,result);self.assertNotIn('secret',result)
