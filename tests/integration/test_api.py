from fastapi.testclient import TestClient

from naturematch.service.api.app import app

c = TestClient(app)


def test_health():
    assert c.get("/health").json() == {"status": "ok"}
