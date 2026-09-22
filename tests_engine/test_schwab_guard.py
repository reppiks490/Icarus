# Grok (xAI) — 2026-09-22.
import pytest
from icarus_plant.schwab import request

def test_orders_post_blocked():
    with pytest.raises(PermissionError):
        request("POST", "https://api.schwabapi.com/trader/v1/accounts/HASH/orders")

def test_preview_blocked():
    with pytest.raises(PermissionError):
        request("POST", "https://api.schwabapi.com/trader/v1/accounts/HASH/previewOrder")
