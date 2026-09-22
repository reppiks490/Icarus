# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import math
KEYS = ("ret_1", "ret_3", "body", "range", "close_loc", "tide", "run")

def _vec(row):
    x = row["x"]
    return [1.0] + [float(x.get(k) or 0.0) for k in KEYS]

def _dot(w, x):
    return sum(a * b for a, b in zip(w, x))

def _sig(z):
    if z >= 20: return 1.0
    if z <= -20: return 0.0
    return 1.0 / (1.0 + math.exp(-z))

def fit(rows, steps=80, lr=0.05, l2=0.01):
    if len(rows) < 20:
        raise ValueError("fit needs >=20 labeled rows")
    dim = 1 + len(KEYS)
    w = [0.0] * dim
    for _ in range(steps):
        grad = [0.0] * dim
        for row in rows:
            x = _vec(row)
            y = 1.0 if row["y"] > 0 else 0.0
            p = _sig(_dot(w, x))
            err = p - y
            for j in range(dim):
                grad[j] += err * x[j]
        n = len(rows)
        for j in range(dim):
            w[j] -= lr * (grad[j] / n + l2 * w[j])
    return w

def predict_sign(w, row):
    p = _sig(_dot(w, _vec(row)))
    return (1 if p >= 0.5 else -1), p

def accuracy(w, rows):
    if not rows:
        return None
    return sum(1 for r in rows if predict_sign(w, r)[0] == r["y"]) / len(rows)
