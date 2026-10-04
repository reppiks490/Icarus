# ICARUS Worlds

Three original anime visual worlds integrated into the engine dashboard's existing Style menu:

- **Divine Ascension:** pearl, gold, a winged sun and a floating citadel; “The one above all.”
- **Crimson Void:** black-to-red eclipse, obsidian architecture and embers; “Market Destroyer.”
- **Astral Dreamscape:** sapphire observatory, violet sky and star fields; “Beyond the horizon.”

These names, titles, guardian figures and animations are decorative identity, never performance or live-state claims.

## Controls

Open **Style → Theme**, or use the three buttons in the scenic header. Existing stored themes remain selected. Fresh browser profiles default to Divine Ascension. All original palettes remain available.

**Atmosphere** offers Cinematic (default), Balanced (static scenery) and Focus (scenery hidden). **Focus** in the header immediately toggles scenery and restores the previous atmosphere. Accent and density settings persist in browser storage; the appearance module retains its preferences in memory if writes are unavailable. Four accents and two densities are available. Existing Music controls remain intact; no automatic audio is added.

The cinematic scene uses a bounded canvas particle system, CSS perspective orbital rings, eased pointer parallax and slow light shafts. Each world has its own particle behavior. Canvas work stops when offscreen, hidden, in Focus/Balanced mode, during the intro, or with reduced motion. Particle count is capped at 70 (35 below 600px), device pixel ratio at 1.5, and redraws at approximately 30fps. This is a layered 2D/3D-transform presentation, not a WebGL model viewer.

## Opening sequence

A 12-second sequence assembles an eclipse, rotating orbital rings, unfolding wings and a custom crown crest, then reveals the ICARUS title over the selected world. It plays once per browser-tab session. **Skip intro**, **Escape**, and **Style → Replay cinematic intro** are supported. Focus mode skips automatic opening. System reduced motion or No motion suppresses the introduction. Hidden tabs close it. Storage-blocked sessions skip auto-opening instead of repeating it.

The intro traps focus on Skip while open, makes existing background nodes inert, restores their previous inert values and returns focus on exit. It never delays engine startup, polling or market processing; it does temporarily cover the dashboard until skipped or completed. There is no simulated loading/progress meter.

## Integration and boundaries

- `experience-ui.js`: appearance controls, saved preferences, scenic header.
- `experience-ui.css`: scoped theme variables, component finishes, responsive layout, scene and intro animations.
- `world-motion.js`: independent presentation runtime, no fetch or admin requests.
- `server.py`: exact allowlist of three same-origin WebP files and one JS resource.
- `pyproject.toml`: includes scenery in installed Python packages.

No new runtime dependency, remote font, third-party embed, API key or external asset request. Strategy, execution, market data, scheduler and chart calculations are unchanged. Existing positive/negative/warning semantics are retained. The three images total less than 1 MB.

The bridge dashboard is a distinct application and is not restyled by this change. The running engine installation must receive the merged version and restart before serving it. A refresh alone cannot install repository changes.

## Validation

- `python -m pytest tests_engine/test_dashboard_js.py tests_engine/test_world_assets.py`
- `python -m pip wheel . --no-deps --no-build-isolation -w /tmp/icarus-wheels`
- Optional Chromium check: install Playwright separately, start an empty Portfolio preview on localhost:8879, then run `node tests_engine/browser_worlds.cjs`. Set `ICARUS_PREVIEW_URL`, `ICARUS_BROWSER_BINARY`, and `ICARUS_BROWSER_OUTPUT` as needed. Do not point the test at a trading session: it changes browser appearance preferences.

The browser check exercises switching, persistence, focus, legacy themes, reduced motion, replay, skip, natural completion, background focus restoration, mobile overflow and System/Inputs/Backtest/Overview navigation. It reports JavaScript errors and any non-GET requests. Preview uses no feed and no trades. Production device performance and Safari still require device-specific validation; no universal “zero errors” claim is made.

Rollback: select an original theme and Focus immediately, or revert this isolated change and restart the installed engine.
