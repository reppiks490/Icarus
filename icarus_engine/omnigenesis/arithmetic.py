"""Exact number theory and discrete first-passage primitives.

The user's prime-successor expression is the conceptual reference: the product
of nondivisibility tests stays 1 until a prime appears. Runtime evaluation uses
trial division rather than materializing n! or its factorial-sized sum.
"""
from __future__ import annotations

from math import isqrt
from typing import Sequence


def floor_divides(x: int, k: int) -> int:
    """floor(x/k)-floor((x-1)/k), exactly 1 iff k divides x."""
    if not isinstance(x, int) or isinstance(x, bool):
        raise TypeError("x must be an integer")
    if not isinstance(k, int) or isinstance(k, bool) or k < 2:
        raise ValueError("k must be an integer >= 2")
    return x // k - (x - 1) // k


def _prime(candidate: int) -> bool:
    if candidate < 2:
        return False
    if candidate == 2:
        return True
    if candidate % 2 == 0:
        return False
    for divisor in range(3, isqrt(candidate) + 1, 2):
        if candidate % divisor == 0:
            return False
    return True


def next_prime(n: int) -> int:
    """Exact least prime > n for positive integers. No factorial allocated."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be a positive integer")
    candidate = n + 1
    while not _prime(candidate):
        candidate += 1
    return candidate


def first_event_offset(flags: Sequence[bool], horizon: int) -> int:
    """First positive offset with an event, or horizon+1 if none.

    The no-event sentinel is not an event. Evaluate only *observed* flags; this
    function is used to label completed historical windows, not as foresight.
    """
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    if len(flags) < horizon:
        raise ValueError("incomplete event horizon")
    for i in range(horizon):
        if type(flags[i]) is not bool:
            raise ValueError("event flags must be strictly boolean")
        if flags[i]:
            return i + 1
    return horizon + 1
