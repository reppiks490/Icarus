"""Asset registry: what each symbol is, where its bars come from, how it is aligned and sized.

Contract specs are CME's (tick size, $ per point). `multiplier` is the emulator's
contract_size: P&L = points × multiplier × contracts, exactly as TradingView
computes it for the futures symbol.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional


# The live adapters currently provide minute OHLC bars. These are the chart choices
# exposed by the UI/MCP; arbitrary positive minute values remain accepted by the
# parser for backward compatibility with existing presets.
PRIMARY_INTRADAY_TIMEFRAMES = ("1", "2", "5", "10", "20", "30")
CHART_TIMEFRAME_OPTIONS = ("1", "2", "3", "5", "10", "15", "20", "30", "45", "60", "120", "180", "240", "D", "W")
CHART_TYPES = ("heikin_ashi", "real")
FILL_MODES = ("real", "chart")
SECURITY_SOURCES = ("chart", "standard")


def normalize_chart_timeframe(value: object) -> str:
    """Canonicalize chart timeframes while refusing synthetic sub-minute/tick precision.

    Accepts Pine-style values ("20", "4H", "D", "W") and the human-readable
    strings TradingView exports ("20 minutes", "1 hour", "1 day", "1 week").
    """
    t = re.sub(r"\s+", " ", str(value).strip().upper())
    if not t:
        raise ValueError("chart timeframe is required")
    if re.fullmatch(r"\d+\s*(?:T|TICK|TICKS)", t):
        raise ValueError("tick charts require a true tick-data adapter; the current ICARUS feeds do not provide one")
    if re.fullmatch(r"\d+\s*(?:S|SEC|SECS|SECOND|SECONDS)", t):
        raise ValueError("second charts require a sub-minute data adapter; the current ICARUS feeds are 1-minute minimum")
    words = re.fullmatch(r"(\d+)\s*(MIN|MINS|MINUTE|MINUTES|HOUR|HOURS|DAY|DAYS|WEEK|WEEKS)", t)
    if words:
        n = int(words.group(1))
        unit = words.group(2)
        mult = 1 if unit.startswith("MIN") else 60 if unit.startswith("HOUR") else 1440 if unit.startswith("DAY") else 10080
        mins = n * mult
        if mins <= 0 or mins > 10080:
            raise ValueError("chart timeframe must be between 1 minute and one week")
        return "D" if mins == 1440 else "W" if mins == 10080 else str(mins)
    if t in ("D", "1D"):
        return "D"
    if t in ("W", "1W"):
        return "W"
    if t.endswith("H") and t[:-1].isdigit():
        n = int(t[:-1]) * 60
        return str(n) if 0 < n <= 10080 else _bad_timeframe(value)
    if t.endswith("M") and t[:-1].isdigit():
        t = t[:-1]
    if not t.isdigit() or int(t) <= 0:
        return _bad_timeframe(value)
    if int(t) > 10080:
        raise ValueError("chart timeframe must be at most one week (10080 minutes)")
    return str(int(t))


def _bad_timeframe(value: object) -> str:
    raise ValueError(f"unsupported chart timeframe {value!r}; use positive minutes, D, or W")


def chart_capabilities() -> Dict[str, object]:
    return {
        "timeframes": list(CHART_TIMEFRAME_OPTIONS),
        "primary_intraday_timeframes": list(PRIMARY_INTRADAY_TIMEFRAMES),
        "chart_types": list(CHART_TYPES),
        "fill_modes": list(FILL_MODES),
        "security_sources": list(SECURITY_SOURCES),
        "seconds": False,
        "ticks": False,
        "minimum_live_resolution": "1m",
        "note": "Seconds/ticks are capability-gated until a genuine sub-minute/tick feed is installed; ICARUS never fabricates ticks.",
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
    calendar: str                    # cme | crypto
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
    session: str = "rth"             # rth | eth  - TradingView chart session for CME futures (see calendar.CMECalendar)
    group: str = "equity"            # holiday schedule: equity | metals | crypto (CME Bitcoin futures follow equity)
    security_source: str = "chart"   # chart | standard - what request.security() sees on a Heikin Ashi chart (chart = HA, TradingView)
    roll: str = "none"               # compatibility field; futures are invariantly continuous
    config_pins: List[str] = field(default_factory=list, repr=False, compare=False)  # explicit startup/API values that beat preset metadata

    def __post_init__(self) -> None:
        # Safety invariant: no saved config/activation may resurrect a dated-contract roller.
        self.roll = "continuous" if self.kind == "futures" else "none"


REGISTRY: Dict[str, AssetSpec] = {
    "NQ": AssetSpec("NQ", "Nasdaq 100 E-mini", "yahoo", "NQ=F", "cme", 0.25, 20.0, tv_symbol="CME_MINI:NQ1!"),
    "MNQ": AssetSpec("MNQ", "Nasdaq 100 Micro E-mini", "yahoo", "MNQ=F", "cme", 0.25, 2.0, tv_symbol="CME_MINI:MNQ1!"),
    "MES": AssetSpec("MES", "Micro E-mini S&P 500", "yahoo", "MES=F", "cme", 0.25, 5.0, tv_symbol="CME_MINI:MES1!"),
    "ES": AssetSpec("ES", "S&P 500 E-mini", "yahoo", "ES=F", "cme", 0.25, 50.0, tv_symbol="CME_MINI:ES1!"),
    "YM": AssetSpec("YM", "Dow E-mini", "yahoo", "YM=F", "cme", 1.0, 5.0, tv_symbol="CBOT_MINI:YM1!"),
    "MYM": AssetSpec("MYM", "Micro E-mini Dow", "yahoo", "MYM=F", "cme", 1.0, 0.5, tv_symbol="CBOT_MINI:MYM1!"),
    "RTY": AssetSpec("RTY", "E-mini Russell 2000", "yahoo", "RTY=F", "cme", 0.10, 50.0, tv_symbol="CME_MINI:RTY1!"),
    "M2K": AssetSpec("M2K", "Micro E-mini Russell 2000", "yahoo", "M2K=F", "cme", 0.10, 5.0, tv_symbol="CME_MINI:M2K1!"),
    "GC": AssetSpec("GC", "Gold", "yahoo", "GC=F", "cme", 0.10, 100.0, tv_symbol="COMEX:GC1!", group="metals"),
    "MGC": AssetSpec("MGC", "Micro Gold", "yahoo", "MGC=F", "cme", 0.10, 10.0, tv_symbol="COMEX_MINI:MGC1!", group="metals"),
    "SI": AssetSpec("SI", "Silver", "yahoo", "SI=F", "cme", 0.005, 5000.0, tv_symbol="COMEX:SI1!", group="metals"),
    "SIL": AssetSpec("SIL", "Micro Silver", "yahoo", "SIL=F", "cme", 0.005, 1000.0, tv_symbol="COMEX_MINI:SIL1!", group="metals"),
    "PL": AssetSpec("PL", "Platinum", "yahoo", "PL=F", "cme", 0.10, 50.0, tv_symbol="NYMEX:PL1!", group="metals"),
    "PA": AssetSpec("PA", "Palladium", "yahoo", "PA=F", "cme", 0.50, 100.0, tv_symbol="NYMEX:PA1!", group="metals"),
    "BTCF": AssetSpec("BTCF", "Bitcoin futures (CME)", "yahoo", "BTC=F", "cme_crypto", 5.0, 5.0, tv_symbol="CME:BTC1!", group="crypto", session="eth"),
    "MBT": AssetSpec("MBT", "Micro Bitcoin futures (CME)", "yahoo", "MBT=F", "cme_crypto", 5.0, 0.1, tv_symbol="CME:MBT1!", group="crypto", session="eth"),
    "BTC": AssetSpec("BTC", "Bitcoin spot (Coinbase)", "coinbase", "BTC-USD", "crypto", 0.01, 1.0, kind="crypto", tv_symbol="COINBASE:BTCUSD"),
    "ETH": AssetSpec("ETH", "Ether spot (Coinbase)", "coinbase", "ETH-USD", "crypto", 0.01, 1.0, kind="crypto", tv_symbol="COINBASE:ETHUSD"),
    "SOL": AssetSpec("SOL", "Solana spot (Coinbase)", "coinbase", "SOL-USD", "crypto", 0.01, 1.0, kind="crypto", tv_symbol="COINBASE:SOLUSD"),
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
    "NQ1!": "NQ", "NQ1": "NQ", "NQ=F": "NQ",
    "MNQ1!": "MNQ", "MNQ1": "MNQ", "MNQ=F": "MNQ",
    "ES1!": "ES", "ES1": "ES", "ES=F": "ES",
    "MES1!": "MES", "MES1": "MES", "MES=F": "MES",
    "YM1!": "YM", "YM1": "YM", "YM=F": "YM",
    "MYM1!": "MYM", "MYM1": "MYM", "MYM=F": "MYM",
    "RTY1!": "RTY", "RTY1": "RTY", "RTY=F": "RTY",
    "M2K1!": "M2K", "M2K1": "M2K", "M2K=F": "M2K",
    "GC1!": "GC", "GC1": "GC", "GC=F": "GC", "GOLD": "GC",
    "MGC1!": "MGC", "MGC1": "MGC", "MGC=F": "MGC",
    "SI1!": "SI", "SI1": "SI", "SI=F": "SI", "SILVER": "SI",
    "SIL1!": "SIL", "SIL1": "SIL", "SIL=F": "SIL",
    "PL1!": "PL", "PL1": "PL", "PL=F": "PL", "PLATINUM": "PL",
    "PA1!": "PA", "PA1": "PA", "PA=F": "PA", "PALLADIUM": "PA",
    "BTC=F": "BTCF", "BTC1!": "BTCF", "BTC1": "BTCF",
    "MBT=F": "MBT", "MBT1!": "MBT", "MBT1": "MBT",
    "BTCUSD": "BTC", "BTC-USD": "BTC",
    "NASDAQ": "NQ", "SP500": "ES", "DOW": "YM", "RUSSELL": "RTY",
}


_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9=!.\-]{0,15}")
_FUTURES_ROOTS = tuple(sorted({
    root
    for spec in REGISTRY.values() if spec.kind == "futures"
    for root in (spec.symbol, spec.ticker[:-2] if spec.ticker.endswith("=F") else spec.ticker)
}, key=len, reverse=True))
_EXPIRING_FUTURE_RE = re.compile(
    rf"^(?:{'|'.join(_FUTURES_ROOTS)})[FGHJKMNQUVXZ]\d{{1,4}}(?:\.(?:CME|CBT|CMX|NYM|NYMEX|COMEX))?$"
)


def resolve(symbol: str) -> AssetSpec:
    s = symbol.strip().upper().split(":")[-1]
    if _EXPIRING_FUTURE_RE.fullmatch(s):
        root = next((r for r in sorted(_FUTURES_ROOTS, key=len, reverse=True) if s.startswith(r)), "future")
        raise ValueError(
            f"expiring futures symbol {symbol!r} is forbidden; ICARUS is continuous-only — use {root}1! or {root}=F"
        )
    s = ALIASES.get(s, s)
    if s in REGISTRY:
        return replace(REGISTRY[s])
    if not _SYMBOL_RE.fullmatch(s):
        raise ValueError(f"bad symbol {symbol!r}: letters, digits, '-', '.', '=' and '!' only")
    # unknown → assume a Coinbase spot pair (keyless), 24/7
    base = s.replace("-USD", "").replace("USD", "")
    if not re.fullmatch(r"[A-Z0-9]{1,12}", base):
        raise ValueError(f"bad symbol {symbol!r}")
    return AssetSpec(base, f"{base} spot (Coinbase)", "coinbase", f"{base}-USD", "crypto", 0.01, 1.0, kind="crypto", tv_symbol=f"COINBASE:{base}USD", chart_type="heikin_ashi")


def parse_spec(token: str, default_tf: str = "20") -> AssetSpec:
    """'NQ', 'NQ@20', 'GC@10:NQ-10m-original' → AssetSpec with tf / preset."""
    tf, preset = default_tf, None
    sym = token.strip()
    if ":" in sym and not sym.upper().startswith(("CME", "COMEX", "NYMEX", "COINBASE", "CBOT")):
        sym, preset = sym.split(":", 1)
    explicit_tf = "@" in sym
    if explicit_tf:
        sym, tf = sym.split("@", 1)
    spec = resolve(sym)
    spec.chart_tf = normalize_chart_timeframe(tf)
    spec.preset = preset
    return pin_config(spec, "timeframe") if explicit_tf else spec
