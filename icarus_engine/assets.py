"""Asset registry: what each symbol is, where its bars come from, how it is aligned and sized.

Futures identity/economics are derived from :mod:`icarus_engine.futures_catalog`.
`multiplier` is the emulator's contract_size: P&L = points × multiplier ×
contracts, exactly as TradingView computes it for the futures symbol.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from .futures_catalog import FUTURES_PRODUCTS, FuturesProduct


# The strategy/chart execution layer is intentionally minute-native even when the
# active raw feed (Databento) exposes 1-second bars, ticks, and depth. These are the
# chart choices exposed by the UI/MCP; arbitrary positive minute values remain
# accepted by the parser for backward compatibility with existing presets.
PRIMARY_INTRADAY_TIMEFRAMES = ("1", "2", "5", "10", "20", "30")
PRIMARY_SECOND_TIMEFRAMES = ("1S", "5S", "10S", "15S", "30S")
PRIMARY_TICK_TIMEFRAMES = ("50T", "100T", "250T", "500T", "1000T")
CHART_TIMEFRAME_OPTIONS = ("1", "2", "3", "5", "10", "15", "20", "30", "45", "60", "120", "180", "240", "D", "W")
CHART_TYPES = ("heikin_ashi", "real")
FILL_MODES = ("real", "chart")
SECURITY_SOURCES = ("chart", "standard")


def chart_timeframe_parts(value: object) -> tuple[str, int]:
    """Return (mode, value) where mode is minutes, seconds, or ticks."""
    t = re.sub(r"\s+", " ", str(value).strip().upper())
    if not t:
        raise ValueError("chart timeframe is required")

    tick = re.fullmatch(r"(\d+)\s*(?:T|TICK|TICKS)", t)
    if tick:
        n = int(tick.group(1))
        if not 1 <= n <= 100000:
            raise ValueError("tick chart size must be between 1 and 100000 trades")
        return "ticks", n

    sec = re.fullmatch(r"(\d+)\s*(?:S|SEC|SECS|SECOND|SECONDS)", t)
    if sec:
        n = int(sec.group(1))
        if not 1 <= n < 60:
            raise ValueError("second chart size must be between 1 and 59 seconds; use minute timeframes at 60 seconds or above")
        return "seconds", n

    words = re.fullmatch(r"(\d+)\s*(MIN|MINS|MINUTE|MINUTES|HOUR|HOURS|DAY|DAYS|WEEK|WEEKS)", t)
    if words:
        n = int(words.group(1))
        unit = words.group(2)
        mult = 1 if unit.startswith("MIN") else 60 if unit.startswith("HOUR") else 1440 if unit.startswith("DAY") else 10080
        mins = n * mult
        if mins <= 0 or mins > 10080:
            raise ValueError("chart timeframe must be between 1 minute and one week")
        return "minutes", mins
    if t in ("D", "1D"):
        return "minutes", 1440
    if t in ("W", "1W"):
        return "minutes", 10080
    if t.endswith("H") and t[:-1].isdigit():
        mins = int(t[:-1]) * 60
        if 0 < mins <= 10080:
            return "minutes", mins
        return _bad_timeframe(value)
    if t.endswith("M") and t[:-1].isdigit():
        t = t[:-1]
    if not t.isdigit() or int(t) <= 0:
        return _bad_timeframe(value)
    mins = int(t)
    if mins > 10080:
        raise ValueError("chart timeframe must be at most one week (10080 minutes)")
    return "minutes", mins


def normalize_chart_timeframe(value: object) -> str:
    """Canonicalize strategy chart timeframes.

    The branch retains authentic event/tick adapters internally, but the Pine-style
    strategy/backtest contract remains minute-native until every downstream consumer
    (HTF chains, cache replay, Strategy Tester) is event-timeframe aware.
    """
    mode, n = chart_timeframe_parts(value)
    if mode == "seconds":
        raise ValueError("sub-minute chart timeframes are raw-event capabilities, not strategy chart timeframes")
    if mode == "ticks":
        raise ValueError("tick chart timeframes are raw-event capabilities, not strategy chart timeframes")
    if n == 1440:
        return "D"
    if n == 10080:
        return "W"
    return str(n)


def _bad_timeframe(value: object) -> str:
    raise ValueError(f"unsupported chart timeframe {value!r}; use positive minutes, D, or W")


def chart_capabilities() -> Dict[str, object]:
    return {
        "timeframes": list(CHART_TIMEFRAME_OPTIONS),
        "primary_intraday_timeframes": list(PRIMARY_INTRADAY_TIMEFRAMES),
        "primary_second_timeframes": [],
        "primary_tick_timeframes": [],
        "chart_types": list(CHART_TYPES),
        "fill_modes": list(FILL_MODES),
        "security_sources": list(SECURITY_SOURCES),
        "seconds": False,
        "ticks": False,
        "raw_event_seconds": True,
        "raw_event_ticks": True,
        "minimum_live_resolution": "trade-event",
        "requires_event_feed": False,
        "note": "Authentic event/tick adapters are retained as raw capabilities; strategy charts remain minute-native and ICARUS never fabricates ticks.",
    }


def validate_chart_config(values: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Validate user-facing chart/execution settings and return canonical values."""
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise ValueError("chart configuration must be an object")
    allowed = {"timeframe", "chart_type", "fill_on", "security_source"}
    bad = set(values) - allowed
    if bad:
        raise ValueError(f"unknown chart configuration fields {sorted(bad)}")
    out: Dict[str, object] = {}
    if values.get("timeframe") not in (None, ""):
        out["timeframe"] = normalize_chart_timeframe(values["timeframe"])
    if values.get("chart_type") not in (None, ""):
        v = str(values["chart_type"])
        if v not in CHART_TYPES:
            raise ValueError(f"chart_type must be one of {CHART_TYPES}")
        out["chart_type"] = v
    if values.get("fill_on") not in (None, ""):
        v = str(values["fill_on"])
        if v not in FILL_MODES:
            raise ValueError(f"fill_on must be one of {FILL_MODES}")
        out["fill_on"] = v
    if values.get("security_source") not in (None, ""):
        v = str(values["security_source"])
        if v not in SECURITY_SOURCES:
            raise ValueError(f"security_source must be one of {SECURITY_SOURCES}")
        out["security_source"] = v
    return out


def pin_config(spec: "AssetSpec", *keys: str) -> "AssetSpec":
    """Mark explicit startup/API configuration so preset metadata cannot silently overwrite it."""
    return replace(spec, config_pins=sorted(set(spec.config_pins) | {str(k) for k in keys}))


def apply_chart_config(spec: "AssetSpec", values: Optional[Dict[str, object]], *, pin: bool = False) -> "AssetSpec":
    """Return a copy of *spec* with validated chart settings applied."""
    out = replace(spec)
    cfg = validate_chart_config(values)
    if "timeframe" in cfg:
        out.chart_tf = str(cfg["timeframe"])
    for key in ("chart_type", "fill_on", "security_source"):
        if key in cfg:
            setattr(out, key, str(cfg[key]))
    return pin_config(out, *cfg.keys()) if pin and cfg else out


@dataclass
class AssetSpec:
    symbol: str                      # short name used everywhere (NQ, ES, BTC ...)
    name: str
    feed: str                        # yahoo | coinbase
    ticker: str                      # feed symbol (NQ=F, BTC-USD)
    calendar: str                    # cme | cme_crypto | crypto
    mintick: float
    multiplier: float                # $ per 1.0 price point per contract (contract_size)
    kind: str = "futures"            # futures | crypto
    tv_symbol: str = ""              # TradingView symbol, for parity exports
    chart_tf: str = "20"
    preset: Optional[str] = None     # inputs preset name (presets/<name>.json)
    chart_type: str = "real"         # real | heikin_ashi  (what the STRATEGY sees)
    fill_on: str = "real"            # real | chart        (what the EMULATOR fills on; chart = TradingView "Heikin Ashi bars")
    slippage_ticks: int = 0
    capital: float = 500000.0
    commission: float = 2.0
    anchor_et: Optional[str] = None  # intraday bar anchor override (ET "HHMM"); derived from `session` when None
    session: str = "rth"             # rth | eth
    group: str = "equity"            # holiday schedule family
    security_source: str = "chart"   # chart | standard
    roll: str = "none"               # compatibility field; futures are invariantly continuous
    exchange: str = ""
    asset_class: str = ""
    micro_of: Optional[str] = None
    feed_mode: str = ""
    config_pins: List[str] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Safety invariant: no saved config/activation may resurrect a dated-contract roller.
        self.roll = "continuous" if self.kind == "futures" else "none"


def _future_asset(product: FuturesProduct) -> AssetSpec:
    return AssetSpec(
        symbol=product.root,
        name=product.name,
        feed="yahoo",
        ticker=product.provider_symbol,
        calendar=product.calendar,
        mintick=product.tick_size,
        multiplier=product.point_value,
        tv_symbol=product.tv_symbol,
        session=product.session,
        group=product.group,
        exchange=product.exchange,
        asset_class=product.asset_class,
        micro_of=product.full_root if product.full_root != product.root else None,
        feed_mode="public_delayed",
    )


REGISTRY: Dict[str, AssetSpec] = {
    **{root: _future_asset(product) for root, product in FUTURES_PRODUCTS.items()},
    "BTC": AssetSpec("BTC", "Bitcoin spot (Coinbase)", "coinbase", "BTC-USD", "crypto", 0.01, 1.0,
                     kind="crypto", tv_symbol="COINBASE:BTCUSD", exchange="COINBASE", asset_class="crypto_spot", feed_mode="public_realtime"),
    "ETH": AssetSpec("ETH", "Ether spot (Coinbase)", "coinbase", "ETH-USD", "crypto", 0.01, 1.0,
                     kind="crypto", tv_symbol="COINBASE:ETHUSD", exchange="COINBASE", asset_class="crypto_spot", feed_mode="public_realtime"),
    "SOL": AssetSpec("SOL", "Solana spot (Coinbase)", "coinbase", "SOL-USD", "crypto", 0.01, 1.0,
                     kind="crypto", tv_symbol="COINBASE:SOLUSD", exchange="COINBASE", asset_class="crypto_spot", feed_mode="public_realtime"),
}

# First-party trading assets use Heikin Ashi as the primary analytical chart.
# Fills remain on real OHLC by default, so synthetic HA prices never become
# executable prices unless the user explicitly selects fill_on="chart".
for _spec in REGISTRY.values():
    _spec.chart_type = "heikin_ashi"
    if _spec.kind == "futures":
        if not _spec.ticker.endswith("=F"):
            raise RuntimeError(f"{_spec.symbol}: futures provider symbol must be continuous (=F), got {_spec.ticker!r}")
        if not _spec.tv_symbol.endswith("1!"):
            raise RuntimeError(f"{_spec.symbol}: TradingView futures identity must be continuous (1!), got {_spec.tv_symbol!r}")
        if _spec.roll != "continuous":
            raise RuntimeError(f"{_spec.symbol}: futures contract policy must be continuous_only")

ALIASES = {
    "GOLD": "GC", "SILVER": "SI", "PLATINUM": "PL", "PALLADIUM": "PA",
    "BTC=F": "BTCF", "BTC1!": "BTCF", "BTC1": "BTCF",
    "BTCUSD": "BTC", "BTC-USD": "BTC",
    "NASDAQ": "NQ", "SP500": "ES", "DOW": "YM", "RUSSELL": "RTY", "RUSSELL2000": "RTY",
}
for _root, _product in FUTURES_PRODUCTS.items():
    ALIASES.setdefault(f"{_root}1!", _root)
    ALIASES.setdefault(f"{_root}1", _root)
    ALIASES.setdefault(_product.provider_symbol, _root)
    ALIASES.setdefault(_product.tv_symbol.split(":")[-1], _root)


_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9=!.\-]{0,15}")
_FUTURES_ROOTS = tuple(sorted({
    root
    for spec in REGISTRY.values() if spec.kind == "futures"
    for root in (spec.symbol, spec.ticker[:-2] if spec.ticker.endswith("=F") else spec.ticker)
}, key=len, reverse=True))
_EXPIRING_FUTURE_RE = re.compile(
    rf"^(?:{'|'.join(_FUTURES_ROOTS)})[FGHJKMNQUVXZ]\d{{1,4}}(?:\.(?:CME|CBT|CMX|NYM|NYMEX|COMEX))?$"
)
# Fail closed for any conventional futures month-code symbol, even when the root is
# not in REGISTRY. Otherwise e.g. CLZ26 could fall through as a fake Coinbase asset.
_ANY_DATED_FUTURE_RE = re.compile(
    r"^[A-Z0-9]{1,6}[FGHJKMNQUVXZ]\d{1,4}(?:\.(?:CME|CBT|CMX|NYM|NYMEX|COMEX))?$"
)
_CONTINUOUS_FUTURE_STYLE_RE = re.compile(r"^[A-Z0-9]{1,8}(?:1!?|=F)$")


def resolve(symbol: str) -> AssetSpec:
    s = symbol.strip().upper().split(":")[-1]
    if _EXPIRING_FUTURE_RE.fullmatch(s) or _ANY_DATED_FUTURE_RE.fullmatch(s):
        root = next((r for r in _FUTURES_ROOTS if s.startswith(r)), re.sub(r"[FGHJKMNQUVXZ]\d{1,4}.*$", "", s) or "future")
        raise ValueError(
            f"expiring futures symbol {symbol!r} is forbidden; ICARUS is continuous-only — use a continuous 1!/=F identity"
            + (f" for {root}" if root != "future" else "")
        )
    raw = s
    s = ALIASES.get(s, s)
    if s in REGISTRY:
        spec = REGISTRY[s]
        if spec.kind == "futures":
            product = FUTURES_PRODUCTS.get(s)
            if product is not None and not product.runtime_qualified:
                raise ValueError(
                    f"unsupported continuous futures symbol {symbol!r}; {s} is registered for discovery "
                    "but its runtime admission is not yet qualified"
                )
        return replace(spec)
    if _CONTINUOUS_FUTURE_STYLE_RE.fullmatch(raw):
        raise ValueError(
            f"unsupported continuous futures symbol {symbol!r}; ICARUS only accepts runtime-qualified continuous futures "
            "(TradingView 1! / provider =F) and never reinterprets them as crypto"
        )
    if not _SYMBOL_RE.fullmatch(s):
        raise ValueError(f"bad symbol {symbol!r}: letters, digits, '-', '.', '=' and '!' only")
    raise ValueError(
        f"unregistered asset {symbol!r}; source identity, market metadata, and bar capabilities must be qualified "
        "before the symbol can enter Pulse (catalog candidates alone are not runtime assets)"
    )


def parse_spec(token: str, default_tf: str = "20") -> AssetSpec:
    """'NQ', 'NQ@20', 'GC@10:NQ-10m-original' → AssetSpec with tf / preset."""
    tf, preset = default_tf, None
    sym = token.strip()
    if ":" in sym and not sym.upper().startswith(("CME", "CME_MINI", "COMEX", "NYMEX", "COINBASE", "CBOT", "CBOT_MINI")):
        sym, preset = sym.split(":", 1)
    explicit_tf = "@" in sym
    if explicit_tf:
        sym, tf = sym.split("@", 1)
    spec = resolve(sym)
    spec.chart_tf = normalize_chart_timeframe(tf)
    spec.preset = preset
    return pin_config(spec, "timeframe") if explicit_tf else spec
