# Grok (xAI) — 2026-09-22. Whole file. Slot 0 baseline. Features from spec.FEATURE_KEYS.
from __future__ import annotations
import math
from icarus_engine.spec import FEATURE_KEYS

KEYS = FEATURE_KEYS

def _raw(row, keys=KEYS):
    x = row["x"]
    return [float(x.get(k) or 0.0) for k in keys]

def _stats(rows, keys=KEYS):
    n = len(rows); dim = len(keys)
    mu = [0.0] * dim
    for row in rows:
        v = _raw(row, keys)
        for j in range(dim):
            mu[j] += v[j]
    mu = [m / n for m in mu]
    var = [0.0] * dim
    for row in rows:
        v = _raw(row, keys)
        for j in range(dim):
            d = v[j] - mu[j]
            var[j] += d * d
    sd = [math.sqrt(v / n) if v > 0 else 1.0 for v in var]
    return [s if s > 1e-12 else 1.0 for s in sd], mu

def _vec(row, mu, sd, keys=KEYS):
    v = _raw(row, keys)
    return [1.0] + [(v[j] - mu[j]) / sd[j] for j in range(len(keys))]

def _dot(w, x):
    return sum(a * b for a, b in zip(w, x))

def _sig(z):
    if z >= 20: return 1.0
    if z <= -20: return 0.0
    return 1.0 / (1.0 + math.exp(-z))

def fit(rows, steps=120, lr=0.08, l2=0.02):
    if len(rows) < 20:
        raise ValueError("fit needs >=20 labeled rows")
    sd, mu = _stats(rows)
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
    return {"w": w, "mu": mu, "sd": sd, "features": list(KEYS), "slot": "logit"}

def predict_sign(model, row):
    x = _vec(row, model["mu"], model["sd"], model.get("features", KEYS))
    p = _sig(_dot(model["w"], x))
    return (1 if p >= 0.5 else -1), p

def accuracy(model, rows):
    if not rows:
        return None
    return sum(1 for r in rows if predict_sign(model, r)[0] == r["y"]) / len(rows)

# Claude (Opus 5.5) 2026-09-27. The 120-step gradient fit above stops well short of the optimum, which makes it
# a weak baseline. fit_newton solves the same ridge-penalised logistic problem by Newton's method (IRLS) to
# convergence; it is deterministic, so validators can replay it exactly.
def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-18:
            raise ValueError("singular Hessian")
        M[c], M[piv] = M[piv], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            if f:
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x

def fit_newton(rows, keys=KEYS, l2=0.02, iters=100, tol=1e-10):
    if len(rows) < 20:
        raise ValueError("fit needs >=20 labeled rows")
    sd, mu = _stats(rows, keys)
    X = [_vec(r, mu, sd, keys) for r in rows]
    Y = [1.0 if r["y"] > 0 else 0.0 for r in rows]
    n, d = len(X), len(X[0])
    w = [0.0] * d
    for _ in range(iters):
        g = [0.0] * d
        H = [[0.0] * d for _ in range(d)]
        for x, y in zip(X, Y):
            p = _sig(_dot(w, x))
            e, s = p - y, p * (1.0 - p)
            for a in range(d):
                g[a] += e * x[a]
                sa = s * x[a]
                Ha = H[a]
                for b in range(a, d):
                    Ha[b] += sa * x[b]
        for a in range(d):
            for b in range(a):
                H[a][b] = H[b][a]
            g[a] /= n
            H[a] = [v / n for v in H[a]]
        for a in range(d):
            pen = l2 if a else 1e-9          # intercept unpenalised, kept invertible
            g[a] += pen * w[a]
            H[a][a] += pen
        step = _solve(H, g)
        w = [wi - si for wi, si in zip(w, step)]
        if max(abs(si) for si in step) < tol:
            break
    return {"w": w, "mu": mu, "sd": sd, "features": list(keys), "slot": "logit", "fit": "newton"}
