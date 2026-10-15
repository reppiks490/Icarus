"""Trading calendars: when a market is open, how its bars are aligned, what a "session" is.

  crypto  24/7, bars aligned to the UTC epoch, session (VWAP / daily bar) = UTC day.
  cme     CME Globex: Sunday 18:00 ET -> Friday 17:00 ET with a 17:00-18:00 ET maintenance
          break every day. The trading day ("trade date") starts at 18:00 ET and is named after
          the calendar day it ends on - the way TradingView and Yahoo stamp CME daily bars.

          Two chart modes, exactly as TradingView offers them (help-center 43000670909):
            eth  "Electronic Trading Hours" - the full session; intraday bars are anchored to the
                 18:00 ET session open (20m bars at :00/:20/:40, 4h at 18/22/02/06/10/14 ET).
            rth  "Regular Trading Hours" - a reduced session showing 08:30-15:15 CT
                 (09:30-16:15 ET) only; intraday bars are anchored to 09:30 ET (20m at :10/:30/:50,
                 the last bar 16:10-16:15 is a 5-minute stub), the daily candle is unchanged.
          The owner's validated NQ charts are RTH (every one of the 698 exported trade rows sits on a
          :10/:30/:50 bar between 08:50 and 15:10 CT; see PARITY.md A9 and the audit).

          Holidays: CME closes or halts early on US holidays. The schedule below is the published
          pattern (equity index vs metals; CME crypto futures trade 24/7 since 2026-05-29 and have none);
          CME confirms each date
          ~2 weeks ahead - verify on cmegroup.com. TradingView and Yahoo book a holiday's shortened
          session into the NEXT trade date's daily bar when the market reopens at 18:00 the same
          day (Thanksgiving Thursday -> Friday's bar, MLK Monday -> Tuesday's bar); the daily/weekly
          buckets and the session id here follow that rule.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from .pine.timeframe import _NY, _is_us_dst

# ET "HHMM" = the session halts/closes at that time on the trade date (reopens 18:00 ET the same day when the
# next calendar day is a trade date); "closed" = no session that trade date.
HOLIDAYS: Dict[str, Dict[str, str]] = {
    "equity": {
        "2026-01-19": "1300", "2026-02-16": "1300", "2026-04-03": "closed", "2026-05-25": "1300", "2026-06-19": "1300",
        "2026-07-02": "1300", "2026-07-03": "1300", "2026-09-07": "1300",
        "2026-11-26": "1300", "2026-11-27": "1315", "2026-12-24": "1315", "2026-12-25": "closed",
        "2027-01-01": "closed", "2027-01-18": "1300", "2027-02-15": "1300", "2027-03-26": "closed", "2027-05-31": "1300",
        "2027-06-18": "1300", "2027-07-05": "1300", "2027-09-06": "1300", "2027-11-25": "1300", "2027-11-26": "1315",
        "2027-12-23": "1315", "2027-12-24": "closed",     # New Year's Day 2028 is a Saturday: no Friday observance (NYSE/CME rule)
    },
    "metals": {
        "2026-01-19": "1430", "2026-02-16": "1430", "2026-04-03": "closed", "2026-05-25": "1430", "2026-06-19": "1300",
        "2026-07-02": "1430", "2026-07-03": "1300", "2026-09-07": "1430",
        "2026-11-26": "1430", "2026-11-27": "1445", "2026-12-24": "1345", "2026-12-25": "closed",
        "2027-01-01": "closed", "2027-01-18": "1430", "2027-02-15": "1430", "2027-03-26": "closed", "2027-05-31": "1430",
        "2027-06-18": "1430", "2027-07-05": "1430", "2027-09-06": "1430", "2027-11-25": "1430", "2027-11-26": "1445",
        "2027-12-23": "1345", "2027-12-24": "closed",
    },
}
HOLIDAYS["crypto"] = {}                          # CME crypto futures trade 24/7 since 2026-05-29 (CMECryptoCalendar); no holiday halts


def holiday_coverage(group: str = "equity"):
    """Latest dated entry in ``HOLIDAYS[group]``, or None if the table is empty.

    Grok (xAI) — 2026-09-20. CME publishes each holiday ~2 weeks ahead.
    ``icarus-engine doctor`` warns when this date is fewer than 90 days out —
    verify on cmegroup.com, do not invent dates.
    """
    table = HOLIDAYS.get(group) or {}
    if not table:
        return None
    return max(date.fromisoformat(k) for k in table)



def _ny(ts: int) -> datetime:
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    if _NY is not None:
        return dt.astimezone(_NY)
    return dt + timedelta(hours=-5 + (1 if _is_us_dst(dt) else 0))


def _from_ny(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> int:
    """Epoch seconds of a New-York wall-clock time."""
    if _NY is not None:
        return int(datetime(y, m, d, hh, mm, tzinfo=_NY).timestamp())
    naive = datetime(y, m, d, hh, mm, tzinfo=timezone.utc)
    off = -5 + (1 if _is_us_dst(naive) else 0)
    return int((naive - timedelta(hours=off)).timestamp())


def _at(day: date, hhmm: str) -> int:
    return _from_ny(day.year, day.month, day.day, int(hhmm[:2]), int(hhmm[2:4]))


class USEquitiesCalendar:
    """NYSE/Nasdaq regular-session calendar for the published 2026–2028 schedule.

    Holiday dates and early closes are transcribed from NYSE's published
    schedule at https://www.nyse.com/markets/hours-calendars. The bounded
    year range is deliberate: callers fail closed until the official schedule
    is extended, rather than extrapolating holidays or special closures.
    """
    name = "us_equities"
    open_24_7 = False
    session = "rth"
    SUPPORTED_YEARS = frozenset((2026, 2027, 2028))
    CLOSED = frozenset({
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
        "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
        "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
        "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
        "2028-01-17", "2028-02-21", "2028-04-14", "2028-05-29", "2028-06-19",
        "2028-07-04", "2028-09-04", "2028-11-23", "2028-12-25",
    })
    EARLY_CLOSES = {
        "2026-11-27": "1300", "2026-12-24": "1300",
        "2027-11-26": "1300",
        "2028-07-03": "1300", "2028-11-24": "1300",
    }
    OPEN = "0930"
    CLOSE = "1600"

    @staticmethod
    def _day(ts: int) -> date:
        return _ny(ts).date()

    def _require_supported(self, day: date) -> None:
        if day.year not in self.SUPPORTED_YEARS:
            raise ValueError(
                f"US equity calendar has no verified schedule for {day.year}; refusing to infer sessions"
            )

    def session_bounds(self, day: date) -> Optional[Tuple[int, int]]:
        self._require_supported(day)
        if day.weekday() >= 5 or day.isoformat() in self.CLOSED:
            return None
        close = self.EARLY_CLOSES.get(day.isoformat(), self.CLOSE)
        return _at(day, self.OPEN), _at(day, close)

    def is_open(self, ts: int) -> bool:
        bounds = self.session_bounds(self._day(ts))
        return bounds is not None and bounds[0] <= int(ts) < bounds[1]

    def intraday_open(self, ts: int) -> bool:
        return self.is_open(ts)

    def session_id(self, ts: int) -> str:
        day = self._day(ts)
        self._require_supported(day)
        return day.isoformat()

    def is_aligned(self, ts: int, interval_seconds: int) -> bool:
        if type(interval_seconds) is not int or interval_seconds <= 0:
            return False
        bounds = self.session_bounds(self._day(ts))
        if bounds is None or not bounds[0] <= int(ts) < bounds[1]:
            return False
        if interval_seconds == 86400:
            return int(ts) == bounds[0]
        if interval_seconds > 86400:
            return False
        return (int(ts) - bounds[0]) % interval_seconds == 0

    def expected_bar_timestamps(self, start_ts: int, end_ts: int, interval_seconds: int) -> list[int]:
        """Build exact RTH bar starts for a requested, bounded UTC time window."""
        if type(start_ts) is not int or type(end_ts) is not int or end_ts < start_ts:
            raise ValueError("US equity schedule window must use ordered integer timestamps")
        if type(interval_seconds) is not int or interval_seconds <= 0 or interval_seconds > 86400:
            raise ValueError("US equity interval must be a positive integer")
        start_day, end_day = self._day(start_ts), self._day(end_ts)
        if start_day.year not in self.SUPPORTED_YEARS or end_day.year not in self.SUPPORTED_YEARS:
            raise ValueError("US equity schedule window exceeds verified 2026–2028 coverage")
        days = (end_day - start_day).days
        if days > 366 * len(self.SUPPORTED_YEARS):
            raise ValueError("US equity schedule window is too large")
        result = []
        for offset in range(days + 1):
            bounds = self.session_bounds(start_day + timedelta(days=offset))
            if bounds is None:
                continue
            candidates = (bounds[0],) if interval_seconds == 86400 else range(bounds[0], bounds[1], interval_seconds)
            result.extend(ts for ts in candidates if start_ts <= ts < end_ts)
        return result

    def bucket_start(self, ts: int, minutes: int) -> int:
        if minutes <= 0:
            raise ValueError("timeframe minutes must be positive")
        day = self._day(ts)
        bounds = self.session_bounds(day)
        if bounds is None or not bounds[0] <= int(ts) < bounds[1]:
            raise ValueError("cannot form a US equity bar outside a trading session")
        if minutes >= 10080:
            monday = day - timedelta(days=day.weekday())
            for offset in range(5):
                session = self.session_bounds(monday + timedelta(days=offset))
                if session:
                    return session[0]
            raise ValueError("US equity week has no scheduled sessions")
        if minutes >= 1440:
            return bounds[0]
        span = int(minutes) * 60
        return bounds[0] + ((int(ts) - bounds[0]) // span) * span

    def bucket_end(self, bucket: int, minutes: int) -> int:
        bounds = self.session_bounds(self._day(bucket))
        if bounds is None:
            raise ValueError("cannot close a US equity bar outside a trading session")
        if minutes >= 10080:
            monday = self._day(bucket) - timedelta(days=self._day(bucket).weekday())
            sessions = [self.session_bounds(monday + timedelta(days=offset)) for offset in range(5)]
            closes = [session[1] for session in sessions if session]
            if not closes:
                raise ValueError("US equity week has no scheduled sessions")
            return closes[-1]
        if minutes >= 1440:
            return bounds[1]
        return min(int(bucket) + int(minutes) * 60, bounds[1])

    def time_close(self, bar_ts: int, minutes: int) -> int:
        return self.bucket_end(self.bucket_start(bar_ts, minutes), minutes)

    def next_open(self, ts: int) -> Optional[int]:
        if self.is_open(ts):
            return None
        day = self._day(ts)
        for offset in range(0, 10):
            bounds = self.session_bounds(day + timedelta(days=offset))
            if bounds is not None and bounds[0] > int(ts):
                return bounds[0]
        return None

    def describe(self, ts: int) -> str:
        if self.is_open(ts):
            close = self.EARLY_CLOSES.get(self._day(ts).isoformat())
            return "open" + (f" · early close {close[:2]}:{close[2:]} ET" if close else "")
        following = self.next_open(ts)
        return f"closed · opens {_ny(following).strftime('%a %H:%M ET')}" if following else "closed"


class CryptoCalendar:
    name = "crypto"
    open_24_7 = True
    session = "eth"

    def is_open(self, ts: int) -> bool:
        return True

    def intraday_open(self, ts: int) -> bool:
        return True

    def session_id(self, ts: int) -> str:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")

    def bucket_start(self, ts: int, minutes: int) -> int:
        span = int(minutes) * 60
        if minutes >= 10080:                                  # weeks start Monday 00:00 UTC (epoch was a Thursday)
            return ((int(ts) - 4 * 86400) // span) * span + 4 * 86400
        return (int(ts) // span) * span

    def bucket_end(self, bucket: int, minutes: int) -> int:
        return int(bucket) + int(minutes) * 60

    def next_open(self, ts: int) -> Optional[int]:
        return None

    def describe(self, ts: int) -> str:
        return "24/7"


class CMECalendar:
    """`session` = "eth" (full Globex session) or "rth" (TradingView's regular-hours chart, 09:30-16:15 ET).
    `group` selects the holiday schedule: equity (NQ/ES/YM, Bitcoin futures) or metals (GC/SI/PL/PA).
    `anchor_et` overrides the intraday bar anchor (derived from the session mode when None)."""
    name = "cme"
    open_24_7 = False
    OPEN_H, CLOSE_H = 18, 17                                 # ET, Globex
    RTH_OPEN, RTH_CLOSE = "0930", "1615"                     # ET, TradingView RTH = 08:30-15:15 CT

    def __init__(self, anchor_et: Optional[str] = None, session: str = "eth", group: str = "equity"):
        self.session = "rth" if str(session).lower() == "rth" else "eth"
        self.group = group if group in HOLIDAYS else "equity"
        self.holidays = HOLIDAYS[self.group]
        anchor = anchor_et or (self.RTH_OPEN if self.session == "rth" else "1800")
        self.anchor_h, self.anchor_m = int(anchor[:2]), int(anchor[2:4])
        self.anchor_et = anchor

    # ── trade dates and sessions ──
    def _holiday(self, day: date) -> Optional[str]:
        return self.holidays.get(day.isoformat())

    def is_trade_date(self, day: date) -> bool:
        return day.weekday() < 5 and self._holiday(day) != "closed"

    def trade_date(self, ts: int) -> date:
        d = _ny(ts)
        return d.date() + (timedelta(days=1) if d.hour >= self.OPEN_H else timedelta(0))

    def session_bounds(self, day: date) -> Optional[Tuple[int, int]]:
        """[open, close) of the Globex session whose trade date is `day`, or None."""
        if not self.is_trade_date(day):
            return None
        prev = day - timedelta(days=1)
        hol = self._holiday(day)
        close = _at(day, hol) if hol and hol != "closed" else _at(day, "1700")
        return _at(prev, "1800"), close

    def _merges_into_next(self, day: date) -> bool:
        """A shortened session followed by an 18:00 reopen the same day is booked into the next trade date's bar."""
        hol = self._holiday(day)
        return bool(hol) and hol != "closed" and self.is_trade_date(day + timedelta(days=1))

    def merged_trade_date(self, day: date) -> date:
        for _ in range(4):
            if self._merges_into_next(day):
                day = day + timedelta(days=1)
            else:
                break
        return day

    def _merged_group_start(self, day: date) -> date:
        for _ in range(4):
            prev = day - timedelta(days=1)
            if self.is_trade_date(prev) and self._merges_into_next(prev):
                day = prev
            else:
                break
        return day

    def _session_open(self, ts: int) -> int:
        """Open of the (merged) daily bar containing ts."""
        day = self._merged_group_start(self.trade_date(ts))
        return _at(day - timedelta(days=1), "1800")

    def rth_bounds(self, day: date) -> Optional[Tuple[int, int]]:
        b = self.session_bounds(day)
        if b is None:
            return None
        o = _at(day, self.RTH_OPEN)
        c = min(_at(day, self.RTH_CLOSE), b[1])
        return (o, c) if c > o else None

    # ── open / closed ──
    def is_open(self, ts: int) -> bool:
        """Globex session membership (data acceptance) - independent of the chart mode."""
        b = self.session_bounds(self.trade_date(ts))
        return b is not None and b[0] <= int(ts) < b[1]

    def intraday_open(self, ts: int) -> bool:
        """Whether an intraday chart bar exists at ts on this chart (RTH: 09:30-16:15 ET only)."""
        if self.session == "eth":
            return self.is_open(ts)
        day = _ny(ts).date()
        b = self.rth_bounds(day)
        return b is not None and b[0] <= int(ts) < b[1]

    def session_id(self, ts: int) -> str:
        """The daily bar a bar belongs to (VWAP / market-profile anchor)."""
        if self.session == "rth":
            day = _ny(ts).date()
        else:
            day = self.trade_date(ts)
        return self.merged_trade_date(day).isoformat()

    # ── bar alignment ──
    def bucket_start(self, ts: int, minutes: int) -> int:
        span = int(minutes) * 60
        if minutes >= 10080:                                   # week = the Sunday-18:00 open of that week
            so = self._session_open(ts)
            d = _ny(so)
            back = (d.weekday() + 1) % 7                       # days since Sunday
            sun = d.date() - timedelta(days=back)
            return _from_ny(sun.year, sun.month, sun.day, self.OPEN_H, 0)
        if minutes >= 1440:
            return self._session_open(ts)
        d = _ny(ts)
        if self.session == "rth":
            anchor = _from_ny(d.year, d.month, d.day, self.anchor_h, self.anchor_m)
            return anchor + ((int(ts) - anchor) // span) * span
        # ETH: anchored to the 18:00 ET open of the session that contains ts (buckets never cross a session open)
        day = self.trade_date(ts)
        anchor = _at(day - timedelta(days=1), self.anchor_et)
        return anchor + ((int(ts) - anchor) // span) * span

    def bucket_end(self, bucket: int, minutes: int) -> int:
        """Bar end; the last intraday bar of a session is truncated at the session close (TradingView's stub bar)."""
        if minutes >= 10080:
            return int(bucket) + 7 * 86400
        if minutes >= 1440:
            day = self.merged_trade_date(self.trade_date(int(bucket) + 3600))
            b = self.session_bounds(day)
            return b[1] if b else int(bucket) + 86400
        end = int(bucket) + int(minutes) * 60
        if self.session == "rth":
            rb = self.rth_bounds(_ny(bucket).date())
            return min(end, rb[1]) if rb else end
        b = self.session_bounds(self.trade_date(bucket))
        return min(end, b[1]) if b else end

    def time_close(self, bar_ts: int, minutes: int) -> int:
        return self.bucket_end(self.bucket_start(bar_ts, minutes), minutes)

    # ── status ──
    def next_open(self, ts: int) -> Optional[int]:
        """Next time an intraday bar can form on this chart (RTH open in rth mode, Globex open in eth)."""
        if self.intraday_open(ts):
            return None
        d = _ny(ts).date()
        for k in range(0, 10):
            day = d + timedelta(days=k)
            if self.session == "rth":
                rb = self.rth_bounds(day)
                if rb and rb[0] > ts:
                    return rb[0]
            else:
                b = self.session_bounds(day)
                if b and b[0] > ts:
                    return b[0]
        return None

    def describe(self, ts: int) -> str:
        tag = " (RTH)" if self.session == "rth" else ""
        if self.intraday_open(ts):
            hol = self._holiday(_ny(ts).date() if self.session == "rth" else self.trade_date(ts))
            return f"open{tag}" + (f" · early close {hol[:2]}:{hol[2:]} ET" if hol and hol != "closed" else "")
        no = self.next_open(ts)
        state = "closed" if not self.is_open(ts) else "outside RTH"
        return f"{state} · opens {_ny(no).strftime('%a %H:%M ET')}" if no else state


class CMECryptoCalendar(CMECalendar):
    """CME Bitcoin / Ether futures: around the clock since 2026-05-29 (CME press release, 2026-06-01) with a
    weekly weekend maintenance window (Saturday 02:00-04:00 CT here; CME guarantees "at least two hours").
    No daily 17:00-18:00 break, no holiday halts. Trade dates and daily/weekly bars still roll at 18:00 ET;
    intraday bars anchor to 18:00 ET (session mode `eth`)."""
    name = "cme_crypto"
    MAINT_START, MAINT_END = "0300", "0500"                   # Saturday, ET (02:00-04:00 CT)

    def __init__(self, anchor_et: Optional[str] = None, session: str = "eth", group: str = "crypto"):
        super().__init__(anchor_et, session="eth", group="crypto")
        self.holidays = {}

    def is_trade_date(self, day: date) -> bool:
        return True

    def session_bounds(self, day: date) -> Optional[Tuple[int, int]]:
        prev = day - timedelta(days=1)
        return _at(prev, "1800"), _at(day, "1800")

    def is_open(self, ts: int) -> bool:
        d = _ny(ts)
        if d.weekday() == 5:
            t = d.hour * 60 + d.minute
            ms = int(self.MAINT_START[:2]) * 60 + int(self.MAINT_START[2:]); me = int(self.MAINT_END[:2]) * 60 + int(self.MAINT_END[2:])
            return not (ms <= t < me)
        return True

    def intraday_open(self, ts: int) -> bool:
        return self.is_open(ts)

    def _merges_into_next(self, day: date) -> bool:
        return False

    def next_open(self, ts: int) -> Optional[int]:
        if self.is_open(ts):
            return None
        d = _ny(ts).date()
        return _at(d, self.MAINT_END)

    def describe(self, ts: int) -> str:
        if self.is_open(ts):
            return "open (24/7)"
        no = self.next_open(ts)
        return f"maintenance · opens {_ny(no).strftime('%a %H:%M ET')}" if no else "maintenance"


def get_calendar(name: str, anchor_et: Optional[str] = None, session: str = "eth", group: str = "equity"):
    n = str(name or "").strip().lower()
    if n in ("us_equities", "us_equity", "nyse", "nasdaq"):
        return USEquitiesCalendar()
    if n == "cme":
        return CMECalendar(anchor_et, session=session, group=group)
    if n == "cme_crypto":
        return CMECryptoCalendar(anchor_et)
    if n in ("", "crypto"):
        return CryptoCalendar()
    raise ValueError(f"unsupported market calendar {name!r}; refusing to assume 24/7 crypto hours")
