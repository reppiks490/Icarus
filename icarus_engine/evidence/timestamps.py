"""Timestamp encoding normalization with explicit identity and timezone policy.

Numeric units are detected by magnitude, not attested by a provider. Exact
decimal seconds remain available alongside the existing float display value.
No received/available time or bar completion time is inferred here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, DecimalException, localcontext

PARSER_VERSION = "icarus.evidence.timestamps/1"
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_ISO_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,](?P<fraction>\d+))?"
                          r"(?P<offset>Z|[+-]\d{2}(?::?\d{2})?(?::?\d{2}(?:[.,]\d+)?)?)?$")
_FINE_FRACTION = re.compile(r"[.,]\d{7,}")
_FRACTIONAL_OFFSET = re.compile(r"[+-]\d{2}(?::?\d{2})?(?::?\d{2})?[.,]\d+$")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_UPPER = Decimal(4102444800)  # exclusive: 2100-01-01 UTC


@dataclass(frozen=True)
class TimestampEvidence:
    raw_value: str
    epoch_seconds: float
    epoch_seconds_exact: str
    detected_unit: str
    timezone_basis: str
    whole_second: bool


def _declared_wall_time(dt, tz):
    # A wall time must round-trip to itself and have exactly one UTC identity.
    # This refuses both nonexistent spring times and ambiguous autumn folds.
    identities = {}
    for fold in (0, 1):
        try:
            aware = dt.replace(tzinfo=tz, fold=fold)
            utc = aware.astimezone(timezone.utc)
            if utc.astimezone(tz).replace(tzinfo=None) == dt:
                identities[utc] = aware
        except (OverflowError, ValueError, TypeError):
            return None
    return next(iter(identities.values())) if len(identities) == 1 else None


def normalize_timestamp(raw, *, naive_timezone=None) -> TimestampEvidence | None:
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        return None
    original = str(raw)
    s = original.strip().strip('"')
    if not s or len(s) > 128:
        return None
    if _NUMBER.fullmatch(s):
        try:
            with localcontext() as ctx:
                ctx.prec = max(40, len(s) + 12)
                n = Decimal(s)
                if not n.is_finite() or n <= 0:
                    return None
                if n < Decimal("1e10"):
                    unit, exponent = "seconds", 0
                elif n < Decimal("1e13"):
                    unit, exponent = "milliseconds", -3
                elif n < Decimal("1e16"):
                    unit, exponent = "microseconds", -6
                else:
                    unit, exponent = "nanoseconds", -9
                epoch = n.scaleb(exponent)
                if not 0 < epoch < _UPPER:
                    return None
                exact = format(epoch.normalize(), "f")
        except DecimalException:
            return None
        basis = "UTC_EPOCH"
    else:
        exact_iso = _ISO_SECONDS.fullmatch(s)
        # datetime truncates fractions beyond microseconds, and can discard
        # fractional UTC offsets entirely. Preserve supported clock fractions
        # explicitly; refuse fractional offsets and other fine ISO forms.
        if _FRACTIONAL_OFFSET.search(s):
            return None
        if _FINE_FRACTION.search(s) and exact_iso is None:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            dt = None
            for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%d.%m.%Y %H:%M"):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                return None
        if dt.tzinfo is None or dt.utcoffset() is None:
            if naive_timezone is None:
                return None
            dt = _declared_wall_time(dt, naive_timezone)
            if dt is None:
                return None
            basis = "DECLARED:" + str(getattr(naive_timezone, "key", None) or naive_timezone)
        else:
            basis = "EXPLICIT_OFFSET"
        try:
            delta = dt.astimezone(timezone.utc) - _EPOCH
        except (OverflowError, ValueError):
            return None
        with localcontext() as ctx:
            ctx.prec = max(40, len(s) + 20)
            epoch = Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / Decimal(1000000)
            if exact_iso and exact_iso["fraction"]:
                epoch += Decimal("0." + exact_iso["fraction"]) - Decimal(dt.microsecond) / Decimal(1000000)
            if not 0 < epoch < _UPPER:
                return None
            exact = format(epoch.normalize(), "f")
        unit = "iso8601"
    return TimestampEvidence(original, float(epoch), exact, unit, basis, epoch == epoch.to_integral_value())
