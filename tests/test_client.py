"""SDK tests: drive the client against an in-memory app via a mounted transport."""

import pytest
from fastapi.testclient import TestClient

from featureflags.client import FeatureFlagsClient
from featureflags.main import create_app
from featureflags.store import FlagStore


@pytest.fixture()
def sdk():
    """A FeatureFlagsClient whose HTTP calls are routed into the ASGI app.

    Starlette's TestClient is a synchronous httpx.Client bound to the ASGI app,
    so we swap it in as the SDK's transport — the client exercises real request
    serialization with no network or running server.
    """
    app = create_app(FlagStore())
    test_client = TestClient(app)
    # Seed a flag directly through the API.
    test_client.put(
        "/flags/beta",
        json={
            "key": "beta",
            "enabled": True,
            "rollout_percentage": 0,
            "rules": [{"attribute": "plan", "operator": "eq", "value": "pro"}],
        },
    )

    client = FeatureFlagsClient("http://testserver")
    client._client = test_client
    yield client
    client.close()


def test_sdk_is_enabled_true_for_targeted_user(sdk):
    assert sdk.is_enabled("beta", user="u1", plan="pro") is True


def test_sdk_is_enabled_false_for_untargeted_user(sdk):
    assert sdk.is_enabled("beta", user="u1", plan="free") is False


def test_sdk_evaluate_returns_full_payload(sdk):
    result = sdk.evaluate("beta", user="u1", attributes={"plan": "pro"})
    assert result["flag"] == "beta"
    assert result["enabled"] is True
    assert result["reason"] == "targeting"


def test_sdk_is_enabled_unknown_flag_fails_safe_to_default(sdk):
    """An unknown flag (or an unreachable service) must not raise.

    A feature-flag SDK exists so that flag-plane problems degrade gracefully:
    a typo'd or not-yet-created flag should behave as "feature off", never
    crash the calling code path. The default is overridable per call.
    """
    assert sdk.is_enabled("never-created", user="u1") is False
    assert sdk.is_enabled("never-created", user="u1", default=True) is True
