"""Exercise the decorative asset boundary through the real feed-free server."""
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


ROOT = Path(__file__).parents[1]


@pytest.fixture
def presentation_server(tmp_path):
    portfolio = Portfolio(Journal(':memory:'), str(tmp_path))
    server = serve(portfolio, 0, token='decorative-test', start=False)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    before = (portfolio.paused, list(portfolio.runners))
    try:
        yield f'http://127.0.0.1:{server.server_address[1]}', portfolio, before
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)
        portfolio.journal.con.close()


@pytest.mark.parametrize('name,mime', [
    ('reference-choreography.js', 'text/javascript'),
    ('reference-choreography.css', 'text/css'),
])
def test_choreography_assets_are_read_only(presentation_server, name, mime):
    base, portfolio, before = presentation_server
    try:
        response = urllib.request.urlopen(f'{base}/{name}')
    except urllib.error.HTTPError as error:
        assert error.code == 200, f'{name} must be served; got HTTP {error.code}'
        return
    with response:
        assert response.headers.get_content_type() == mime
        assert response.read() == (ROOT / 'icarus_engine' / name).read_bytes()
    assert (portfolio.paused, list(portfolio.runners)) == before


@pytest.mark.parametrize('path', [
    '/reference-choreography.js/extra',
    '/reference-choreography.css/../server.py',
    '/reference-choreography.js%2f..%2fserver.py',
])
def test_choreography_asset_allowlist_rejects_other_paths(presentation_server, path):
    base, portfolio, before = presentation_server
    with pytest.raises(urllib.error.HTTPError) as failure:
        urllib.request.urlopen(base + path)
    assert failure.value.code == 404
    assert (portfolio.paused, list(portfolio.runners)) == before


def test_reference_renderer_lifecycle():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the presentation lifecycle harness')
    result = subprocess.run(
        [node, str(ROOT / 'tests_engine' / 'reference_choreography_lifecycle.cjs')],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['passed'] >= 8
