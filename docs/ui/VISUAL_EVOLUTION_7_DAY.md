# ICARUS Visual Evolution — Seven-Day Continuation Contract

This document is an implementation contract for the UI-only visual evolution lane. It does not authorize changes to trading, strategy, execution, broker, market-data, scheduler, risk, or research semantics.

## North star

The dashboard should feel like one continuous world rather than a decorated hero followed by ordinary application chrome. Scrolling, navigation, charts, dense tables, system consoles, controls, and loading transitions should share one spatial/material language while financial data stays literal and readable.

## Landed in the current visual lane

- ICARUS Worlds with Divine / Void / Astral world identity.
- Eclipse Loom projected geometry and bounded WebGL aura.
- Four-act opening vault, aperture, horizon, world glyph field and world-specific copy.
- Full-page world atmosphere with scroll depth and pointer parallax.
- Long-scroll sticky-shell repair.
- Native view transitions.
- Desktop four-stage depth spine and current-view identity.
- Scroll-direction / velocity edge energy.
- Faceted and prismatic instrument glass.
- Pointer-responsive panel perspective below one degree.
- Specialized subsystem skin for Brain, Evolution, PARALLAX, PANTHEON, Ψ and related consoles.
- World-specific lower-dashboard architecture rather than palette-only variants.
- Instrument-specific click responses.
- Overlay-only first-load chart scan; plotted SVG geometry stays unchanged.
- Sticky glass table headers, world-aware inputs, logs, scrollbars and metric tiles.
- Focus / Light / No Motion / Reduced Motion / High Contrast fallbacks.
- Presentation-only I/O guard for the immersion runtime.

## Next-pass priorities

### 1. Motion grammar, not random animation
Build a reusable choreography vocabulary and apply it consistently:
- arrival
- reveal
- focus
- selection
- confirmation
- warning
- world transition
- view transition
- chart arrival
- long-scroll chapter crossing

No polling-only event may masquerade as market activity.

### 2. Deep chart presentation
Without changing plotted values or geometry:
- refine chart framing and edge light
- improve tooltip material
- add crosshair/hover optics
- coordinate chart entrance with surrounding card entrance
- protect legibility at dense candle counts
- retain exact SVG before/after invariants

### 3. Specialized-console convergence
Audit every UI module for hard-coded local styling. Replace isolated aesthetic islands with world-aware variables while preserving semantic success/warn/error colors.

Priority namespaces:
- brain-*
- px-*
- psi-*
- pan-*
- evo-*
- commissioning / integrity / engine-control / learning / chronofold / APEX / ASCENDANCY

### 4. Mobile and narrow-screen cinema
Mobile must feel intentionally composed, not merely reduced:
- keep touch responses
- avoid hover-only dependencies
- maintain zero horizontal overflow
- simplify depth geometry automatically
- keep intro framing centered on 390x844-class displays
- ensure tabs and settings remain usable

### 5. Performance budget
Rich visuals may never destabilize the trading UI.
- 2D scene remains bounded near 30 fps.
- GPU aura remains independently bounded near 15 fps.
- Rich mode may degrade to Light after sustained slow frames.
- Hidden tabs, Focus, Balanced, No Motion and Reduced Motion stop decorative work.
- Avoid unbounded MutationObserver, DOM, canvas, audio, or animation accumulation.
- No remote runtime visual dependency.

### 6. Visual regression evidence
For every substantial pass, preserve or extend screenshots for:
- Divine
- Void
- Astral
- lower-page / long-scroll
- mobile
- opening sequence
- at least one dense subsystem view

Verify:
- no page errors
- no unexpected non-GET requests from visual tests
- no horizontal overflow
- sticky header remains pinned
- no stale transition veils
- no geometry mutation in chart presentation
- reduced-motion path is static
- no-WebGL path remains usable

### 7. Material quality
Continue replacing flat translucency with constructed surfaces:
- bevel hierarchy
- directional specular response
- subtle world-specific refraction
- nested surface depth
- table/form material consistency
- modal and palette consistency

Do not reduce the UI to a generic glassmorphism template.

## Acceptance boundary

A visual pass is not complete merely because CSS changed. It should leave:
1. a concrete visible improvement,
2. a regression or invariant test where practical,
3. performance/motion gates intact,
4. no trading-semantic diff,
5. auditable GitHub evidence.

The seven-day lane should keep iterating from the current repository head rather than restarting the aesthetic system.


## Structural depth pass

The world frame now includes a bounded structural constellation generated only from the current dashboard layout. It connects at most 18 major instrument surfaces with at most 24 decorative paths, uses no market values, performs no network I/O, and exists solely to make the dashboard read as one constructed system rather than isolated cards. The nearest visible instrument becomes a subtle scroll anchor, and pointer/focus interaction temporarily brightens its local links.

The last four visited dashboard chambers also remain visible as an in-memory navigation trail. This history is session-only, never persisted, and does not change application state. It exists to make deliberate navigation feel continuous while preserving the current tab, command, and hash contracts.

Guardrails for this layer:
- hidden on narrow/mobile layouts;
- hidden in Focus and Light rendering;
- animation removed for reduced-motion users;
- path/node budgets are hard-bounded;
- no semantic or trading data is encoded in link geometry;
- no layout element may be shifted by the decorative SVG.
