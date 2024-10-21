import base64
import hashlib
from pathlib import Path

import py_fast_rsync
from fastapi.testclient import TestClient
from py_fast_rsync import signature

from syftbox.server.sync.models import DiffResponse
from tests.server.conftest import TEST_DATASITE_NAME, TEST_FILE


def test_get_all_permissions(client: TestClient):
    # TODO: filter permissions and not return everything
    response = client.post(
        "/sync/get_metadata",
        json={"path_like": "%.syftperm"},
    )

    response.raise_for_status()
    assert len(response.json())


def test_get_diff(client: TestClient):
    local_data = b"This is my local data"
    sig = signature.calculate(local_data)
    sig_b85 = base64.b85encode(sig).decode("utf-8")
    response = client.post(
        "/sync/get_diff",
        json={
            "path": f"{TEST_DATASITE_NAME}/{TEST_FILE}",
            "signature": sig_b85,
        },
    )

    response.raise_for_status()
    diff_response = DiffResponse.model_validate(response.json())
    remote_diff = diff_response.diff_bytes
    probably_remote_data = py_fast_rsync.apply(local_data, remote_diff)

    server_settings = client.app_state["server_settings"]
    file_server_contents = server_settings.read(f"{TEST_DATASITE_NAME}/{TEST_FILE}")
    assert file_server_contents == probably_remote_data


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


def test_delete_file(client: TestClient):
    response = client.post(
        "/sync/delete",
        json={"path": f"{TEST_DATASITE_NAME}/{TEST_FILE}"},
    )

    response.raise_for_status()
    snapshot_folder = client.app_state["server_settings"].snapshot_folder
    path = Path(f"{snapshot_folder}/{TEST_DATASITE_NAME}/{TEST_FILE}")
    assert not path.exists()


def test_create_file(client: TestClient):
    response = client.post(
        "/sync/create",
        json={"path": f"{TEST_DATASITE_NAME}/{TEST_FILE}"},
    )

    response.raise_for_status()
    snapshot_folder = client.app_state["server_settings"].snapshot_folder
    path = Path(f"{snapshot_folder}/{TEST_DATASITE_NAME}/{TEST_FILE}")
    assert not path.exists()
