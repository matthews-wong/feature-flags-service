"""Tiny Python client SDK wrapping the /evaluate endpoint.

Deliberately minimal: one class, two methods. It speaks to a running service
over HTTP using ``httpx`` (already a dependency via Starlette's TestClient),
so there are no extra runtime requirements.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import httpx


class FeatureFlagsClient:
    """Client for the feature-flags REST API.

    Example:
        client = FeatureFlagsClient("http://localhost:8000")
        if client.is_enabled("new-checkout", user="user-123", country="DE"):
            ...
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def evaluate(
        self, flag: str, user: str, attributes: Optional[Mapping[str, Any]] = None
    ) -> dict:
        """Return the full evaluation response for a flag/user pair."""
        resp = self._client.post(
            "/evaluate",
            json={"flag": flag, "user": user, "attributes": dict(attributes or {})},
        )
        resp.raise_for_status()
        return resp.json()

    def is_enabled(
        self, flag: str, user: str, **attributes: Any
    ) -> bool:
        """Return whether ``flag`` is ON for ``user``.

        Extra keyword arguments are passed as targeting attributes, e.g.
        ``is_enabled("beta", user="u1", plan="pro")``.
        """
        return bool(self.evaluate(flag, user, attributes).get("enabled", False))

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "FeatureFlagsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
