# Claude (Opus 5.5) — 2026-09-27. Isotonic calibration by pool-adjacent-violators. Stdlib, deterministic.
from __future__ import annotations
from bisect import bisect_left

EPS = 1e-6

def isotonic_fit(ps, ys):
    """Non-decreasing step map from score to P(y=1). Tied scores share one block."""
    blocks = []  # [upper score, sum y, weight]
    for p, y in sorted(zip((float(p) for p in ps), (1.0 if y > 0 else 0.0 for y in ys))):
        if blocks and blocks[-1][0] == p:
            blocks[-1][1] += y
            blocks[-1][2] += 1
        else:
            blocks.append([p, y, 1])
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][2] > blocks[-1][1] / blocks[-1][2]:
            last = blocks.pop()
            blocks[-1][0] = last[0]
            blocks[-1][1] += last[1]
            blocks[-1][2] += last[2]
    return {"x": [b[0] for b in blocks], "y": [b[1] / b[2] for b in blocks]}

def isotonic_apply(model, p):
    xs, ys = model["x"], model["y"]
    i = min(bisect_left(xs, float(p)), len(ys) - 1)
    return min(max(ys[i], EPS), 1.0 - EPS)
