import json
import time
from collections.abc import Generator
from functools import partial
from pathlib import Path
from typing import Mapping, Union

import faker
import httpx
import pytest
from fastapi.testclient import TestClient

from syftbox.client.plugins.create_datasite import run as run_create_datasite_plugin
from syftbox.client.plugins.init import run as run_init_plugin
from syftbox.client.plugins.sync.manager import SyncManager, SyncQueueItem
from syftbox.client.plugins.sync.sync import is_permission_file
from syftbox.lib import Client
from syftbox.lib.lib import ClientConfig, SharedState, SyftPermission, perm_file_path
from syftbox.server.server import app as server_app
from syftbox.server.server import lifespan as server_lifespan
from syftbox.server.settings import ServerSettings

fake = faker.Faker()

DirTree = Mapping[str, Union[str, "DirTree"]]


def create_local_tree(base_path: Path, tree: DirTree) -> None:
    print(f"creating tree at {base_path}, {type(base_path)}")
    for name, content in tree.items():
        local_path = base_path / name

        if isinstance(content, str):
            local_path.write_text(content)
        elif isinstance(content, SyftPermission):
            content.save(path=str(local_path))
        elif isinstance(content, dict):
            local_path.mkdir(parents=True, exist_ok=True)
            create_local_tree(local_path, content)


@pytest.fixture(scope="function")
def datasite_1(tmp_path: Path, server_client: TestClient) -> ClientConfig:
    email = "user_1@openmined.org"
    return setup_datasite(tmp_path, server_client, email)


@pytest.fixture(scope="function")
def datasite_2(tmp_path: Path, server_client: TestClient) -> ClientConfig:
    email = "user_2@openmined.org"
    return setup_datasite(tmp_path, server_client, email)


def setup_datasite(
    tmp_path: Path, server_client: TestClient, email: str
) -> ClientConfig:
    client_path = tmp_path / email
    client_path.unlink(missing_ok=True)
    client_path.mkdir(parents=True)

    client_config = ClientConfig(
        config_path=str(client_path / "client_config.json"),
        sync_folder=str(client_path / "sync"),
        email=email,
        server_url=str(server_client.base_url),
        autorun_plugins=[],
    )

    client_config._server_client = server_client

    shared_state = SharedState(client_config=client_config)
    run_init_plugin(shared_state)
    run_create_datasite_plugin(shared_state)
    wait_for_datasite_setup(client_config)
    return client_config


@pytest.fixture(scope="function")
def server_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    print("Using test dir", tmp_path)
    path = tmp_path / "server"
    path.mkdir()

    settings = ServerSettings.from_data_folder(path)
    lifespan_with_settings = partial(server_lifespan, settings=settings)
    server_app.router.lifespan_context = lifespan_with_settings

    with TestClient(server_app) as client:
        yield client


@pytest.fixture(scope="function")
def http_server_client():
    with httpx.Client(base_url="http://localhost:5001") as client:
        yield client


def wait_for_datasite_setup(client_config: ClientConfig, timeout=5):
    print("waiting for datasite setup...")

    perm_file = perm_file_path(str(client_config.datasite_path))

    t0 = time.time()
    while time.time() - t0 < timeout:
        perm_file_exists = Path(perm_file).exists()
        is_registered = client_config.is_registered
        if perm_file_exists and is_registered:
            print("Datasite setup complete")
            return
        time.sleep(1)

    raise TimeoutError("Datasite setup took too long")


def create_random_file(client_config: ClientConfig, sub_path: str = "") -> Path:
    relative_path = Path(sub_path) / fake.file_name(extension="json")
    file_path = client_config.datasite_path / relative_path
    content = {"body": fake.text()}
    file_path.write_text(json.dumps(content))

    path_in_datasite = file_path.relative_to(client_config.sync_folder)
    return path_in_datasite


def assert_files_not_on_datasite(datasite: ClientConfig, files: list[Path]):
    for file in files:
        assert not (
            datasite.sync_folder / file
        ).exists(), f"File {file} exists on datasite {datasite.email}"


def assert_files_on_datasite(datasite: ClientConfig, files: list[Path]):
    for file in files:
        assert (
            datasite.sync_folder / file
        ).exists(), f"File {file} does not exist on datasite {datasite.email}"


def assert_files_on_server(server_client: TestClient, files: list[Path]):
    server_settings: ServerSettings = server_client.app_state["server_settings"]
    for file in files:
        assert (
            server_settings.snapshot_folder / file
        ).exists(), f"File {file} does not exist on server"


def assert_dirtree_exists(base_path: Path, tree: DirTree) -> None:
    for name, content in tree.items():
        local_path = base_path / name

        if isinstance(content, str):
            assert local_path.read_text() == content
        elif isinstance(content, SyftPermission):
            assert json.loads(local_path.read_text()) == content.to_dict()
        elif isinstance(content, dict):
            assert local_path.is_dir()
            assert_dirtree_exists(local_path, content)


def test_get_datasites(datasite_1: Client, datasite_2: Client):
    emails = {datasite_1.email, datasite_2.email}
    sync_service = SyncManager(datasite_1)

    datasites = sync_service.get_datasites()
    assert {datasites[0].email, datasites[1].email} == emails


def test_enqueue_changes(datasite_1: Client):
    sync_service = SyncManager(datasite_1)
    datasites = sync_service.get_datasites()

    out_of_sync_permissions, out_of_sync_files = datasites[0].get_out_of_sync_files()
    num_files_after_setup = len(out_of_sync_files) + len(out_of_sync_permissions)

    # Create two files in datasite_1
    tree = {
        "folder1": {
            "_.syftperm": SyftPermission.mine_with_public_read(datasite_1.email),
            "large.txt": fake.text(max_nb_chars=1000),
            "small.txt": fake.text(max_nb_chars=10),
        },
    }
    create_local_tree(Path(datasite_1.datasite_path), tree)
    out_of_sync_permissions, out_of_sync_files = datasites[0].get_out_of_sync_files()
    num_out_of_sync_files = len(out_of_sync_files) + len(out_of_sync_permissions)
    # 3 new files
    assert num_out_of_sync_files - num_files_after_setup == 3

    # Enqueue the changes + verify order
    for change in out_of_sync_permissions + out_of_sync_files:
        sync_service.enqueue(change)

    items_from_queue: list[SyncQueueItem] = []
    while not sync_service.queue.empty():
        items_from_queue.append(sync_service.queue.get())

    should_be_permissions = items_from_queue[: len(out_of_sync_permissions)]
    should_be_files = items_from_queue[len(out_of_sync_permissions) :]

    assert all(is_permission_file(item.data.path) for item in should_be_permissions)
    assert all(not is_permission_file(item.data.path) for item in should_be_files)

    for item in should_be_files:
        print(item.priority, item.data)
