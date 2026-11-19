from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from naturematch.service.api.app import app
from naturematch.service.api.routes.observations import store


client = TestClient(app)


def setup_function() -> None:
    store.clear()


def observation(
    *,
    observation_id: str,
    metric: str = "temperature",
    value: float | None = 20.0,
    ts: datetime | None = None,
) -> dict:
    return {
        "id": observation_id,
        "station_id": "NM-01",
        "metric": metric,
        "value": value,
        "unit": "C",
        "ts": (ts or datetime(2026, 11, 19, tzinfo=UTC)).isoformat(),
        "quality": "ok",
    }


def test_ingest_accepts_batch_and_returns_latest() -> None:
    response = client.post(
        "/api/v1/observations",
        json=[observation(observation_id="a"), observation(observation_id="b", metric="humidity")],
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": 2, "duplicates": 0}
    latest = client.get("/api/v1/stations/NM-01/latest")
    assert {item["metric"] for item in latest.json()} == {"temperature", "humidity"}


def test_resending_same_observation_is_idempotent() -> None:
    payload = [observation(observation_id="same")]

    assert client.post("/api/v1/observations", json=payload).json() == {
        "accepted": 1,
        "duplicates": 0,
    }
    assert client.post("/api/v1/observations", json=payload).json() == {
        "accepted": 0,
        "duplicates": 1,
    }


def test_conflicting_reuse_of_observation_id_is_rejected() -> None:
    assert (
        client.post(
            "/api/v1/observations", json=[observation(observation_id="same")]
        ).status_code
        == 202
    )

    conflict = client.post(
        "/api/v1/observations",
        json=[observation(observation_id="same", value=21.0)],
    )

    assert conflict.status_code == 409


def test_conflicting_ids_in_one_batch_are_rejected() -> None:
    response = client.post(
        "/api/v1/observations",
        json=[
            observation(observation_id="same", value=20.0),
            observation(observation_id="same", value=21.0),
        ],
    )

    assert response.status_code == 409


def test_delayed_observation_does_not_replace_newer_latest() -> None:
    newer = datetime(2026, 11, 19, 12, 1, tzinfo=UTC)
    older = newer - timedelta(minutes=1)
    assert (
        client.post(
            "/api/v1/observations",
            json=[observation(observation_id="new", value=22.0, ts=newer)],
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/api/v1/observations",
            json=[observation(observation_id="old", value=18.0, ts=older)],
        ).status_code
        == 202
    )

    latest = client.get("/api/v1/stations/NM-01/latest").json()
    assert latest[0]["value"] == 22.0


def test_missing_value_is_preserved() -> None:
    payload = observation(observation_id="missing", value=None)
    response = client.post("/api/v1/observations", json=[payload])

    assert response.status_code == 202
    assert client.get("/api/v1/stations/NM-01/latest").json()[0]["value"] is None
