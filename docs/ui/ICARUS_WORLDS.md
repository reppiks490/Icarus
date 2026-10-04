# ICARUS Worlds

Three original anime visual worlds integrated into the engine dashboard's existing Style menu:

- **Divine Ascension:** obsidian and gold (with the original pearl palette available), a winged sun and a floating citadel; “The one above all.”
- **Crimson Void:** black-to-red eclipse, obsidian architecture and embers; “Market Destroyer.”
- **Astral Dreamscape:** sapphire observatory, violet sky and star fields; “Beyond the horizon.”

These names, titles, guardian figures and animations are decorative identity, never performance or live-state claims.

## Controls

Open **Style → Theme**, or use the three buttons in the scenic header. Existing stored themes remain selected. Fresh browser profiles default to Divine Ascension. All original palettes remain available.

**Atmosphere** offers Cinematic (default), Balanced (static scenery) and Focus (scenery hidden). **Focus** in the header immediately toggles scenery and restores the previous atmosphere. Accent and density settings persist in browser storage; the appearance module retains its preferences in memory if writes are unavailable. Four accents and two densities are available. Scene scale offers Compact, Grand (default), and Panorama. Lighting selects dark Obsidian (default) or the original palette; only Divine needs a separate dark palette. Existing Music controls remain intact. Celestial sound is separately opt-in, resets to off on reload, and follows the scene motion gates. It uses locally synthesized wind and a short tonal chord, without downloaded audio.

The cinematic scene adds the original **Eclipse Loom**: 72 depth-sorted projected glass facets, two engraved geometric orbits, a rotating lattice, light ribbons and curved spark trajectories. Its 18-second cycle folds inward and opens again, independently of markets. It retains the bounded particle system, eased pointer parallax and slow light shafts. CSS perspective rings serve as the canvas-unavailable fallback. Each world has its own particle behavior. Canvas work stops when offscreen, hidden, in Focus/Balanced mode, during the intro, or with reduced motion. Particle count is capped at 70 (35 below 600px), device pixel ratio at 1.5, and redraws at approximately 30fps. This combines software-projected 3D geometry, 2D atmosphere and CSS transforms; it is not a WebGL model viewer. Component edges slowly change illumination, panel/headings enter once per view transition, and newly loaded charts fade in once per symbol per view. Chart geometry, prices and labels are never interpolated or distorted. Polling does not replay these entrances.

## Opening sequence

The default 20-second opening assembles the glass mechanism, folds it into an eclipse, then reveals the original orbital crest, wings and ICARUS title. A 12-second option remains under Style → Opening. The timer and all animation timelines use the selected duration. It plays once per browser-tab session. **Skip intro**, **Escape**, and **Style → Replay cinematic intro** are supported. Focus mode skips automatic opening. System reduced motion or No motion suppresses the introduction. Hidden tabs close it. Storage-blocked sessions skip auto-opening instead of repeating it.

The intro traps focus on Skip while open, makes existing background nodes inert, restores their previous inert values and returns focus on exit. It never delays engine startup, polling or market processing; it does temporarily cover the dashboard until skipped or completed. There is no simulated loading/progress meter.

## Integration and boundaries

- `experience-ui.js`: appearance controls, saved preferences, scenic header.
- `experience-ui.css`: scoped theme variables, component finishes, responsive layout, scene and intro animations.
- `world-motion.js`: shared scene lifecycle and separate bounded intro loop, no fetch or admin requests.
- `world-cinema.js`: original projected geometry, opt-in synthesis and cancelable panel/chart entrances.
- `server.py`: exact allowlist of three same-origin WebP files and the local presentation JS resources.
- `pyproject.toml`: includes scenery in installed Python packages.

No new runtime dependency, remote font, third-party embed, API key or external asset request. Strategy, execution, market data, scheduler and chart calculations are unchanged. Existing positive/negative/warning semantics are retained. The three images total less than 1 MB.

The bridge dashboard is a distinct application and is not restyled by this change. The running engine installation must receive the merged version and restart before serving it. A refresh alone cannot install repository changes.

## Validation

- `python -m pytest tests_engine/test_dashboard_js.py tests_engine/test_world_assets.py tests_engine/test_world_cinema.py`
- `python -m pip wheel . --no-deps --no-build-isolation -w /tmp/icarus-wheels`
- Optional Chromium check: install Playwright separately, start an empty Portfolio preview on localhost:8879, then run `node tests_engine/browser_worlds.cjs` and `node tests_engine/browser_cinema.cjs`. Set `ICARUS_PREVIEW_URL`, `ICARUS_BROWSER_BINARY`, and `ICARUS_BROWSER_OUTPUT` as needed. Do not point the test at a trading session: it changes browser appearance preferences.

The browser check exercises switching, persistence, focus, legacy themes, reduced motion, replay, skip, natural completion, background focus restoration, mobile overflow and System/Inputs/Backtest/Overview navigation. It reports JavaScript errors and any non-GET requests. Preview uses no feed and no trades. Production device performance and Safari still require device-specific validation; no universal “zero errors” claim is made.

Rollback: select an original theme and Focus immediately, or revert this isolated change and restart the installed engine.

## Eclipse Loom verification handoff

Base revision: `c4f2f4b27db8e086aa9a93e3cc0f6f6bc536aa98`. Scope: presentation only. The requested anime/combat examples were explicitly a baseline; no warriors, combat choreography, borrowed characters, anime footage or copied symbols ship in this implementation. Existing approved world artwork is preserved.

Test oracle: browser behavior and canvas geometry invariants, partially independent of implementation. Negative controls include canvas returning null, No Motion, Reduced Motion, Focus/Balanced, disabled audio, repeated chart callbacks and zero-sized canvases. The geometry recorder rejects nonfinite coordinates and external access. Browser checks assert no non-GET requests and unchanged SVG markup during chart entrance. These tests are UI evidence, not evidence of market performance.

Local validation: 64 focused Python/Node tests passed; Chromium behavior checks passed with zero page errors and zero non-GET requests. The actual 20-second opening and original controls are also exercised separately. Safari and production device frame rates remain unverified. This package does not update or restart the user's local installation.
