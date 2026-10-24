"""Selected cached tape identity and native paper go-live integrity gates."""
from __future__ import annotations

from .golive import from_status
from .workspace_market_data import snapshot as market_snapshot
from .workspace_research_engines import private_root
from .workspace_api import WorkspaceAPIError


def snapshot(port):
    """Reuse native integrity math, exposing only selected cached feed identity."""
    private_root(port.base_dir)
    status = port.status()
    nq = next((row for row in status.get("assets", []) if row.get("symbol") == "NQ"), None)
    feeds = []
    for runner in port.runner_list():
        # PanelRunner.feed already wraps this same cached reader. No raw feed
        # accessor, environment feed selector, or parent history root is used.
        underlying = getattr(runner, "_runner", runner)
        if not underlying.lock.acquire(timeout=0.05):
            raise WorkspaceAPIError(503, "selected cached feed is busy", "SNAPSHOT_UNAVAILABLE")
        try:
            caps = market_snapshot(underlying, "capabilities")
        finally:
            underlying.lock.release()
        feeds.append({"asset": runner.symbol, "provider": caps["provider"],
                      "capabilities": caps["capabilities"], "metadata": caps["metadata"],
                      "available": caps["available"], "reason": caps["reason"],
                      "cached_only": True, "acquisition_requested": False})
    providers = sorted({str(row["provider"]) for row in feeds})
    identity = "Selected workspace cached tape: " + (", ".join(providers) if providers else "unavailable")
    # Broker process environment is outside this selected paper workspace. The
    # explicit paper flag expresses its enforced execution boundary.
    # Native from_status otherwise treats the first asset as NQ. Supply only
    # genuine selected NQ market context while retaining aggregate paper P&L.
    result = from_status({**status, "assets": [nq] if nq else []}, feed="file",
                         env={"ALPACA_PAPER": "true"}, base_dir=port.base_dir)
    result.update(feed=providers[0] if len(providers) == 1 else "mixed" if providers else "unavailable",
                  identity=identity, selected_feeds=feeds, broker_armed=False,
                  execution_authorized=False, production_decision_authorized=False,
                  nq_context_available=nq is not None,
                  history_scope="selected_workspace_private; shared history is not admitted by this adapter")
    for gate in result["gates"]:
        if gate["id"] == "tape":
            gate["detail"] = identity
            gate["ok"] = bool(nq and nq.get("price") is not None)
            gate["level"] = "ok" if gate["ok"] else "warn"
        elif gate["id"] == "feed_age":
            age = nq.get("price_age") if nq else None
            gate["ok"] = age is not None and 0 <= float(age) < 120
            gate["detail"] = f"Selected NQ cached price_age={age}s; this report does not refresh providers."
        elif gate["id"] == "bridge_secrets":
            gate["detail"] = "Bridge credentials are outside this paper workspace's integrity report."
        if nq is None and gate["id"] in {"tape", "session_rth", "feed_age", "fomc", "fill_model"}:
            gate.update(available=False, ok=False, level="warn",
                        detail="Unavailable: the selected workspace has no NQ runner for this NQ integrity check.")
    result["brains"]["B"] = "Selected workspace cached tape and local paper emulator fills."
    if result["verdict"] == "NO_TAPE":
        result["headline"] = "No cached tape in the selected workspace."
    if nq is None:
        result.update(verdict="NQ_UNAVAILABLE", headline="NQ integrity checks are unavailable in this selected workspace.",
                      nq_history={"path": None, "minutes": None})
    return result
