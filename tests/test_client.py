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
