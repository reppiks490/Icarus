# Grok (xAI) — 2026-09-22.
import pytest
from icarus_plant.schwab import orders_unlocked, request

def test_orders_locked_by_default():
    assert orders_unlocked() is False

def test_orders_post_blocked():
    with pytest.raises(PermissionError):
        request("POST", "https://api.schwabapi.com/trader/v1/accounts/HASH/orders")

def test_preview_blocked():
    with pytest.raises(PermissionError):
        request("POST", "https://api.schwabapi.com/trader/v1/accounts/HASH/previewOrder")
