import base64
import hashlib

import py_fast_rsync
from fastapi.testclient import TestClient

from tests.server.conftest import TEST_DATASITE_NAME, TEST_FILE


def test_get_all_permissions(client: TestClient):
    # TODO: filter permissions and not return everything
    response = client.post(
        "/sync/get_metadata",
        json={"path_like": "%.syftperm"},
    )

    response.raise_for_status()
    assert len(response.json())


def test_syft_client_push_flow(client: TestClient):
    response = client.post(
        "/sync/get_metadata",
        json={"path_like": f"%{TEST_DATASITE_NAME}/{TEST_FILE}"},
    )

    response.raise_for_status()
    server_signature_b85 = response.json()[0]["signature"]
    server_signature = base64.b85decode(server_signature_b85)
    assert server_signature

    local_data = b"This is my local data"
    delta = py_fast_rsync.diff(server_signature, local_data)
    delta_b85 = base64.b85encode(delta).decode("utf-8")
    expected_hash = hashlib.sha256(local_data).hexdigest()

    response = client.post(
        "/sync/apply_diff",
        json={
            "path": f"{TEST_DATASITE_NAME}/{TEST_FILE}",
            "diff": delta_b85,
            "expected_hash": expected_hash,
        },
    )

    response.raise_for_status()

    result = response.json()
    snapshot_folder = client.app_state["server_settings"].snapshot_folder
    with open(f"{snapshot_folder}/{TEST_DATASITE_NAME}/{TEST_FILE}", "rb") as f:
        sha256local = hashlib.file_digest(f, "sha256").hexdigest()
    assert result["current_hash"] == expected_hash == sha256local
