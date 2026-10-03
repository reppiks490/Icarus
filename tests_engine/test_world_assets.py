"""Exercise shipped visual assets through the real server, without a running feed."""
import threading
import urllib.request
import urllib.error
from pathlib import Path

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


def test_world_assets_are_served_without_changing_portfolio(tmp_path):
    portfolio = Portfolio(Journal(':memory:'), str(tmp_path))
    server = serve(portfolio, 0, token='world-test', start=False)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    before = (portfolio.paused, list(portfolio.runners))
    try:
        for name in ('divine', 'void', 'astral'):
            with urllib.request.urlopen(f'{base}/worlds/{name}.webp') as response:
                assert response.headers.get_content_type() == 'image/webp'
                assert response.read() == (Path(__file__).parents[1] / 'icarus_engine' / 'worlds' / f'{name}.webp').read_bytes()
        with urllib.request.urlopen(f'{base}/world-motion.js') as response:
            assert response.headers.get_content_type() == 'text/javascript'
        for route in ('/worlds/missing.webp', '/worlds/../server.py'):
            try:
                urllib.request.urlopen(base + route)
            except urllib.error.HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError('Non-allowlisted asset was served')
        assert (portfolio.paused, list(portfolio.runners)) == before
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)
        portfolio.journal.con.close()
