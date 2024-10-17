import time

from fastapi.testclient import TestClient

from syftbox.lib.lib import bintostr
from tests.server.conftest import TEST_DATASITE_NAME, TEST_FILE


def test_register(client: TestClient):
    data = {"email": "test@example.com"}
    response = client.post("/register", json=data)
    assert response.status_code == 200
    assert "token" in response.json()

    response = client.get("/list_datasites")
    assert response.status_code == 200


def test_write_file(client: TestClient):
    request_data = {
        "email": TEST_DATASITE_NAME,
        "change": {
            "kind": "write",
            "parent_path": TEST_DATASITE_NAME,
            "sub_path": "test_file.txt",
            "file_hash": "some_hash",
            "last_modified": time.time(),
        },
        "data": bintostr(b"Hello, World!"),
    }

    # Send POST request to /write endpoint
    response = client.post("/write", json=request_data)
    response.raise_for_status()
    data = response.json()
    print(data)


def test_list_datasites(client: TestClient):
    response = client.get("/list_datasites")
    assert response.status_code == 200

    assert len(response.json()["datasites"])

    response = client.get(f"/datasites/{TEST_DATASITE_NAME}/")
    assert response.status_code == 200


def test_read_file(client: TestClient):
    change = {
        "kind": "write",
        "parent_path": TEST_DATASITE_NAME,
        "sub_path": TEST_FILE,
        "file_hash": "some_hash",
        "last_modified": time.time(),
    }
    response = client.post(
        "/read", json={"email": TEST_DATASITE_NAME, "change": change}
    )

    response.raise_for_status()


def test_read_folder(client: TestClient):
    change = {
        "kind": "write",
        "parent_path": TEST_DATASITE_NAME,
        "sub_path": ".",
        "file_hash": "some_hash",
        "last_modified": time.time(),
    }
    response = client.post(
        "/read", json={"email": TEST_DATASITE_NAME, "change": change}
    )

    response.raise_for_status()


def test_dir_state(client: TestClient):
    response = client.post(
        "/dir_state", json={"email": TEST_DATASITE_NAME, "sub_path": "."}
    )

    response.raise_for_status()
    tree = response.json()["dir_state"]["tree"]
    assert "test_datasite@openmined.org/test_file.txt" in tree


def test_dir_state_random(client_without_perms: TestClient):
    response = client_without_perms.post(
        "/dir_state",
        json={
            "email": TEST_DATASITE_NAME,
            "sub_path": ".",
        },
    )

    response.raise_for_status()
    tree = response.json()["dir_state"]["tree"]
    assert "test_datasite@openmined.org/test_file.txt" in tree
