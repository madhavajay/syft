import json
from pathlib import Path

import faker
from fastapi.testclient import TestClient

from syftbox.client.plugins.sync.manager import SyncManager, SyncQueueItem
from syftbox.client.plugins.sync.sync import is_permission_file
from syftbox.client.utils.dir_tree import DirTree, create_dir_tree
from syftbox.lib import Client
from syftbox.lib.lib import ClientConfig, SyftPermission
from syftbox.server.settings import ServerSettings

fake = faker.Faker()


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
    create_dir_tree(Path(datasite_1.datasite_path), tree)
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
