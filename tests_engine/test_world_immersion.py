"""Presentation-only invariants for full-dashboard ICARUS immersion."""
from pathlib import Path


ROOT = Path(__file__).parents[1]
IMMERSION = ROOT / "icarus_engine" / "world-immersion.js"
DASHBOARD = ROOT / "icarus_engine" / "dashboard.html"


def test_immersion_runtime_has_no_market_or_control_io():
    source = IMMERSION.read_text(encoding="utf-8")
    forbidden = (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "sendBeacon",
        "/api/",
        "/admin/",
        "localStorage",
        "sessionStorage",
    )
    for token in forbidden:
        assert token not in source, f"presentation runtime must not perform I/O: {token}"


def test_immersion_runtime_is_loaded_before_dashboard_world_motion():
    html = DASHBOARD.read_text(encoding="utf-8")
    immersion = html.index('<script src="/world-immersion.js"></script>')
    motion = html.index('<script src="/world-motion.js"></script>')
    experience = html.index('<script src="/experience-ui.js"></script>')
    assert immersion < motion < experience


def test_immersion_runtime_keeps_motion_and_visibility_gates():
    source = IMMERSION.read_text(encoding="utf-8")
    for guard in (
        "prefers-reduced-motion: reduce",
        "root.dataset.motion==='live'",
        "root.dataset.experience==='cinematic'",
        "!document.hidden",
        "root.dataset.introActive!=='true'",
    ):
        assert guard in source


def test_adaptive_brain_visuals_follow_world_tokens():
    source = (ROOT / "icarus_engine" / "brain-ui.js").read_text(encoding="utf-8")
    for fixed in (
        "rgba(86,225,255,.16)",
        "rgba(145,92,255,.12)",
        "rgba(95,232,255,.35)",
        "background:#67e8f9",
    ):
        assert fixed not in source
    assert "var(--view-accent" in source
