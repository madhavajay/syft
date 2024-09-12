import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from threading import Event

import requests

from lib import (
    FileChange,
    FileChangeKind,
    Jsonable,
    SyftPermission,
    bintostr,
    perm_file_path,
)


# write operations
def diff_dirstate(old, new):
    sync_folder = old.sync_folder
    old_sub_path = old.sub_path
    try:
        changes = []
        for afile, file_hash in new.tree.items():
            kind = None
            if afile in old.tree.keys():
                if old.tree[afile] != file_hash:
                    # update
                    kind = FileChangeKind.WRITE
            else:
                # create
                kind = FileChangeKind.CREATE

            if kind:
                change = FileChange(
                    kind=kind,
                    parent_path=old_sub_path,
                    sub_path=afile,
                    file_hash=file_hash,
                    sync_folder=sync_folder,
                )
                changes.append(change)

        for afile, file_hash in old.tree.items():
            if afile not in new.tree.keys():
                # delete
                kind = FileChangeKind.DELETE
                change = FileChange(
                    kind=kind,
                    parent_path=old.sub_path,
                    sub_path=afile,
                    file_hash=file_hash,
                    sync_folder=sync_folder,
                )
                changes.append(change)
        return changes
    except Exception as e:
        print("Error in diff_dirstate", str(e))
        raise e


@dataclass
class DirState(Jsonable):
    tree: dict[str, str]
    timestamp: float
    sync_folder: str
    sub_path: str


def prune_invalid_changes(new, valid_changes) -> DirState:
    new_tree = {}
    for file, file_hash in new.tree.items():
        internal_path = new.sub_path + "/" + file
        if internal_path in valid_changes:
            new_tree[file] = file_hash

    return DirState(
        tree=new_tree,
        timestamp=new.timestamp,
        sync_folder=new.sync_folder,
        sub_path=new.sub_path,
    )


def delete_files(new, deleted_files) -> DirState:
    new_tree = {}
    for file, file_hash in new.tree.items():
        internal_path = new.sub_path + "/" + file
        if internal_path not in deleted_files:
            new_tree[file] = file_hash

    return DirState(
        tree=new_tree,
        timestamp=new.timestamp,
        sync_folder=new.sync_folder,
        sub_path=new.sub_path,
    )


stop_event = Event()

CLIENT_CHANGELOG_FOLDER = "syft_changelog"

stop_event = Event()

PLUGIN_NAME = "sync"

ICON_FILE = "Icon"  # special
IGNORE_FILES = ["sync_checkpoints.sqlite"]
IGNORE_FOLDERS = [CLIENT_CHANGELOG_FOLDER]


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


def filter_changes(
    user_email: str, changes: list[FileChange], perm_file: SyftPermission
):
    valid_changes = []
    valid_change_files = []
    invalid_changes = []
    for change in changes:
        if change.kind in [
            FileChangeKind.WRITE,
            FileChangeKind.CREATE,
            FileChangeKind.DELETE,
        ]:
            if user_email in perm_file.write or "GLOBAL" in perm_file.write:
                valid_changes.append(change)
                valid_change_files.append(change.sub_path)
                continue
        invalid_changes.append(change)
    return valid_changes, valid_change_files, invalid_changes


def push_changes(client_config, changes):
    written_changes = []
    for change in changes:
        try:
            data = {
                "email": client_config.email,
                "change": change.to_dict(),
            }
            if change.kind_write:
                data["data"] = bintostr(change.read())
            elif change.kind_delete:
                # no data
                pass

            response = requests.post(
                f"{client_config.server_url}/write",
                json=data,
            )
            write_response = response.json()
            change_result = write_response["change"]
            change_result["kind"] = FileChangeKind(change_result["kind"])
            ok_change = FileChange(**change_result)
            if response.status_code == 200:
                print(
                    f"> {client_config.email} /write {change.kind} {change.internal_path}"
                )
                written_changes.append(ok_change)
            else:
                print(
                    f"> {client_config.email} FAILED /write {change.kind} {change.internal_path}"
                )
        except Exception as e:
            print("Failed to call /write on the server", str(e))
    return written_changes


def sync(client_config):
    # create a folder to store the change log
    change_log_folder = f"{client_config.sync_folder}/{CLIENT_CHANGELOG_FOLDER}"
    os.makedirs(change_log_folder, exist_ok=True)

    # get all the datasites
    datasites = get_datasites(client_config.sync_folder)
    for datasite in datasites:
        # get the top level perm file

        datasite_permfile = perm_file_path(
            os.path.join(client_config.sync_folder, datasite)
        )

        permission = SyftPermission.load(datasite_permfile)

        dir_filename = f"{change_log_folder}/{datasite}.json"

        # get the old dir state
        old_dir_state = DirState.load(dir_filename)
        if old_dir_state is None:
            old_dir_state = DirState(
                tree={},
                timestamp=0,
                sync_folder=client_config.sync_folder,
                sub_path=datasite,
            )
            print(f"> {client_config.email} Creating datasite:{datasite} state")

        # get the new dir state
        new_dir_state = hash_dir(client_config.sync_folder, datasite)
        changes = diff_dirstate(old_dir_state, new_dir_state)
        if len(changes) == 0:
            print("😴", end=None)
            return

        val, val_files, inval = filter_changes(client_config.email, changes, permission)

        # send val changes
        results = push_changes(client_config, val)
        deleted_files = []
        changed_files = []
        for result in results:
            if result.kind_write:
                changed_files.append(result.internal_path)
            elif result.kind_delete:
                deleted_files.append(result.internal_path)

        synced_dir_state = prune_invalid_changes(new_dir_state, changed_files)

        # combine successfulc hanges qwith old dir state
        combined_tree = old_dir_state.tree
        combined_tree.update(synced_dir_state.tree)
        synced_dir_state.tree = combined_tree

        synced_dir_state = delete_files(new_dir_state, deleted_files)

        # this will be old_dir_state next run
        if len(synced_dir_state.tree.keys()) == 0:
            raise Exception(f"Trying to save no keys, {synced_dir_state.tree}")
        print(f"> {client_config.email} NSYNC 👨‍👨‍👦‍👦")
        synced_dir_state.save(dir_filename)


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


def hash_dir(sync_folder: str, sub_path: str) -> DirState:
    state_dict = {}
    full_path = os.path.join(sync_folder, sub_path)
    for root, dirs, files in os.walk(full_path):
        if not ignore_dirs(full_path, root):
            for file in files:
                if not ignore_file(full_path, root, file):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, full_path)
                    state_dict[rel_path] = get_file_hash(path)

    utc_unix_timestamp = datetime.now().timestamp()
    dir_state = DirState(
        tree=state_dict,
        timestamp=utc_unix_timestamp,
        sync_folder=sync_folder,
        sub_path=sub_path,
    )
    return dir_state


def run(shared_state):
    try:
        if not stop_event.is_set():
            if shared_state.client_config.token:
                sync(shared_state.client_config)
            else:
                print("init first")
    except Exception as e:
        print("Failed to run plugin", e)
