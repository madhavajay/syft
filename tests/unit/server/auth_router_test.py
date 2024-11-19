from fastapi.testclient import TestClient

from syftbox.server.server import app

client = TestClient(app)


def test_request_email_token_auth_disabled(server_client):
    """Test requesting email token when auth is disabled"""
    response = server_client.post("/auth/request_email_token", json={"email": "test@example.com"})

    assert response.status_code == 200
    email_token = response.json()["email_token"]

    response = server_client.post("/auth/validate_email_token", headers={"Authorization": f"Bearer {email_token}"})

    assert response.status_code == 200
    assert response.json()["access_token"]
