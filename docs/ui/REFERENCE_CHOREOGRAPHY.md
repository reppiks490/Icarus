# Cinematic material and motion

The October 13 animation reference uses large curved surfaces enclosing a cosmic
opening, continuous grazing rims, perspective-following surface markings,
independent cloud/light/foreground movement and staged light reveals. The shipped
choreography uses original procedural geometry and materials to bring that
visual language to ICARUS's three worlds and opening.

The reference study covered the complete 22.84-second container timeline. The MOV
declares 640 frames; decoding enumerated 639 pictures, with the last at 22.780 seconds.
All decoded frames were inspected in chronological sheets by the review team;
the implementer additionally examined six time-labelled 6 Hz sequences across
the full timeline. Sampling a few stills alone was inadequate and was corrected
before implementation. Original footage, audio, extracted frames and temporary
Dropbox links remain outside the public repository.

## Visual structure

- Stable broad dark contours create foreground mass and genuine occlusion.
- White/gold rims, curved normals, staggered enamel markings and local iridescent highlights follow each open quadratic surface.
- Deeper nebula material, dust and light evolve on separate slow trajectories.
- The opening stages ignition, a traverse through folded material and an off-axis celestial reveal.
- The three existing themes retain their visual identity. Dashboard text,
  charts, controls and market-state semantics remain independent of the scenery.

## Integration and lifecycle

`reference-choreography.js` loads after the existing aura and cinema modules and
before world-motion. Its small adapters retain the existing draw/pause/dispose
and cinema APIs. The existing world/intro callbacks provide scheduling; there is
no second requestAnimationFrame loop. Only the two new assets are added to the
server's exact static-asset allowlist. No folder-wide asset route is introduced.

The renderer has one draw pass capped at 960 × 560 pixels and 30 frames per second, with a continuous bounded ambient phase for limited-precision GPUs. It has bounded resolution and honors adaptive/light detail, hidden
and offscreen scenes, no-motion preferences and reduced motion. Unavailable or
lost GPU contexts preserve a usable presentation. Closing the intro releases
its renderer, including Escape and reduced-motion closure. Existing skip,
focus and inert behavior is retained. The opening uses monotonic elapsed presentation
time, so slow frames cannot omit its finale before the existing closing timer.
The caller still owns scheduling and bounded physics updates. Light detail uses
two shaded Canvas2D folds without a GPU draw pass. World buttons receive subtle
hover/press responses and visible keyboard focus, with reduced-motion overrides.

## Verification

Validation uses the real feed-free HTTP asset boundary, collected Node lifecycle
checks, actual Chromium shader compilation/context recovery, desktop/mobile
captures and a complete live opening timeline. Controlled phase captures are labelled
as simulations; a separate natural timeline records actual shader progress. Browser fixtures are labelled
synthetic and intercept outbound requests; they prove presentation behavior,
not live market data or production GPU throughput. Before/after visual review
checks geometry, material depth, readable text and temporal continuity.

This implementation is an original procedural interpretation. Authored anime
character animation and film-production equivalence are not certified by tests.

The final Chromium audit at the reviewed source hashes captured all three themes
and 320/768/1024/1440-pixel layouts with no horizontal overflow or page, console,
shader-compilation or network errors. GPU draws stop for balanced/focus/light,
motion-off, reduced motion, forced colors, offscreen and simulated hidden-document
inputs. The forced-colors check covers this GPU layer; existing Canvas2D motion
continues. Context recovery and three repeated Escape cleanups pass.

The six collected HTTP/lifecycle pytest cases include 23 Node lifecycle cases.
The opening clock regression was demonstrated failing before the correction.
Linux CI collects the new module; the existing explicit Windows suite does not.
Full engine suite and commit-specific CI results belong in the delivery receipt.
