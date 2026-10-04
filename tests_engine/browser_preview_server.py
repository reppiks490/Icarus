"""Feed-free dashboard preview used only by browser presentation checks."""
from __future__ import annotations

import os
import signal
from pathlib import Path

from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.server import serve


def main() -> None:
    root = Path(os.environ.get("ICARUS_BROWSER_PREVIEW_ROOT", "/tmp/icarus-browser-preview"))
    root.mkdir(parents=True, exist_ok=True)
    portfolio = Portfolio(Journal(":memory:"), str(root))
    server = serve(
        portfolio,
        int(os.environ.get("ICARUS_BROWSER_PREVIEW_PORT", "8879")),
        token="world-browser-test",
        start=False,
    )

    stopping = False

    def stop(*_args) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        server.shutdown()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        portfolio.journal.con.close()


if __name__ == "__main__":
    main()
