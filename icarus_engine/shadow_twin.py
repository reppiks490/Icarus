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
        # This is close-marked observation only; it is not intrabar drawdown.
        self._equity_peaks = {"primary": float(primary.initial_capital),
                              "shadow": float(primary.initial_capital)}
        self._bar_close_max_drawdowns = {"primary": 0.0, "shadow": 0.0}
        self._bar_close_equity_observations = 0
        self._administrative_censored_positions = 0
        self._administrative_censor_events: list[dict[str, Any]] = []
        self._administratively_flattened_lot_ids: dict[str, set[int]] = {
            "primary": set(), "shadow": set(),
        }

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
            pair[lane] = {"entry_id": str(fill.entry_id), "ts": int(fill.ts),
                          "bar": int(fill.bar), "side": fill.side,
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
            self._record_bar_close_equity(primary_bar.c, real_bar.c)
        except Exception as exc:
            self._degrade(f"shadow bar processing failed: {type(exc).__name__}: {exc}")

    def _record_bar_close_equity(self, primary_mark: float, shadow_mark: float) -> None:
        """Track the maximum drawdown observed at paired bar closes."""
        for lane, engine, mark in (("primary", self.primary, primary_mark),
                                   ("shadow", self.shadow, shadow_mark)):
            equity = float(engine.equity(mark))
            peak = max(self._equity_peaks[lane], equity)
            self._equity_peaks[lane] = peak
            self._bar_close_max_drawdowns[lane] = max(
                self._bar_close_max_drawdowns[lane], peak - equity)
        self._bar_close_equity_observations += 1

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

    def process_administrative_flatten(self, primary_bar: Optional[Bar], bar_index: int,
                                       entry_ids: set[str], *, reason: str) -> None:
        """Flatten primary state at its admin mark and censor shadow positions.

        The primary runtime must honor an operator-requested flatten, but its
        wall-clock mark is not a paired market bar. Open shadow positions are
        therefore discarded as censored observations, not closed into shadow
        fill, outcome, realized-P&L, or bar-close drawdown statistics.
        """
        self._bar_index = int(bar_index)
        self._bar_ts = int(primary_bar.ts) if primary_bar is not None else None
        # Preserve operational closes while keeping the synthetic admin mark
        # and the affected whole lots out of market-bar evidence.
        self._administratively_flattened_lot_ids["primary"].update(
            int(trade.seq) for trade in self.primary.open if trade.entry_id in entry_ids)
        self._administratively_flattened_lot_ids["shadow"].update(
            int(trade.seq) for trade in self.shadow.open if trade.entry_id in entry_ids)
        if primary_bar is not None:
            primary_fills_before = len(self.primary.fills)
            self.primary.process_bar(primary_bar, bar_index)
            self._capture_entry_fills(self.primary, primary_fills_before, "primary")

        censored = [trade for trade in self.shadow.open if trade.entry_id in entry_ids]
        self._administratively_flattened_lot_ids["shadow"].update(
            int(trade.seq) for trade in censored)
        pending_entries = [row for row in self.shadow._pending_entries if row.id in entry_ids]
        for entry_id in entry_ids:
            self._pending_entry_intents["shadow"][:] = [
                row for row in self._pending_entry_intents["shadow"] if row["id"] != entry_id]
        self.shadow.open[:] = [trade for trade in self.shadow.open if trade.entry_id not in entry_ids]
        self.shadow._pending_entries[:] = [row for row in self.shadow._pending_entries
                                           if row.id not in entry_ids]
        self.shadow._pending_closes[:] = [row for row in self.shadow._pending_closes
                                          if row.entry_id not in entry_ids]
        self.shadow._exits = {key: order for key, order in self.shadow._exits.items()
                              if order.from_entry not in entry_ids}
        self._administrative_censored_positions += len(censored)
        if censored or pending_entries:
            self._administrative_censor_events.append({
                "bar_ts": int(primary_bar.ts) if primary_bar is not None else None,
                "bar_index": int(bar_index),
                "reason": str(reason),
                "censored_positions": len(censored),
                "cancelled_pending_entries": len(pending_entries),
                "entry_ids": sorted(entry_ids),
                "shadow_market_outcome_recorded": False,
            })
        self._intent("administrative_flatten", {
            "reason": str(reason), "entry_ids": sorted(entry_ids),
            "censored_positions": len(censored),
            "cancelled_pending_entries": len(pending_entries),
            "shadow_market_outcome_recorded": False,
        })

    def _episodes(self, engine: Emulator, lane: str) -> tuple[dict[Any, dict[str, Any]], int]:
        intent_by_entry: dict[tuple[str, int, int, str, int, float], int] = {}
        for intent_seq, pair in self._entry_fill_pairs.items():
            fill = pair.get(lane)
            if fill is None:
                continue
            identity = (fill["entry_id"], fill["ts"], fill["bar"], fill["side"],
                        fill["qty"], fill["price"])
            intent_by_entry[identity] = int(intent_seq)

        episodes: dict[Any, dict[str, Any]] = defaultdict(
            lambda: {"net": 0.0, "pieces": 0, "qty": 0, "closed": False,
                     "entry_qty": 0, "closed_qty": 0,
                     "entry_ts": 0, "last_exit_ts": 0,
                     "runup": 0.0, "drawdown": 0.0})
        excluded_admin_flatten_pieces = 0
        for trade in engine.closed:
            if int(trade.lot_id) in self._administratively_flattened_lot_ids[lane]:
                excluded_admin_flatten_pieces += 1
                continue
            side = "buy" if int(trade.direction) > 0 else "sell"
            identity = (str(trade.entry_id), int(trade.entry_ts), int(trade.entry_bar),
                        side, int(trade.entry_qty or trade.qty), float(trade.entry_price))
            intent_seq = intent_by_entry.get(identity)
            # Unlinked records are intentionally lane-specific. Similar labels
            # or timestamps alone are insufficient evidence to pair outcomes.
            key = ("UNMATCHED", lane, *identity) if intent_seq is None else intent_seq
            row = episodes[key]
            row["net"] += float(trade.profit)
            row["pieces"] += 1
            row["qty"] += int(trade.qty)
            row["closed_qty"] += int(trade.qty)
            row["runup"] += float(trade.runup)
            row["drawdown"] += float(trade.drawdown)
            row["entry_qty"] = max(row["entry_qty"], int(trade.entry_qty or trade.qty))
            row["closed"] = row["closed_qty"] >= row["entry_qty"]
            row["entry_ts"] = int(trade.entry_ts)
            row["last_exit_ts"] = max(row["last_exit_ts"], int(trade.exit_ts))
        return dict(episodes), excluded_admin_flatten_pieces

    def summary(self, *, live_from_ts: Optional[int] = None) -> dict[str, Any]:
        primary_eps, primary_admin_flatten_pieces = self._episodes(self.primary, "primary")
        shadow_eps, shadow_admin_flatten_pieces = self._episodes(self.shadow, "shadow")
        primary_closed = {key: row for key, row in primary_eps.items() if row["closed"]}
        shadow_closed = {key: row for key, row in shadow_eps.items() if row["closed"]}
        common = sorted(primary_closed.keys() & shadow_closed.keys())
        directional = [k for k in common if primary_closed[k]["net"] != 0 and shadow_closed[k]["net"] != 0]
        agreement = sum((primary_closed[k]["net"] > 0) == (shadow_closed[k]["net"] > 0)
                        for k in directional)
        primary_wins = [k for k in common if primary_closed[k]["net"] > 0]
        shadow_wins_preserved = sum(shadow_closed[k]["net"] > 0 for k in primary_wins)
        outcome_matrix = {primary: {shadow: 0 for shadow in ("win", "loss", "break_even")}
                          for primary in ("win", "loss", "break_even")}
        for key in common:
            p_net, s_net = primary_closed[key]["net"], shadow_closed[key]["net"]
            p_outcome = "win" if p_net > 0 else "loss" if p_net < 0 else "break_even"
            s_outcome = "win" if s_net > 0 else "loss" if s_net < 0 else "break_even"
            outcome_matrix[p_outcome][s_outcome] += 1

        def totals(keys: dict[tuple[str, int, str], dict[str, Any]]) -> dict[str, float | int]:
            # Attribute by entry decision time. A warm-up position closing
            # after go-live remains part of warm-up evidence.
            warmup = [v for v in keys.values() if live_from_ts is None or v["entry_ts"] < live_from_ts]
            live = [v for v in keys.values() if live_from_ts is not None and v["entry_ts"] >= live_from_ts]
            return {"episodes": len(keys),
                    "closed_episodes": sum(v["closed"] for v in keys.values()),
                    "partial_realized_episodes": sum(not v["closed"] for v in keys.values()),
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
        primary_net = float(sum(row["net"] for row in primary_eps.values()))
        shadow_net = float(sum(row["net"] for row in shadow_eps.values()))
        paired_primary_winner_net = float(sum(primary_eps[key]["net"] for key in primary_wins))
        paired_shadow_net_on_primary_winners = float(sum(shadow_eps[key]["net"] for key in primary_wins))
        epsilon = max(1e-8, abs(primary_net) * 1e-12)
        net_realization_ratio = shadow_net / primary_net if primary_net > epsilon else None
        paired_profit_capture = (paired_shadow_net_on_primary_winners / paired_primary_winner_net
                                 if paired_primary_winner_net > 1e-8 else None)

        def delta_summary(values: list[float]) -> dict[str, Any]:
            ordered = sorted(values)
            return {"count": len(ordered), "mean": (sum(ordered) / len(ordered) if ordered else None),
                    "median": (median(ordered) if ordered else None),
                    "min": (ordered[0] if ordered else None), "max": (ordered[-1] if ordered else None)}

        def closed_excursions(rows: dict[Any, dict[str, Any]]) -> dict[str, Any]:
            closed_rows = [row for row in rows.values() if row["closed"]]
            return {
                "episode_count": len(closed_rows),
                "favorable_excursion": round(sum(row["runup"] for row in closed_rows), 8),
                "adverse_excursion": round(sum(row["drawdown"] for row in closed_rows), 8),
            }

        primary_excursions = closed_excursions(primary_closed)
        shadow_excursions = closed_excursions(shadow_closed)
        matched_favorable_deltas = [shadow_closed[key]["runup"] - primary_closed[key]["runup"]
                                    for key in common]
        matched_adverse_deltas = [shadow_closed[key]["drawdown"] - primary_closed[key]["drawdown"]
                                  for key in common]

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
            "primary_only_closed_episodes": len(primary_closed.keys() - shadow_closed.keys()),
            "shadow_only_closed_episodes": len(shadow_closed.keys() - primary_closed.keys()),
            "pairable_closed_episodes": len(common),
            "excluded_admin_flatten_lot_trade_pieces": {
                "primary": primary_admin_flatten_pieces,
                "shadow": shadow_admin_flatten_pieces,
            },
            "outcome_agreement_denominator": len(directional),
            "outcome_agreement_rate": (agreement / len(directional) if directional else None),
            "outcome_agreement_count": agreement,
            "outcome_matrix": outcome_matrix,
            "primary_break_even_episodes": sum(primary_eps[k]["net"] == 0 for k in common),
            "shadow_break_even_episodes": sum(shadow_eps[k]["net"] == 0 for k in common),
            "primary_win_count": len(primary_wins),
            "primary_win_preserved_count": shadow_wins_preserved,
            "primary_win_preservation": (shadow_wins_preserved / len(primary_wins) if primary_wins else None),
            "primary": totals(primary_eps),
            "real_price_shadow": totals(shadow_eps),
            "net_realization_ratio": net_realization_ratio,
            "net_realization_ratio_unavailable_reason": (
                None if net_realization_ratio is not None else
                "primary net is non-positive or too close to zero"),
            "paired_profit_capture": paired_profit_capture,
            "paired_profit_capture_unavailable_reason": (
                None if paired_profit_capture is not None else
                "no positive pairable primary-winner P&L denominator"),
            "paired_primary_winner_net": round(paired_primary_winner_net, 8),
            "paired_shadow_net_on_primary_winners": round(paired_shadow_net_on_primary_winners, 8),
            "closed_episode_excursion_basis": (
                "EMULATOR_OBSERVED_HIGH_LOW_THROUGH_EXIT_FILL_QTY_WEIGHTED_ENTRY_COMMISSION_ADJUSTED"
            ),
            "primary_closed_episode_excursions": primary_excursions,
            "real_price_shadow_closed_episode_excursions": shadow_excursions,
            "matched_closed_episode_favorable_excursion_delta_shadow_minus_primary":
                delta_summary(matched_favorable_deltas),
            "matched_closed_episode_adverse_excursion_delta_shadow_minus_primary":
                delta_summary(matched_adverse_deltas),
            "bar_close_drawdown_basis": "BAR_CLOSE_MARKED_EQUITY_NOT_INTRABAR",
            "bar_close_equity_observations": self._bar_close_equity_observations,
            "administrative_censored_shadow_positions": self._administrative_censored_positions,
            "recent_administrative_censors": self._administrative_censor_events[-20:],
            "primary_bar_close_max_drawdown": round(self._bar_close_max_drawdowns["primary"], 8),
            "real_price_shadow_bar_close_max_drawdown": round(self._bar_close_max_drawdowns["shadow"], 8),
            "open_primary": len(self.primary.open),
            "open_shadow": len(self.shadow.open),
            "recent_intents": self.intents[-20:],
        }
