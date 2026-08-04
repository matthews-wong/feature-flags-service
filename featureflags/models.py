"""Domain models for flags and targeting rules.

These are the single source of truth for the shape of a flag. Both the store
and the evaluation engine depend on them, so the API layer can trust the core.
"""

from __future__ import annotations

from typing import Any, List, Literal

from pydantic import BaseModel, Field

# Supported comparison operators for a targeting rule. Kept deliberately small
# ("simple attribute match") — extend here if a real use case appears (YAGNI).
Operator = Literal["eq", "neq", "in", "contains"]


class Rule(BaseModel):
    """A single targeting rule matched against a user's attributes.

    A rule is a positive match: when it evaluates true for the supplied
    attributes, the flag is considered ON for that user regardless of the
    percentage rollout.
    """

    attribute: str = Field(..., description="Attribute key to read from the user context.")
    operator: Operator = Field("eq", description="How to compare the attribute value.")
    value: Any = Field(..., description="Expected value (a list for the 'in' operator).")


class Flag(BaseModel):
    """A feature flag.

    Evaluation precedence (see engine.evaluate):
      1. If ``enabled`` is False the flag is OFF for everyone (kill switch).
      2. If any targeting rule matches, the flag is ON.
      3. Otherwise the user is bucketed by ``rollout_percentage``.
    """

    key: str = Field(..., description="Unique, stable flag identifier.")
    enabled: bool = Field(True, description="Master on/off switch for the flag.")
    rollout_percentage: int = Field(
        100,
        ge=0,
        le=100,
        description="Percentage of non-targeted users the flag is ON for.",
    )
    rules: List[Rule] = Field(default_factory=list, description="Targeting rules (OR-ed).")
    description: str = Field("", description="Human-readable purpose of the flag.")


class EvaluationRequest(BaseModel):
    """Request body for POST /evaluate."""

    flag: str = Field(..., description="Flag key to evaluate.")
    user: str = Field(..., description="Stable user identifier used for bucketing.")
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="User attributes for targeting rules."
    )


class EvaluationResponse(BaseModel):
    """Result of evaluating a flag for a user."""

    flag: str
    user: str
    enabled: bool
    reason: str = Field(..., description="Which rule decided the outcome.")
