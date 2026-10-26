# 14 — orderbook readiness

**Decision: reference-only; block incorporation pending license and correctness work.** Static inspection only; no build, data download, or runtime verification.

- **Reusable candidates:** big-endian integer/nanosecond decoding (`include/utils.h:26–46`), typed ITCH order events (`include/Message.h:119–218`), price-level FIFO and aggregated books (`include/OrderBook.h:10–134`). These are implementation references, not validated components. CMake exposes executables only; no library/interface target.
- **Protocol gaps:** `Parser.h:70–102,182–206` consumes multiple message types but returns empty, zero-initialized structs, discarding trading-state, trade, auction and imbalance information. Fixed-size payload reads are unchecked; declared-length checks use debug-only assertions (`Parser.h:33–40`; `utils.h:77–89`). Unknown types terminate parsing. Replacement adds the new order without removing the old reference (`OrderBookAggregate.h:188–198`), leaving stale pool state.
- **Output defects:** CSV header has an extra empty column (`OrderBookAggregate.h:28–32`); rows do not. Prices truncate four-decimal ITCH precision to cents (`:59–73`). Timestamp output contains time-of-day only (`:37–47`), requiring date/timezone provenance.
- **Samples:** `data/` contains only `.gitignore`; downloader references external 2018–2020 Nasdaq/BX/PSX feeds (`data_pull.py:26–52`). No checked-in fixture or tests establish correctness.
- **Icarus fit:** current depth lane uses GLBX.MDP3/NQ MBP-10 (`Icarus-engine/cl_lab/feeds/databento_depth_sweep.py:35`), unlike Nasdaq equity ITCH. Research projection expects minute features, not these snapshots (`tools/databento_depth_research_context.py:28–33`). No drop-in adapter.
- **License evidence:** no LICENSE/COPYING/NOTICE file or license/SPDX/copyright declaration found in inspected source tree; README names upstream clonemasterUwU while origin names reppiks490. Public availability establishes no reuse grant.

**Next action:** obtain explicit licensing, then independently validate synthetic ITCH lifecycle/truncation fixtures and lossless export before designing a provenance-bearing equity research adapter.
