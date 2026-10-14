# ICARUS Worlds

Three original anime visual worlds integrated into the engine dashboard's existing Style menu:

- **Divine Ascension:** obsidian and gold (with the original pearl palette available), a winged sun and a floating citadel; “The one above all.”
- **Crimson Void:** black-to-red eclipse, obsidian architecture and embers; “Market Destroyer.”
- **Astral Dreamscape:** sapphire observatory, violet sky and star fields; “Beyond the horizon.”

These names, titles, guardian figures and animations are decorative identity, never performance or live-state claims.

## Controls

Open **Style → Theme**, or use the three buttons in the scenic header. Existing stored themes remain selected. Fresh browser profiles default to Divine Ascension. All original palettes remain available.

**Atmosphere** offers Cinematic (default), Balanced (static scenery) and Focus (scenery hidden). **Focus** in the header immediately toggles scenery and restores the previous atmosphere. Accent and density settings persist in browser storage; the appearance module retains its preferences in memory if writes are unavailable. Four accents and two densities are available. Scene scale offers Compact, Grand (default), and Panorama. Lighting selects dark Obsidian (default) or the original palette; only Divine needs a separate dark palette. **Visual detail** offers Adaptive (default), Rich and Light. Adaptive uses Light below 640 scene pixels and reduces detail after sustained slow frames. Light removes the GPU layer, reduces geometry/particles and caps particle canvas DPR at 1. Rich retains the higher detail. Existing Music controls remain intact. Celestial sound is separately opt-in, resets to off on reload, and follows the scene motion gates. It uses locally synthesized wind and a short tonal chord, without downloaded audio.

The cinematic scene adds the original **Eclipse Loom**: projected glass petals and vaulted arches around a luminous crystal in Divine; red accretion strands and an opaque eclipse in Void; a connected spherical star atlas with a helical meridian in Astral. Geometric orbits, light ribbons and curved spark trajectories unite the three. World-specific cycles remain independent of markets: Divine uses a 24-second unfolding form, Void a 16-second accretion cycle, and Astral a 30-second star atlas. It retains the bounded particle system, eased pointer parallax and slow light shafts. CSS perspective rings serve as the canvas-unavailable fallback. Each world has its own particle behavior. Canvas work stops when offscreen, hidden, in Focus/Balanced mode, during the intro, or with reduced motion. Particle count is capped at 70 (35 below 600px), device pixel ratio at 1.5, and redraws at approximately 30fps. This combines software-projected 3D geometry, optional WebGL atmospheric shading, 2D particles and CSS transforms; it is not a model viewer. The atmospheric shader draws at most about 15fps into at most 900×480 pixels, with no external dependency. Canvas2D continues if WebGL is unavailable or its context is lost; a restored context rebuilds its shaders and buffers. Component edges slowly change illumination, panel/headings enter once per view transition, and newly loaded charts fade in once per symbol per view. Chart geometry, prices and labels are never interpolated or distorted. Polling does not replay these entrances.

## Opening sequence

The default 20-second opening assembles the glass mechanism, folds it into an eclipse, then reveals the original orbital crest, wings and ICARUS title. A 12-second option remains under Style → Opening. The timer and all animation timelines use the selected duration. It plays once per browser-tab session. **Skip intro**, **Escape**, and **Style → Replay cinematic intro** are supported. Focus mode skips automatic opening. System reduced motion or No motion suppresses the introduction. Hidden tabs close it. Storage-blocked sessions skip auto-opening instead of repeating it.

The intro traps focus on Skip while open, makes existing background nodes inert, restores their previous inert values and returns focus on exit. It never delays engine startup, polling or market processing; it does temporarily cover the dashboard until skipped or completed. There is no simulated loading/progress meter.

## Integration and boundaries

- `experience-ui.js`: appearance controls, saved preferences, scenic header.
- `experience-ui.css`: scoped theme variables, component finishes, responsive layout, scene and intro animations.
- `world-motion.js`: shared scene lifecycle and separate bounded intro loop, no fetch or admin requests.
- `world-cinema.js`: original world-specific geometry, opt-in synthesis, pointer-follow panel lighting and cancelable word/panel/chart transitions.
- `world-aura.js`: optional same-origin WebGL atmosphere, context recovery and resource lifecycle.
- `server.py`: exact allowlist of three same-origin WebP files and the local presentation JS resources.
- `pyproject.toml`: includes scenery in installed Python packages.

No new runtime dependency, remote font, third-party embed, API key or external asset request. Strategy, execution, market data, scheduler and chart calculations are unchanged. Existing positive/negative/warning semantics are retained. The three images total less than 1 MB.

The bridge dashboard is a distinct application and is not restyled by this change. The running engine installation must receive the merged version and restart before serving it. A refresh alone cannot install repository changes.

## Validation

- `python -m pytest tests_engine/test_dashboard_js.py tests_engine/test_world_assets.py tests_engine/test_world_cinema.py`
- `python -m pip wheel . --no-deps --no-build-isolation -w /tmp/icarus-wheels`
- Optional Chromium check: install Playwright separately, start an empty Portfolio preview on localhost:8879, then run `node tests_engine/browser_worlds.cjs` , `node tests_engine/browser_cinema.cjs`, and `node tests_engine/browser_depth.cjs`. Set `ICARUS_PREVIEW_URL`, `ICARUS_BROWSER_BINARY`, and `ICARUS_BROWSER_OUTPUT` as needed. Do not point the test at a trading session: it changes browser appearance preferences.

The browser check exercises switching, persistence, focus, legacy themes, reduced motion, replay, skip, natural completion, background focus restoration, mobile overflow and System/Inputs/Backtest/Overview navigation. It reports JavaScript errors and any non-GET requests. Preview uses no feed and no trades. Production device performance and Safari still require device-specific validation; no universal “zero errors” claim is made.

Rollback: select an original theme and Focus immediately, or revert this isolated change and restart the installed engine.

## Eclipse Loom verification handoff

Base revision: `c4f2f4b27db8e086aa9a93e3cc0f6f6bc536aa98`. Scope: presentation only. The requested anime/combat examples were explicitly a baseline; no warriors, combat choreography, borrowed characters, anime footage or copied symbols ship in this implementation. Existing approved world artwork is preserved.

Test oracle: browser behavior and canvas geometry invariants, partially independent of implementation. Negative controls include canvas returning null, No Motion, Reduced Motion, Focus/Balanced, disabled audio, repeated chart callbacks and zero-sized canvases. The geometry recorder rejects nonfinite coordinates and external access. Browser checks assert no non-GET requests and unchanged SVG markup during chart entrance. These tests are UI evidence, not evidence of market performance.

Local validation: 64 focused Python/Node tests passed; Chromium behavior checks passed with zero page errors and zero non-GET requests. The actual 20-second opening and original controls are also exercised separately. Safari and production device frame rates remain unverified. This package does not update or restart the user's local installation.

## Depth pass verification handoff

Base: `6d65a4ca977f490540a5daf9b5dabe55329d919c`. This pass adds distinct geometry and timing per world, pointer-responsive camera and panel lighting, animated title words, an iris transition that cleans up after rapid switching, and three timed intro chapter captions. The scene's artwork remains unchanged. Financial text, SVG geometry and values stay untouched.

The optional atmosphere has a bounded shader workload and uses the existing scene scheduler. `Light`, Focus, Balanced, hidden/offscreen state, No Motion and Reduced Motion retain their control over rendering. Shader failure or unavailable WebGL leaves the existing 2D scene usable. There are no paid services, external asset downloads, new market requests or order paths.

Verification includes finite projected coordinates in both detail levels, actual Chromium shader compilation, context loss/restore, no-WebGL fallback, sustained slow-frame injection, rapid transitions, accessible title updates under No Motion, and mobile detail selection. Tests remain presentation evidence only. Production Safari/GPU performance remains device-specific and unverified.


## Full-dashboard immersion phase II

The selected world now extends beyond the scenic header without changing market semantics. A fixed, low-opacity local world layer and geometric light field sit behind the complete dashboard; scroll depth changes only presentation intensity. The main header remains sticky for long views by avoiding the former 100vh/overflow scroll-container combination.

`world-immersion.js` owns bounded page-level interaction choreography: scroll phase, viewport pointer offsets, one-time panel illumination on viewport entry, and short local light impacts on direct UI interactions. It performs no fetches, writes, trading actions, chart interpolation, or market-state inference. Focus mode, No Motion, system reduced motion, hidden tabs, and Light visual detail suppress or reduce the effects.

Instrument surfaces use layered world-reactive glass with a high-detail backdrop-filter path and an ordinary opaque fallback. Tables, scrollbars, active tabs, cards, assets, groups, status nodes, and modal shells share the selected world's edge light while preserving existing semantic green/red/warning colors.

The optional browser depth check now scrolls a long page to the bottom, verifies the header is still pinned, confirms the immersion runtime reaches the final scroll phase, and captures a lower-page screenshot in addition to world and mobile screenshots.


### Immersion phase III

The continuation adds a desktop depth spine with four scroll chapters, view identity, faceted instrument bevels, restrained pointer perspective, per-instrument click responses, and world-specific lower-dashboard architectural grammar. Divine uses ordered radial/architectural light, Void uses fractured/dashed geometry, and Astral uses orbital/star-field geometry; these differences are decorative and never inferred from market state.

The opening is now a four-act local cinematic. A perspective vault, aperture, horizon flare, world-specific glyph field, and world-specific chapter copy are layered around the existing projected Eclipse Loom. The WebGL aura also gains separate analytic spatial fields per world while retaining the same low-power context, internal 15 fps cap, bounded render size, adaptive Light fallback, context-loss recovery, and no-network/no-market boundaries. Panel perspective stays below one degree and is removed immediately when pointer motion stops or motion is disabled.
