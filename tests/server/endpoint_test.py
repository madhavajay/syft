import time

import pytest
from fastapi.testclient import TestClient

from syftbox.lib.lib import bintostr
from syftbox.server.server import app
from syftbox.server.settings import ServerSettings

TEST_DATASITE_NAME = "test_datasite@openmined.org"


@pytest.fixture(scope="function")
def client(monkeypatch, tmp_path):
    """Every client gets their own snapshot folder at `tmp_path`"""
    snapshot_folder = tmp_path / TEST_DATASITE_NAME
    settings = ServerSettings.from_data_folder(snapshot_folder)
    monkeypatch.setenv("SYFTBOX_DATA_FOLDER", str(settings.data_folder))
    monkeypatch.setenv("SYFTBOX_SNAPSHOT_FOLDER", str(settings.snapshot_folder))
    monkeypatch.setenv("SYFTBOX_USER_FILE_PATH", str(settings.user_file_path))

    datasite_name = TEST_DATASITE_NAME
    datasite = settings.snapshot_folder / datasite_name
    datasite.mkdir(parents=True)

    with TestClient(app) as client:
        yield client


def test_register(client):
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
