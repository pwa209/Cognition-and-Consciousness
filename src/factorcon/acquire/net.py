"""HTTP helpers with bounded retries and explicit user-agent identification."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

from factorcon.errors import SourceError

USER_AGENT = "factorcon/0.1 (+https://github.com/pwa209/Cognition-and-Consciousness)"


def request_bytes(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
    attempts: int = 5,
) -> tuple[bytes, dict[str, str], int]:
    """Request bytes with exponential backoff for transient HTTP/network failures."""

    merged = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    merged.update(headers or {})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, data=data, headers=merged, method=method)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), dict(response.headers.items()), int(response.status)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(min(30.0, (2**attempt) + random.random()))
    raise SourceError(f"Request failed after {attempts} attempts: {url}: {last_error}")


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 180,
    attempts: int = 5,
) -> dict[str, Any]:
    """Request and decode a JSON object."""

    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    body, _, _ = request_bytes(
        url, method=method, data=data, headers=headers, timeout=timeout, attempts=attempts
    )
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceError(f"Source did not return JSON: {url}") from exc
    if not isinstance(value, dict):
        raise SourceError(f"Expected a JSON object from {url}")
    return value
