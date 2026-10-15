"""Fail-isolated same-decision real-price emulator twin.

The facade deliberately exposes primary emulator reads to PulseStrategy and
mirrors only its explicitly inventoried order mutations. It has no broker or
external execution interface.
"""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any, Optional

from .emulator import Emulator
from .pine.timeframe import Bar


_MUTATORS = {"entry", "exit", "close", "cancel"}


class MirroredEmulator:
    """Emulator-compatible wrapper; reads are primary-only, writes are mirrored."""

    def __init__(self, primary: Emulator, *, asset: str = ""):
        self.primary = primary
        self.shadow = Emulator(
            primary.initial_capital, primary.commission, primary.mintick,
            primary.contract_size, primary.pyramiding, primary.slippage_ticks,
        )
        self.asset = str(asset)
        self.enabled = True
        self.status = "READY"
        self.reason: Optional[str] = None
        self.intent_seq = 0
        self.intents: list[dict[str, Any]] = []
        self._pending_entry_intents: dict[str, list[dict[str, Any]]] = {"primary": [], "shadow": []}
        self._entry_fill_pairs: dict[int, dict[str, Any]] = {}
        self._bar_index = -1
        self._bar_ts: Optional[int] = None

    def __getattr__(self, name: str) -> Any:
        # Strategy and existing runtime diagnostics see canonical state only.
        return getattr(self.primary, name)

    @staticmethod
    def mutator_contract() -> frozenset[str]:
        """The mutation inventory pinned by tests against Emulator's public API."""
        return frozenset(_MUTATORS)

    def _intent(self, method: str, args: dict[str, Any]) -> int:
        self.intent_seq += 1
        self.intents.append({
            "intent_seq": self.intent_seq,
            "asset": self.asset,
            "bar_index": self._bar_index,
            "bar_ts": self._bar_ts,
            "method": method,
            "args": args,
            "primary_position_before": self.primary.position_size,
            "shadow_position_before": self.shadow.position_size,
            "execution_authorized": False,
        })
        return self.intent_seq

    def _mirror(self, method: str, args: dict[str, Any], *call_args: Any, **call_kwargs: Any) -> int:
        intent_seq = self._intent(method, args)
        getattr(self.primary, method)(*call_args, **call_kwargs)
        if self.enabled:
            try:
                getattr(self.shadow, method)(*call_args, **call_kwargs)
            except Exception as exc:  # fail-isolated: primary must remain authoritative
                self._degrade(f"shadow {method} failed: {type(exc).__name__}: {exc}")
        return intent_seq

    def _register_entry_intent(self, intent_seq: int, args: dict[str, Any]) -> None:
        record = {"intent_seq": intent_seq, "id": str(args["id"]),
                  "direction": int(args["direction"]), "qty": int(args["qty"])}
        lanes = ("primary", "shadow") if self.enabled else ("primary",)
        for lane in lanes:
            queue = self._pending_entry_intents[lane]
            queue[:] = [row for row in queue if row["id"] != record["id"]]
            queue.append(dict(record))

    def _capture_entry_fills(self, engine: Emulator, start: int, lane: str) -> None:
        for fill in engine.fills[start:]:
            if fill.kind != "entry":
                continue
            direction = 1 if fill.side == "buy" else -1
            queue = self._pending_entry_intents[lane]
            match = next((row for row in queue if row["id"] == fill.entry_id
                          and row["direction"] == direction and row["qty"] == fill.qty), None)
            if match is None:
                continue
            queue.remove(match)
            pair = self._entry_fill_pairs.setdefault(match["intent_seq"], {"intent_seq": match["intent_seq"]})
            pair[lane] = {"ts": int(fill.ts), "bar": int(fill.bar), "side": fill.side,
                          "qty": int(fill.qty), "price": float(fill.price)}

    def _degrade(self, reason: str, *, invalid: bool = False) -> None:
        self.enabled = False
        self.status = "INVALID" if invalid else "DEGRADED"
        self.reason = reason

    def process_bar(self, primary_bar: Bar, bar_index: int, *, real_bar: Optional[Bar] = None) -> None:
        """Advance both lanes; primary always runs, shadow requires a valid paired real bar."""
        self._bar_index = int(bar_index)
        self._bar_ts = int(primary_bar.ts)
        primary_fills_before = len(self.primary.fills)
        self.primary.process_bar(primary_bar, bar_index)
        self._capture_entry_fills(self.primary, primary_fills_before, "primary")
        if not self.enabled:
            return
        try:
            if real_bar is None:
                self._degrade("standard real-price bar missing")
                return
            if int(real_bar.ts) != int(primary_bar.ts):
                self._degrade("paired bar timestamp mismatch", invalid=True)
                return
            values = tuple(float(v) for v in (real_bar.o, real_bar.h, real_bar.l, real_bar.c))
            if not all(math.isfinite(v) for v in values):
                self._degrade("standard real-price bar contains non-finite OHLC", invalid=True)
                return
            o, h, l, c = values
            if h < max(o, c, l) or l > min(o, c, h):
                self._degrade("standard real-price bar OHLC range is malformed", invalid=True)
                return
            shadow_fills_before = len(self.shadow.fills)
            self.shadow.process_bar(real_bar, bar_index)
            self._capture_entry_fills(self.shadow, shadow_fills_before, "shadow")
        except Exception as exc:
            self._degrade(f"shadow bar processing failed: {type(exc).__name__}: {exc}")

    def entry(self, id: str, direction: int, qty: int, limit: Optional[float] = None,
              comment: str = "", alert_message: str = "") -> None:
        args = {"id": id, "direction": direction, "qty": qty, "limit": limit,
                "comment": comment, "alert_message": alert_message}
        intent_seq = self._mirror("entry", args, id, direction, qty, limit, comment, alert_message)
        self._register_entry_intent(intent_seq, args)

    def exit(self, id: str, from_entry: str, qty: Optional[int] = None,
             profit: Optional[float] = None, loss: Optional[float] = None,
             limit: Optional[float] = None, stop: Optional[float] = None,
             comment_profit: str = "", comment_loss: str = "") -> None:
        args = {"id": id, "from_entry": from_entry, "qty": qty, "profit": profit,
                "loss": loss, "limit": limit, "stop": stop,
                "comment_profit": comment_profit, "comment_loss": comment_loss}
        self._mirror("exit", args, id, from_entry, qty, profit, loss, limit, stop,
                     comment_profit, comment_loss)

    def close(self, entry_id: str, comment: str = "") -> None:
        self._mirror("close", {"entry_id": entry_id, "comment": comment}, entry_id, comment)

    def cancel(self, id: str) -> None:
        self._mirror("cancel", {"id": id}, id)
        for queue in self._pending_entry_intents.values():
            queue[:] = [row for row in queue if row["id"] != id]

    def cancel_pending_entries(self, entry_ids: set[str]) -> None:
        """Mirror runtime's administrative cancellation, including attached orphan exits."""
        if not entry_ids:
            return
        self._intent("cancel_pending_entries", {"entry_ids": sorted(entry_ids)})
        for queue in self._pending_entry_intents.values():
            queue[:] = [row for row in queue if row["id"] not in entry_ids]
        def cancel(engine: Emulator) -> None:
            engine._pending_entries[:] = [p for p in engine._pending_entries if p.id not in entry_ids]
            for exit_id, order in list(engine._exits.items()):
                if order.from_entry in entry_ids and not engine.qty_open(order.from_entry):
                    engine._exits.pop(exit_id, None)
            engine._pending_closes[:] = [c for c in engine._pending_closes
                                         if c.entry_id not in entry_ids or engine.qty_open(c.entry_id)]
        cancel(self.primary)
        if self.enabled:
            try:
                cancel(self.shadow)
            except Exception as exc:
                self._degrade(f"shadow administrative cancellation failed: {type(exc).__name__}: {exc}")

    @staticmethod
    def _episodes(engine: Emulator) -> dict[tuple[str, int, str], dict[str, Any]]:
        episodes: dict[tuple[str, int, str], dict[str, Any]] = defaultdict(
            lambda: {"net": 0.0, "pieces": 0, "qty": 0, "closed": False, "last_exit_ts": 0})
        for trade in engine.closed:
            key = (trade.entry_id, int(trade.entry_ts), trade.entry_comment or "")
            row = episodes[key]
            row["net"] += float(trade.profit)
            row["pieces"] += 1
            row["qty"] += int(trade.qty)
            row["closed"] = True
            row["last_exit_ts"] = max(row["last_exit_ts"], int(trade.exit_ts))
        return dict(episodes)

    def summary(self, *, live_from_ts: Optional[int] = None) -> dict[str, Any]:
        primary_eps = self._episodes(self.primary)
        shadow_eps = self._episodes(self.shadow)
        common = sorted(primary_eps.keys() & shadow_eps.keys())
        directional = [k for k in common if primary_eps[k]["net"] != 0 and shadow_eps[k]["net"] != 0]
        agreement = sum((primary_eps[k]["net"] > 0) == (shadow_eps[k]["net"] > 0)
                        for k in directional)
        primary_wins = [k for k in common if primary_eps[k]["net"] > 0]
        shadow_wins_preserved = sum(shadow_eps[k]["net"] > 0 for k in primary_wins)

        def totals(keys: dict[tuple[str, int, str], dict[str, Any]]) -> dict[str, float | int]:
            warmup = [v for v in keys.values() if live_from_ts is None or v["last_exit_ts"] < live_from_ts]
            live = [v for v in keys.values() if live_from_ts is not None and v["last_exit_ts"] >= live_from_ts]
            return {"episodes": len(keys), "closed_episodes": len(keys),
                    "net": round(sum(v["net"] for v in keys.values()), 8),
                    "warmup_net": round(sum(v["net"] for v in warmup), 8),
                    "live_net": round(sum(v["net"] for v in live), 8)}

        primary_entries = sum(f.kind == "entry" for f in self.primary.fills)
        shadow_entries = sum(f.kind == "entry" for f in self.shadow.fills)
        matched_entry_pairs = [pair for pair in self._entry_fill_pairs.values()
                               if "primary" in pair and "shadow" in pair]
        primary_only_entries = sum("primary" in pair and "shadow" not in pair
                                   for pair in self._entry_fill_pairs.values())
        shadow_only_entries = sum("shadow" in pair and "primary" not in pair
                                  for pair in self._entry_fill_pairs.values())
        entry_deltas = [pair["shadow"]["price"] - pair["primary"]["price"]
                        for pair in matched_entry_pairs]
        entry_delta_dollars = [delta * pair["primary"]["qty"] * self.primary.contract_size
                               for pair, delta in zip(matched_entry_pairs, entry_deltas)]

        def delta_summary(values: list[float]) -> dict[str, Any]:
            ordered = sorted(values)
            return {"count": len(ordered), "mean": (sum(ordered) / len(ordered) if ordered else None),
                    "median": (median(ordered) if ordered else None),
                    "min": (ordered[0] if ordered else None), "max": (ordered[-1] if ordered else None)}

        return {
            "schema": "icarus.real_price_shadow/1",
            "enabled": True,
            "status": self.status,
            "reason": self.reason,
            "execution_authorized": False,
            "fill_basis": "STANDARD_REAL_BAR_EMULATOR",
            "signal_basis": "PRIMARY_ICARUS_ORDER_INTENTS",
            "asset": self.asset,
            "intents": len(self.intents),
            "primary_entry_fills": primary_entries,
            "shadow_entry_fills": shadow_entries,
            "entry_fill_parity": (len(matched_entry_pairs) / primary_entries if primary_entries else None),
            "primary_only_entry_fills": primary_only_entries,
            "shadow_only_entry_fills": shadow_only_entries,
            "matched_entry_intents": len(matched_entry_pairs),
            "entry_price_delta_points_shadow_minus_primary": delta_summary(entry_deltas),
            "entry_price_delta_ticks_shadow_minus_primary": delta_summary(
                [value / self.primary.mintick for value in entry_deltas] if self.primary.mintick else []),
            "entry_price_delta_dollars_shadow_minus_primary": delta_summary(entry_delta_dollars),
            "recent_entry_fill_pairs": matched_entry_pairs[-20:],
            "primary_only_closed_episodes": len(primary_eps.keys() - shadow_eps.keys()),
            "shadow_only_closed_episodes": len(shadow_eps.keys() - primary_eps.keys()),
            "pairable_closed_episodes": len(common),
            "outcome_agreement_denominator": len(directional),
            "outcome_agreement_rate": (agreement / len(directional) if directional else None),
            "outcome_agreement_count": agreement,
            "primary_break_even_episodes": sum(primary_eps[k]["net"] == 0 for k in common),
            "shadow_break_even_episodes": sum(shadow_eps[k]["net"] == 0 for k in common),
            "primary_win_count": len(primary_wins),
            "primary_win_preserved_count": shadow_wins_preserved,
            "primary_win_preservation": (shadow_wins_preserved / len(primary_wins) if primary_wins else None),
            "primary": totals(primary_eps),
            "real_price_shadow": totals(shadow_eps),
            "open_primary": len(self.primary.open),
            "open_shadow": len(self.shadow.open),
            "recent_intents": self.intents[-20:],
        }
