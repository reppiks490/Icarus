import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from icarus_engine.feeds import yahoo


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return "https://query1.finance.yahoo.com/test"

    def read(self, _limit):
        return json.dumps({"ok": True}).encode()


def test_shared_client_paces_concurrent_request_starts(monkeypatch):
    interval = 0.04
    client = yahoo.Yahoo(min_interval=interval)
    starts = []
    starts_lock = threading.Lock()

    def fake_urlopen(_request, timeout):
        with starts_lock:
            starts.append(time.monotonic())
        return _Response()

    monkeypatch.setattr(yahoo.urllib.request, "urlopen", fake_urlopen)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda n: client._get(f"https://example.test/{n}"), range(8)))

    assert all(result == {"ok": True} for result in results)
    assert len(starts) == 8
    gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
    assert min(gaps) >= interval * 0.75
