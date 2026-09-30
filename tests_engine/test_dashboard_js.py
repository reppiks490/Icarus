"""Parse every shipped dashboard JavaScript surface with Node when available."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed on this developer machine")
@pytest.mark.parametrize(
    "rel",
    [
        "icarus_engine/dashboard.html",
        "icarus_bridge/dashboard.html",
        "icarus_engine/research-ui.js",
        "icarus_engine/sources-ui.js",
        "icarus_engine/experience-ui.js",
    ],
)
def test_dashboard_javascript_parses(rel, tmp_path):
    src = (REPO / rel).read_text(encoding="utf-8")
    if rel.endswith(".html"):
        blocks = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", src, flags=re.IGNORECASE)
        assert blocks, f"{rel} has no inline JavaScript to validate"
        src = "\n".join(blocks)
    out = tmp_path / (Path(rel).name.replace(".html", "") + ".js")
    out.write_text(src, encoding="utf-8")
    result = subprocess.run([NODE, "--check", str(out)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_engine_dashboard_has_no_expiry_contract_ui():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "a.next_contract" not in src
    assert "a.contract?" not in src
    assert "continuous_symbol || a.provider_symbol || a.symbol" in src


def test_strategy_tester_timeframes_are_cache_aware():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "available_from_cache" in src
    assert "cache unavailable" in src
    assert "cached_source_resolutions_minutes" in src
    assert "$('#btAsset').addEventListener('change'" in src
    assert "BT.res = null; BT.compare = null" in src


def test_databento_dashboard_distinguishes_raw_feed_from_strategy_chart():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert "Databento raw · 1s · ticks · MBP-10 · MBO" in src
    assert "strategy chart · minute-native" in src
    assert "a.feed_provider==='databento'" in src
