"""FMP historical equity bars for explicitly configured, read-only probes.

This connector does not attest mapping, exchange entitlement, bar finality, or
terms. Callers must preserve those gaps in their receipts and keep unqualified
bars outside Pulse.
"""
from __future__ import annotations

from datetime import date, datetime, time as wall_time
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ..pine.timeframe import Bar


_ET = ZoneInfo("America/New_York")
_INTERVAL_PATH = {
    60: "1min",
    300: "5min",
    900: "15min",
    1800: "30min",
    3600: "1hour",
    14400: "4hour",
}


class FmpHistory:
    """Fetch FMP history using an API key supplied outside the repository."""

    GRANULARITIES = (*_INTERVAL_PATH.keys(), 86400)
    BASE = "https://financialmodelingprep.com/stable"
    MAX_BYTES = 32 << 20

    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        self.api_key = (api_key or os.environ.get("FMP_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is required for FMP historical data")
        self.timeout = timeout
        self._metadata: dict[str, dict[str, Any]] = {}

    def _get(self, path: str, params: dict[str, str]) -> Any:
        query = urlencode({**params, "apikey": self.api_key})
        request = Request(f"{self.BASE}/{path}?{query}", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not response.geturl().startswith("https://"):
                    raise RuntimeError("FMP redirected to a non-HTTPS URL")
                raw = response.read(self.MAX_BYTES + 1)
                if len(raw) > self.MAX_BYTES:
                    raise RuntimeError("FMP response exceeds 32 MiB")
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"FMP request failed with HTTP {exc.code}") from None
        except URLError as exc:
            raise RuntimeError(f"FMP request failed: {exc.reason}") from None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("FMP returned malformed JSON") from exc

    @staticmethod
    def _date(ts: int) -> str:
        return datetime.fromtimestamp(ts, _ET).date().isoformat()

    @staticmethod
    def _timestamp(value: str, daily: bool) -> int:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            if daily and " " not in value and "T" not in value:
                parsed = datetime.combine(parsed.date(), wall_time(9, 30), tzinfo=_ET)
            else:
                parsed = parsed.replace(tzinfo=_ET)
        return int(parsed.timestamp())

    def candles(self, symbol: str, interval: int, start: int, end: int) -> list[Bar]:
        if interval not in self.GRANULARITIES:
            raise ValueError(f"FMP does not support {interval}-second intervals")
        params = {"symbol": symbol, "from": self._date(start), "to": self._date(end)}
        if interval == 86400:
            path = "historical-price-eod/full"
        else:
            path = f"historical-chart/{_INTERVAL_PATH[interval]}"
        payload = self._get(path, params)
        if not isinstance(payload, list):
            raise RuntimeError("FMP history response is not a row list")
        bars = []
        for row in payload:
            if not isinstance(row, dict) or not isinstance(row.get("date"), str):
                raise RuntimeError("FMP history row has no timestamp")
            try:
                ts = self._timestamp(row["date"], interval == 86400)
                bars.append(Bar(
                    ts,
                    float(row["open"]), float(row["high"]), float(row["low"]),
                    float(row["close"]), float(row.get("volume") or 0),
                ))
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError("FMP history row has invalid timestamp or OHLCV") from exc
        bars.sort(key=lambda bar: bar.ts)
        return [bar for bar in bars if start <= bar.ts < end]

    def meta(self, symbol: str) -> dict[str, Any]:
        if symbol not in self._metadata:
            rows = self._get("profile", {"symbol": symbol})
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
                return {}
            self._metadata[symbol] = rows[0]
        return self._metadata[symbol]
