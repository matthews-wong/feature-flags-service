"""API tests using FastAPI's TestClient against an in-memory store."""

import pytest
from fastapi.testclient import TestClient

from featureflags.main import create_app
from featureflags.store import FlagStore


@pytest.fixture()
def client():
    app = create_app(FlagStore())  # in-memory, no persistence
    return TestClient(app)


def _put(client, key, **kwargs):
    body = {"key": key, "enabled": True, "rollout_percentage": 100, "rules": []}
    body.update(kwargs)
    return client.put(f"/flags/{key}", json=body)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_crud_lifecycle(client):
    assert client.get("/flags").json() == []

    assert _put(client, "alpha", description="first").status_code == 200
    assert client.get("/flags/alpha").json()["description"] == "first"
    assert len(client.get("/flags").json()) == 1

    # Update in place.
    _put(client, "alpha", enabled=False)
    assert client.get("/flags/alpha").json()["enabled"] is False

    assert client.delete("/flags/alpha").status_code == 204
    assert client.get("/flags/alpha").status_code == 404


def test_put_key_mismatch_is_rejected(client):
    resp = client.put(
        "/flags/alpha",
        json={"key": "beta", "enabled": True, "rollout_percentage": 100},
    )
    assert resp.status_code == 400


def test_evaluate_unknown_flag_is_404(client):
    resp = client.post("/evaluate", json={"flag": "nope", "user": "u1"})
    assert resp.status_code == 404


def test_evaluate_boolean_and_targeting(client):
    _put(
        client,
        "eu-pricing",
        rollout_percentage=0,
        rules=[{"attribute": "country", "operator": "in", "value": ["DE", "FR"]}],
    )
    on = client.post(
        "/evaluate",
        json={"flag": "eu-pricing", "user": "u1", "attributes": {"country": "DE"}},
    ).json()
    off = client.post(
        "/evaluate",
        json={"flag": "eu-pricing", "user": "u1", "attributes": {"country": "US"}},
    ).json()
    assert on["enabled"] is True and on["reason"] == "targeting"
    assert off["enabled"] is False
