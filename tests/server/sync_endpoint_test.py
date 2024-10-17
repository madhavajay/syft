import base64
import hashlib

from fastapi.testclient import TestClient
from py_fast_rsync import signature

from tests.server.conftest import TEST_DATASITE_NAME, TEST_FILE


def test_get_signature(client: TestClient):
    response = client.post(
        "/sync/get_signature", json={"path": f"{TEST_DATASITE_NAME}/{TEST_FILE}"}
    )

    response.raise_for_status()
    assert response.json()["signature"]


def test_get_apply_diff(client: TestClient):
    data = "Hello, Moon!".encode("utf-8")
    sig = signature.calculate(data)
    sig_b85 = base64.b85encode(sig).decode("utf-8")
    response = client.post(
        "/sync/get_diff",
        json={"path": f"{TEST_DATASITE_NAME}/{TEST_FILE}", "signature": sig_b85},
    )

    response.raise_for_status()
    diff = response.json()["diff"]

    assert diff
    expected_hash = hashlib.sha256(data).hexdigest()

    response = client.post(
        "/sync/apply_diff",
        json={
            "path": f"{TEST_DATASITE_NAME}/{TEST_FILE}",
            "diff": diff,
            "expected_hash": expected_hash,
        },
    )

    response.raise_for_status()
