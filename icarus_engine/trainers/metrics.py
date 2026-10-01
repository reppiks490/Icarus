# Claude (Opus 5.5) — 2026-09-27. Holdout metrics shared by every slot and every validator.
from __future__ import annotations
import math

ALPHA = 0.05      # one-sided significance a challenger needs against each baseline
_EPS = 1e-15

def row_loss(p, y):
    p = min(max(p, _EPS), 1 - _EPS)
    return -math.log(p) if y > 0 else -math.log(1 - p)

def logloss(ps, ys):
    return sum(row_loss(p, y) for p, y in zip(ps, ys)) / len(ps)

def sign_accuracy(ps, ys):
    return sum(1 for p, y in zip(ps, ys) if (1 if p >= 0.5 else -1) == y) / len(ys)

def incremental_status(model_ll, baseline_ll, null_ll):
    return "PASS" if model_ll < baseline_ll and model_ll < null_ll else "FAIL"

def paired_test(d, lag=None):
    """One-sided test that mean(d) < 0 for per-row loss differences (model minus baseline). Rows next to each other
    share features, so the variance of the mean uses Newey-West with the usual lag floor(4 (n/100)^(2/9))."""
    n = len(d)
    mean = sum(d) / n
    lag = int(4 * (n / 100) ** (2 / 9)) if lag is None else lag
    dev = [x - mean for x in d]
    var = sum(v * v for v in dev) / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * sum(dev[t] * dev[t - k] for t in range(k, n)) / n
    se = math.sqrt(max(var, 0.0) / n)
    if se > 0:
        z = mean / se
        p = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    else:                       # every difference equal: the sign of the mean decides
        z, p = None, (0.0 if mean < 0 else 1.0 if mean > 0 else 0.5)
    return {"n": n, "mean": mean, "se": se, "lag": lag, "z": z, "p": p}

def significance(ps, base_ps, null_p, ys, baseline):
    """Paired tests of the model's per-row holdout loss against a baseline's and the constant null's."""
    model = [row_loss(p, y) for p, y in zip(ps, ys)]
    vs_base = paired_test([m - row_loss(b, y) for m, b, y in zip(model, base_ps, ys)])
    vs_null = paired_test([m - row_loss(null_p, y) for m, y in zip(model, ys)])
    return {"method": "paired per-row log loss, one-sided, Newey-West", "alpha": ALPHA,
            f"vs_{baseline}": vs_base, "vs_null": vs_null,
            "significant": vs_base["p"] < ALPHA and vs_null["p"] < ALPHA}
