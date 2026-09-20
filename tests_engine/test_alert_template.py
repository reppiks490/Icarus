# Grok (xAI) — 2026-09-20. Whole file. pine/ALERT_TEMPLATE.json must parse the way the bridge expects.
"""pine/ALERT_TEMPLATE.json must parse the way the bridge expects."""
from __future__ import annotations

import json
import os

from icarus_bridge.models import parse_alert

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "pine", "ALERT_TEMPLATE.json")


def test_alert_template_file_exists_and_is_json():
    assert os.path.isfile(TPL)
    with open(TPL, encoding="utf-8") as fh:
        data = json.load(fh)
    for k in ("secret", "event", "ticker", "action", "contracts", "order_id",
              "comment", "order_price", "position_size", "market_position",
              "prev_market_position", "bar_close", "time", "meta"):
        assert k in data


def test_filled_template_parses_as_order_fill():
    with open(TPL, encoding="utf-8") as fh:
        raw = fh.read()
    filled = (
        raw.replace("YOUR_WEBHOOK_SECRET", "s3cret")
        .replace("{{ticker}}", "NQ1!")
        .replace("{{strategy.order.action}}", "buy")
        .replace("{{strategy.order.contracts}}", "5")
        .replace("{{strategy.order.id}}", "Long")
        .replace("{{strategy.order.comment}}", "")
        .replace("{{strategy.order.price}}", "24700.25")
        .replace("{{strategy.position_size}}", "5")
        .replace("{{strategy.market_position}}", "long")
        .replace("{{strategy.prev_market_position}}", "flat")
        .replace("{{close}}", "24701.00")
        .replace("{{timenow}}", "2026-09-14T13:50:00Z")
        .replace("{{strategy.order.alert_message}}", "sys=RATE;side=long;tp1=15;tp2=30;sl=45;q1=2;q2=3;ref=24700.25")
    )
    a = parse_alert(filled, expected_secret="s3cret")
    assert a.event == "order_fill"
    assert a.ticker == "NQ1!" and a.action == "buy"
    assert a.contracts == 5 and a.position_size == 5
    assert a.meta["sys"] == "RATE" and a.meta["sl"] == 45.0
    assert a.is_entry
