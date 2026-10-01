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


def test_asset_adder_uses_registry_and_timeframe_suggestions_and_single_flight_submit():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert 'list="addAssetOptions"' in src
    assert 'datalist id="addAssetOptions"' in src
    assert 'list="addTfOptions"' in src
    assert 'datalist id="addTfOptions"' in src
    assert "['1','2','3','5','10','15','20','30','45','60','120','180','240','D','W']" in src
    assert "REGISTRY.map" in src
    assert "b.disabled = true" in src
    assert "await admin('/admin/assets/add'" in src
    assert "j.detail||j.error||'request failed'" in src


def test_engine_dashboard_surfaces_repository_mcp_audit():
    src = (REPO / "icarus_engine/dashboard.html").read_text(encoding="utf-8")
    assert 'id="repoHealth"' in src
    assert 'data-v="system">System</span>' in src
    assert "repositoryAuditCard(window.ICARUS_AUDIT" in src
    assert "fetch('/api/system/audit'" in src
    assert "setInterval(refreshAudit, 20000)" in src
