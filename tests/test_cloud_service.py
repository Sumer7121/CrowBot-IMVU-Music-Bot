import os
import time
import unittest
import threading
import tempfile
import subprocess
import uuid
import array
from unittest.mock import patch
os.environ['CROWBOT_SERVICE_TOKEN'] = 'test-only-' * 8
from cloud.server import app, stations, shutdown

class CloudServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.auth = {'Authorization': 'Bearer ' + os.environ['CROWBOT_SERVICE_TOKEN'], 'X-Crowbot-Tenant': 'host-a'}
    def tearDown(self):
        shutdown()
        stations.clear()
    def test_auth_and_invalid_payload(self):
        self.assertEqual(self.client.post('/v1/rooms/123-4', json={'tracks':['x']}).status_code,401)
        self.assertEqual(self.client.post('/v1/rooms/123-4',headers=self.auth,json={'tracks':[]}).status_code,400)
        self.assertEqual(self.client.get('/listen/unknown.mp3').status_code,404)
        self.assertTrue(self.client.get('/healthz').json['ready'])
    def test_loading_has_no_playable_stream(self):
        entered = threading.Event()
        def delayed(*args, **kwargs):
            entered.set()
            while not kwargs['cancel_check'](): time.sleep(.01)
            return None
        with patch('music.youtube_owned.YouTubeOwnedProvider.search', side_effect=delayed):
            response = self.client.post('/v1/rooms/123-4', headers=self.auth, json={'tracks':['waiting']})
            self.assertTrue(entered.wait(2))
            self.assertFalse(self.client.get('/v1/rooms/123-4',headers=self.auth).json['audio_ready'])
            self.assertEqual(self.client.get(response.json['stream_path']).status_code,425)
            self.client.delete('/v1/rooms/123-4',headers=self.auth)

    def test_uploaded_mp3_isolated_and_audible(self):
        import cloud.server as service
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'UPLOAD_ROOT', __import__('pathlib').Path(folder)):
            raw = subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=10','-f','mp3','pipe:1'],capture_output=True,check=True).stdout
            file_id = str(uuid.uuid4())
            url = '/v1/uploads/' + file_id
            self.assertEqual(self.client.put(url,data=raw).status_code,401)
            self.assertEqual(self.client.put(url,headers=self.auth,data=b'bad audio').status_code,400)
            self.assertEqual(self.client.put(url,headers={**self.auth,'X-Track-Title':'Saved tone.mp3'},data=raw).status_code,201)
            other={**self.auth,'X-Crowbot-Tenant':'host-b'}
            self.assertEqual(self.client.get(url,headers=other).status_code,404)
            with patch('music.youtube_owned.YouTubeOwnedProvider.search',side_effect=AssertionError('Uploaded tracks must not use YouTube')):
                response=self.client.post('/v1/rooms/123-4',headers=self.auth,json={'tracks':['upload:'+file_id]})
                station=stations[('host-a','123-4')]
                deadline=time.time()+10
                while station.status!='playing':
                    if time.time()>deadline:self.fail('Uploaded track did not play')
                    time.sleep(.1)
                stream=self.client.get(response.json['stream_path'],buffered=False)
                iterator=iter(stream.response)
                mp3=b''.join(next(iterator) for _ in range(4))
                stream.close()
                pcm=subprocess.run(['ffmpeg','-v','error','-f','mp3','-i','pipe:0','-f','s16le','-ac','1','pipe:1'],input=mp3,capture_output=True,check=True).stdout
                samples=array.array('h',pcm)
                self.assertGreater(max(abs(v) for v in samples),100,'Decoded audio is silent')
                self.client.delete('/v1/rooms/123-4',headers=self.auth)

    def test_real_audio_and_tenant_isolation(self):
        response=self.client.post('/v1/rooms/123-4',headers=self.auth,json={'tracks':['__crowbot_audio_check__']})
        self.assertEqual(response.status_code,202)
        other={**self.auth,'X-Crowbot-Tenant':'host-b'}
        self.assertEqual(self.client.get('/v1/rooms/123-4',headers=other).json['status'],'offline')
        self.client.delete('/v1/rooms/123-4',headers=other)
        self.assertIn(('host-a','123-4'),stations)
        self.assertEqual(self.client.post('/v1/rooms/123-4',headers=self.auth,json={'tracks':['x']}).status_code,409)
        station=stations[('host-a','123-4')]
        deadline=time.time()+10
        while station.status in ('resolving','starting','buffering'):
            if time.time()>deadline: self.fail('Encoder startup timed out')
            time.sleep(.1)
        self.assertEqual(station.status,'playing')
        stream=self.client.get(response.json['stream_path'],buffered=False)
        self.assertEqual(stream.status_code,200)
        self.assertGreater(len(next(iter(stream.response))),1000)
        stream.close()
        self.assertEqual(self.client.delete('/v1/rooms/123-4',headers=self.auth).status_code,200)
        self.assertEqual(self.client.get(response.json['stream_path']).status_code,404)

if __name__=='__main__': unittest.main()
