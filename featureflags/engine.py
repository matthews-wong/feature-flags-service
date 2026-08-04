"""Flag evaluation engine.

Pure functions only — no IO, no framework types. Given a Flag and a user
context, decide whether the flag is ON. Determinism is the key contract:
the same (flag key, user) pair always lands in the same rollout bucket.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .models import Flag, Rule

# Number of buckets a user can hash into. Percentage is expressed 0-100, so
# 100 buckets maps cleanly: bucket < rollout_percentage => ON.
_BUCKET_COUNT = 100


def bucket_for(flag_key: str, user: str) -> int:
    """Return a stable bucket in [0, 100) for a (flag, user) pair.

    Uses SHA-256 over ``"{flag_key}:{user}"`` so bucketing is deterministic
    across processes and machines (unlike Python's salted ``hash()``). Keying
    on the flag as well means a user is not correlated across different flags.
    """

    digest = hashlib.sha256(f"{flag_key}:{user}".encode("utf-8")).hexdigest()
    return int(digest, 16) % _BUCKET_COUNT


def rule_matches(rule: Rule, attributes: Mapping[str, Any]) -> bool:
    """Return True if a single targeting rule matches the user attributes."""

    if rule.attribute not in attributes:
        return False
    actual = attributes[rule.attribute]

    if rule.operator == "eq":
        return actual == rule.value
    if rule.operator == "neq":
        return actual != rule.value
    if rule.operator == "in":
        # ``value`` is expected to be a collection of allowed values.
        return actual in rule.value
    if rule.operator == "contains":
        # ``actual`` is expected to be a collection/string containing ``value``.
        try:
            return rule.value in actual
        except TypeError:
            return False
    return False


def evaluate(
    flag: Flag, user: str, attributes: Mapping[str, Any] | None = None
) -> tuple[bool, str]:
    """Evaluate a flag for a user, returning (enabled, reason).

    Precedence:
      1. Master switch off  -> (False, "disabled")
      2. Any targeting rule matches -> (True, "targeting")
      3. Percentage bucket   -> (bucket < rollout, "percentage")
    """

    attributes = attributes or {}

    if not flag.enabled:
        return False, "disabled"

    for rule in flag.rules:
        if rule_matches(rule, attributes):
            return True, "targeting"

    if flag.rollout_percentage >= _BUCKET_COUNT:
        return True, "rollout-100"
    if flag.rollout_percentage <= 0:
        return False, "rollout-0"

    hit = bucket_for(flag.key, user) < flag.rollout_percentage
    return hit, "percentage"
