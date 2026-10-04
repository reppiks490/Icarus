"""Exercise tunnel launch boundaries without opening public tunnels."""
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from icarus_bridge.cli import start_tunnel


NO_WINDOW = 0x08000000
URL = 'https://synthetic-contract.trycloudflare.com'


class BridgeBackgroundTests(unittest.TestCase):
    def test_tunnel_flags_preserve_callbacks_and_platform_behavior(self):
        for platform in ['win32', 'linux']:
            for kind in ['ngrok', 'cloudflared']:
                with self.subTest(platform=platform, kind=kind):
                    received = []
                    ready = threading.Event()

                    def on_url(url):
                        received.append(url)
                        ready.set()

                    def launch(command, **kwargs):
                        self.assertEqual(command[0], 'synthetic-tunnel')
                        self.assertEqual(kwargs.get('creationflags', 0), NO_WINDOW if platform == 'win32' else 0)
                        if kind == 'ngrok':
                            self.assertEqual(command[1:], ['http', '8787', '--log=stdout', '--log-format=json'])
                            self.assertEqual(kwargs['stdout'], subprocess.DEVNULL)
                            self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
                        else:
                            self.assertEqual(command[1:], ['tunnel', '--url', 'http://localhost:8787', '--no-autoupdate'])
                            self.assertEqual(kwargs['stdout'], subprocess.PIPE)
                            self.assertEqual(kwargs['stderr'], subprocess.STDOUT)
                            self.assertTrue(kwargs['text'])
                        return SimpleNamespace(pid=404, stdout=io.StringIO(URL + '\n'))

                    with patch('sys.platform', platform), \
                         patch.object(subprocess, 'CREATE_NO_WINDOW', NO_WINDOW, create=True), \
                         patch('icarus_bridge.cli.shutil.which', return_value='synthetic-tunnel'), \
                         patch('icarus_bridge.cli.subprocess.Popen', side_effect=launch), \
                         patch('icarus_bridge.cli._ngrok_public_url', return_value=URL):
                        proc = start_tunnel(kind, 8787, on_url)
                        self.assertEqual(proc.pid, 404)
                        self.assertTrue(ready.wait(2), 'tunnel callback was lost')
                        self.assertEqual(received, [URL])

    @unittest.skipUnless(sys.platform == 'win32', 'requires actual Windows console API')
    def test_real_windows_tunnel_children_have_no_console(self):
        # Substitute only the executable so CI opens no network tunnel. The real
        # Popen receives exactly the launch options produced by start_tunnel.
        popen = subprocess.Popen
        for kind in ['ngrok', 'cloudflared']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                result = Path(temp) / 'console.txt'
                ready = threading.Event()
                script = ("import ctypes; from pathlib import Path; "
                          f"Path({str(result)!r}).write_text(str(ctypes.windll.kernel32.GetConsoleWindow())); "
                          f"print({URL!r}, flush=True)")

                def launch(command, **kwargs):
                    return popen([sys.executable, '-c', script], **kwargs)

                with patch('icarus_bridge.cli.shutil.which', return_value=sys.executable), \
                     patch('icarus_bridge.cli.subprocess.Popen', side_effect=launch), \
                     patch('icarus_bridge.cli._ngrok_public_url', return_value=URL):
                    proc = start_tunnel(kind, 8787, lambda url: ready.set() if url == URL else None)
                    try:
                        self.assertEqual(proc.wait(timeout=10), 0)
                        self.assertTrue(ready.wait(2), 'tunnel callback was lost')
                        self.assertEqual(result.read_text(), '0')
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.wait(timeout=5)
                        if proc.stdout is not None:
                            proc.stdout.close()


if __name__ == '__main__':
    unittest.main()
