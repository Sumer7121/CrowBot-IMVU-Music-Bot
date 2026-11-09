"""Real local HTTP + FFmpeg smoke test; no external services or IMVU."""
import shutil
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from radio_server.server import RadioStreamServer


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for local audio smoke test")
class LocalRadioSmokeTests(unittest.TestCase):
    def test_two_stations_stream_and_finish_independently(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "radio_server.server.get_ffmpeg_path", return_value=shutil.which("ffmpeg")
        ):
            source = Path(temp) / "one-second.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                wav.writeframes(b"\0\0" * 44100)
            first, second = RadioStreamServer(port=0), RadioStreamServer(port=0)
            responses = []
            finished = threading.Event()
            first.track_finished_callback = lambda url, generation: finished.set()
            try:
                first.start()
                second.start()
                ports = [r.server.server_address[1] for r in (first, second)]
                self.assertNotEqual(*ports)
                for port in ports:
                    response = urlopen(f"http://127.0.0.1:{port}/stream.mp3", timeout=8)
                    responses.append(response)
                    self.assertEqual(response.headers.get_content_type(), "audio/mpeg")
                    self.assertTrue(response.read(1024))
                first.set_source(str(source), force_restart=True)
                self.assertTrue(finished.wait(8), "Public FFmpeg EOF callback missing")
                self.assertEqual(first.get_source(), "")
                first.stop()
                self.assertTrue(second.is_running())
                self.assertTrue(responses[1].read(1024))
            finally:
                for response in responses:
                    response.close()
                first.stop()
                second.stop()
            self.assertFalse(first.is_running())
            self.assertFalse(second.is_running())
