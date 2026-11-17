import os
import shlex
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from music.download_proxy import proxy_arguments
from music.youtube_owned import _run_cancellable


class DownloadProxyTests(unittest.TestCase):
    def test_disabled_preserves_command(self):
        with patch.dict(os.environ, {'CROWBOT_YTDLP_PROXY_URL': ''}):
            with proxy_arguments() as args:
                self.assertEqual(args, [])

    def test_private_file_and_cleanup(self):
        secret = 'http://user:pass%40word@proxy.example:8000'
        with patch.dict(os.environ, {'CROWBOT_YTDLP_PROXY_URL': secret}):
            with proxy_arguments() as args:
                path = Path(args[1])
                self.assertNotIn(secret, str(args))
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(shlex.split(path.read_text()), ['--proxy', secret])
            self.assertFalse(path.exists())

    def test_invalid_configuration_fails_closed(self):
        for value in ['http://host:bad', 'http://host', 'file:///secret', 'http://host:80\n--verbose']:
            with patch.dict(os.environ, {'CROWBOT_YTDLP_PROXY_URL': value}):
                with self.assertRaisesRegex(RuntimeError, 'Invalid downloader proxy'):
                    with proxy_arguments():
                        self.fail('invalid proxy accepted')

    def test_diagnostics_are_suppressed_and_file_removed(self):
        secret = 'http://user:secret@proxy.example:8000'
        paths = []
        def run(command, timeout, capture_output, cancel_check):
            self.assertTrue(capture_output)
            self.assertNotIn(secret, str(command))
            paths.append(Path(command[-1]))
            return subprocess.CompletedProcess(command, 1, '', secret)
        with patch.dict(os.environ, {'CROWBOT_YTDLP_PROXY_URL': secret}):
            with patch('music.youtube_owned._run_cancellable_process', side_effect=run):
                result = _run_cancellable(['yt-dlp', 'query'], 10)
        self.assertNotIn('secret', result.stderr)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_timeout_removes_secret_file(self):
        paths = []
        def run(command, *args, **kwargs):
            paths.append(Path(command[-1]))
            raise subprocess.TimeoutExpired(command, 1)
        with patch.dict(os.environ, {'CROWBOT_YTDLP_PROXY_URL': 'http://proxy.example:8000'}):
            with patch('music.youtube_owned._run_cancellable_process', side_effect=run):
                with self.assertRaises(subprocess.TimeoutExpired):
                    _run_cancellable(['yt-dlp'], 1)
        self.assertFalse(paths[0].exists())
