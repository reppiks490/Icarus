from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED = "***"
DEFAULT_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "key",
        "token",
        "access_token",
        "access-token",
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "x-auth-token",
        "client_secret",
        "client-secret",
        "secret",
        "password",
    }
)


def normalized_secret_keys(secret_keys: Iterable[str] = ()) -> frozenset[str]:
    return frozenset({key.strip().lower() for key in secret_keys if key and key.strip()}) | DEFAULT_SECRET_KEYS


def redact_url(url: str, secret_keys: Iterable[str] = ()) -> str:
    """Return *url* with values for named secret query parameters masked."""

    keys = normalized_secret_keys(secret_keys)
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, REDACTED if key.lower() in keys else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment))


def redact_headers(headers: Mapping[str, str], secret_keys: Iterable[str] = ()) -> dict[str, str]:
    keys = normalized_secret_keys(secret_keys)
    return {key: (REDACTED if key.lower() in keys else value) for key, value in headers.items()}


def secret_values(
    url: str,
    headers: Mapping[str, str],
    secret_keys: Iterable[str] = (),
) -> tuple[str, ...]:
    """Extract only values whose names are explicitly sensitive.

    Token components are included so an exception containing ``Bearer <token>`` or
    the bare token is scrubbed either way. Values are sorted longest-first to avoid
    partial replacement leaving a suffix behind.
    """

    keys = normalized_secret_keys(secret_keys)
    values: set[str] = set()
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if key.lower() in keys and value:
            values.add(value)
            values.update(piece for piece in value.split() if len(piece) >= 4)
    for key, value in headers.items():
        if key.lower() in keys and value:
            values.add(value)
            values.update(piece for piece in value.split() if len(piece) >= 4)
    return tuple(sorted(values, key=len, reverse=True))


def redact_text(text: str, values: Iterable[str], replacement: str = REDACTED) -> str:
    rendered = str(text)
    for value in sorted({value for value in values if value}, key=len, reverse=True):
        rendered = rendered.replace(value, replacement)
    return rendered
