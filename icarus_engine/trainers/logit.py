# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import math
KEYS = ("ret_1", "ret_3", "body", "range", "close_loc", "tide", "run", "fomc", "any_macro")

def _raw(row):
    x = row["x"]
    return [float(x.get(k) or 0.0) for k in KEYS]

def _stats(rows):
    n = len(rows); dim = len(KEYS)
    mu = [0.0] * dim
    for row in rows:
        v = _raw(row)
        for j in range(dim):
            mu[j] += v[j]
    mu = [m / n for m in mu]
    var = [0.0] * dim
    for row in rows:
        v = _raw(row)
        for j in range(dim):
            d = v[j] - mu[j]
            var[j] += d * d
    sd = [math.sqrt(v / n) if v > 0 else 1.0 for v in var]
    sd = [s if s > 1e-12 else 1.0 for s in sd]
    return mu, sd

def _vec(row, mu, sd):
    v = _raw(row)
    return [1.0] + [(v[j] - mu[j]) / sd[j] for j in range(len(KEYS))]

def _dot(w, x):
    return sum(a * b for a, b in zip(w, x))

def _sig(z):
    if z >= 20: return 1.0
    if z <= -20: return 0.0
    return 1.0 / (1.0 + math.exp(-z))

def fit(rows, steps=120, lr=0.08, l2=0.02):
    if len(rows) < 20:
        raise ValueError("fit needs >=20 labeled rows")
    mu, sd = _stats(rows)
    dim = 1 + len(KEYS)
    w = [0.0] * dim
    for _ in range(steps):
        grad = [0.0] * dim
        for row in rows:
            x = _vec(row, mu, sd)
            y = 1.0 if row["y"] > 0 else 0.0
            p = _sig(_dot(w, x))
            err = p - y
            for j in range(dim):
                grad[j] += err * x[j]
        n = len(rows)
        for j in range(dim):
            w[j] -= lr * (grad[j] / n + l2 * w[j])
    return {"w": w, "mu": mu, "sd": sd}

def predict_sign(model, row):
    x = _vec(row, model["mu"], model["sd"])
    p = _sig(_dot(model["w"], x))
    return (1 if p >= 0.5 else -1), p

def accuracy(model, rows):
    if not rows:
        return None
    return sum(1 for r in rows if predict_sign(model, r)[0] == r["y"]) / len(rows)
