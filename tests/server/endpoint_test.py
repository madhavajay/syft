from fastapi.testclient import TestClient

from tests.server.conftest import TEST_DATASITE_NAME


def test_register(client: TestClient):
    data = {"email": "test@example.com"}
    response = client.post("/register", json=data)
    assert response.status_code == 200
    assert "token" in response.json()

    response = client.get("/list_datasites")
    assert response.status_code == 200


def test_list_datasites(client: TestClient):
    response = client.get("/list_datasites")
    assert response.status_code == 200

    assert len(response.json()["datasites"])

    response = client.get(f"/datasites/{TEST_DATASITE_NAME}/")
    assert response.status_code == 200
