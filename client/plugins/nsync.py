import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from threading import Event

from lib import Jsonable, SyftPermission, perm_file_path

stop_event = Event()

CLIENT_CHANGELOG_FOLDER = "syft_changelog"

stop_event = Event()

PLUGIN_NAME = "sync"

ICON_FILE = "Icon"  # special
IGNORE_FILES = ["sync_checkpoints.sqlite"]
IGNORE_FOLDERS = [CLIENT_CHANGELOG_FOLDER]


@dataclass
class DirState(Jsonable):
    tree: dict[str, str]
    timestamp: float
    sub_path: str


def get_file_hash(file_path: str) -> str:
    with open(file_path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


def get_datasites(sync_folder: str) -> list[str]:
    datasites = []
    folders = os.listdir(sync_folder)
    for folder in folders:
        if "@" in folder:
            datasites.append(folder)
    return datasites


def sync(client_config):
    change_log_folder = f"{client_config.sync_folder}/{CLIENT_CHANGELOG_FOLDER}"
    os.makedirs(change_log_folder, exist_ok=True)

    datasites = get_datasites(client_config.sync_folder)
    for datasite in datasites:
        datasite_path = os.path.abspath(
            os.path.join(client_config.sync_folder, datasite)
        )
        datasite_permfile = perm_file_path(datasite_path)

        permission = SyftPermission.load(datasite_permfile)
        print(">", permission)

        dir_filename = f"{change_log_folder}/{datasite}.json"
        old_dir_state = DirState.load(dir_filename)
        dir_state = hash_dir(datasite_path)
        if old_dir_state is None:
            dir_state.save(dir_filename)
        else:
            print("time to diff")


def ignore_file(directory: str, root: str, filename: str) -> bool:
    if directory == root:
        if filename.startswith(ICON_FILE):
            return True
        if filename in IGNORE_FILES:
            return True
    if filename == ".DS_Store":
        return True
    return False


def ignore_dirs(directory: str, root: str) -> bool:
    if root.endswith(CLIENT_CHANGELOG_FOLDER):
        return True
    return False


def hash_dir(directory: str) -> DirState:
    state_dict = {}
    for root, dirs, files in os.walk(directory):
        if not ignore_dirs(directory, root):
            for file in files:
                if not ignore_file(directory, root, file):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, directory)
                    state_dict[rel_path] = get_file_hash(path)

    utc_unix_timestamp = datetime.now().timestamp()
    dir_state = DirState(
        tree=state_dict, timestamp=utc_unix_timestamp, sub_path=directory
    )
    return dir_state


def run(shared_state):
    if not stop_event.is_set():
        if shared_state.client_config.token:
            sync(shared_state.client_config)
        else:
            print("init first")
