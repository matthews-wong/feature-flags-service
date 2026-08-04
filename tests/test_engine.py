"""Engine unit tests: boolean, percentage stability/distribution, targeting."""

from featureflags.engine import bucket_for, evaluate
from featureflags.models import Flag, Rule


def test_boolean_off_is_disabled_for_everyone():
    flag = Flag(key="f", enabled=False, rollout_percentage=100)
    enabled, reason = evaluate(flag, user="anyone")
    assert enabled is False
    assert reason == "disabled"


def test_boolean_on_full_rollout_is_enabled():
    flag = Flag(key="f", enabled=True, rollout_percentage=100)
    enabled, reason = evaluate(flag, user="anyone")
    assert enabled is True
    assert reason == "rollout-100"


def test_percentage_is_stable_for_a_user():
    flag = Flag(key="checkout", enabled=True, rollout_percentage=50)
    first = evaluate(flag, user="user-42")
    # Repeated evaluations must never flip for the same user.
    for _ in range(100):
        assert evaluate(flag, user="user-42") == first


def test_bucket_is_deterministic_across_calls():
    assert bucket_for("flag-a", "user-1") == bucket_for("flag-a", "user-1")


def test_percentage_distribution_matches_roughly():
    flag = Flag(key="rollout", enabled=True, rollout_percentage=30)
    n = 10_000
    enabled_count = sum(
        1 for i in range(n) if evaluate(flag, user=f"user-{i}")[0]
    )
    ratio = enabled_count / n
    # Hash-based bucketing should land within a couple points of the target.
    assert 0.27 <= ratio <= 0.33


def test_targeting_rule_matches_regardless_of_percentage():
    flag = Flag(
        key="eu",
        enabled=True,
        rollout_percentage=0,
        rules=[Rule(attribute="country", operator="in", value=["DE", "FR"])],
    )
    enabled, reason = evaluate(flag, user="u1", attributes={"country": "DE"})
    assert enabled is True
    assert reason == "targeting"


def test_targeting_rule_miss_falls_through_to_percentage():
    flag = Flag(
        key="eu",
        enabled=True,
        rollout_percentage=0,
        rules=[Rule(attribute="country", operator="in", value=["DE", "FR"])],
    )
    enabled, reason = evaluate(flag, user="u1", attributes={"country": "US"})
    assert enabled is False
    assert reason == "rollout-0"


def test_operators():
    attrs = {"plan": "pro", "tags": ["a", "b"]}
    assert evaluate(
        Flag(key="k", rules=[Rule(attribute="plan", operator="eq", value="pro")]),
        "u", attrs,
    )[0]
    assert evaluate(
        Flag(key="k", rollout_percentage=0,
             rules=[Rule(attribute="plan", operator="neq", value="free")]),
        "u", attrs,
    )[0]
    assert evaluate(
        Flag(key="k", rollout_percentage=0,
             rules=[Rule(attribute="tags", operator="contains", value="a")]),
        "u", attrs,
    )[0]
