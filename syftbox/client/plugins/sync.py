import os
from threading import Event

import requests

from syftbox.lib import (
    DirState,
    FileChange,
    FileChangeKind,
    PermissionTree,
    bintostr,
    get_datasites,
    hash_dir,
    strtobin,
)

CLIENT_CHANGELOG_FOLDER = "syft_changelog"
IGNORE_FOLDERS = [CLIENT_CHANGELOG_FOLDER]


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


stop_event = Event()

PLUGIN_NAME = "sync"


def filter_changes(
    user_email: str,
    changes: list[FileChange],
    perm_tree: PermissionTree,
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
            perm_file_at_path = perm_tree.permission_for_path(change.full_path)
            if (
                user_email in perm_file_at_path.write
                or "GLOBAL" in perm_file_at_path.write
            ) and perm_file_at_path.read != [
                user_email,
            ]:  # skip upload if only we have read perms.
                valid_changes.append(change)
                valid_change_files.append(change.sub_path)
                continue
            if perm_file_at_path.read == [user_email]:
                if change.internal_path[-10:] == "_.syftperm":
                    # include changes for syft_perm file even if only we have read perms.
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
                written_changes.append(ok_change)
            else:
                print(
                    f"> {client_config.email} FAILED /write {change.kind} {change.internal_path}",
                )
        except Exception as e:
            print("Failed to call /write on the server", str(e))
    return written_changes


def pull_changes(client_config, changes):
    remote_changes = []
    for change in changes:
        try:
            data = {
                "email": client_config.email,
                "change": change.to_dict(),
            }
            response = requests.post(
                f"{client_config.server_url}/read",
                json=data,
            )
            read_response = response.json()
            change_result = read_response["change"]
            change_result["kind"] = FileChangeKind(change_result["kind"])
            ok_change = FileChange(**change_result)

            if ok_change.kind_write:
                data = strtobin(read_response["data"])
            elif change.kind_delete:
                data = None

            if response.status_code == 200:
                print(
                    f"> {client_config.email} /read {change.kind} {change.internal_path}",
                )
                remote_changes.append((ok_change, data))
            else:
                print(
                    f"> {client_config.email} FAILED /read {change.kind} {change.internal_path}",
                )
        except Exception as e:
            print("Failed to call /read on the server", str(e))
    return remote_changes


def list_datasites(client_config):
    datasites = []
    try:
        response = requests.get(
            f"{client_config.server_url}/datasites",
        )
        read_response = response.json()
        remote_datasites = read_response["datasites"]

        if response.status_code == 200:
            datasites = remote_datasites
        else:
            print(f"> {client_config.email} FAILED /datasites")
    except Exception as e:
        print("Failed to call /datasites on the server", str(e))
    return datasites


def get_remote_state(client_config, sub_path: str):
    try:
        data = {
            "email": client_config.email,
            "sub_path": sub_path,
        }

        response = requests.post(
            f"{client_config.server_url}/dir_state",
            json=data,
        )
        state_response = response.json()
        if response.status_code == 200:
            dir_state = DirState(**state_response["dir_state"])
            return dir_state
        print(f"> {client_config.email} FAILED /dir_state: {sub_path}")
        return None
    except Exception as e:
        print("Failed to call /dir_state on the server", str(e))


def create_datasites(client_config):
    datasites = list_datasites(client_config)
    for datasite in datasites:
        # get the top level perm file
        os.makedirs(os.path.join(client_config.sync_folder, datasite), exist_ok=True)


def ascii_for_change(changes) -> str:
    count = 0
    change_text = ""
    for change in changes:
        count += 1
        pipe = "├──"
        if count == len(changes):
            pipe = "└──"
        change_text += pipe + change
    return change_text


def sync_up(client_config):
    # create a folder to store the change log
    change_log_folder = f"{client_config.sync_folder}/{CLIENT_CHANGELOG_FOLDER}"
    os.makedirs(change_log_folder, exist_ok=True)

    # get all the datasites
    datasites = get_datasites(client_config.sync_folder)

    n_changes = 0

    for datasite in datasites:
        # get the top level perm file
        datasite_path = os.path.join(client_config.sync_folder, datasite)

        perm_tree = PermissionTree.from_path(datasite_path)

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

        # get the new dir state
        new_dir_state = hash_dir(client_config.sync_folder, datasite, IGNORE_FOLDERS)
        changes = diff_dirstate(old_dir_state, new_dir_state)
        if len(changes) == 0:
            continue

        val, val_files, inval = filter_changes(client_config.email, changes, perm_tree)

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

        # combine successful changes qwith old dir state
        combined_tree = old_dir_state.tree
        combined_tree.update(synced_dir_state.tree)
        synced_dir_state.tree = combined_tree

        synced_dir_state = delete_files(new_dir_state, deleted_files)

        change_text = ""
        if len(changed_files):
            change_text += f"🔼 Syncing Up {len(changed_files)} Changes\n"
            change_text += ascii_for_change(changed_files)

        if len(deleted_files):
            change_text += f"❌ Syncing Up {len(deleted_files)} Deletes\n"
            change_text += ascii_for_change(deleted_files)

        print(change_text)

        synced_dir_state.save(dir_filename)
        n_changes += len(changed_files) + len(deleted_files)

    return n_changes


def sync_down(client_config) -> int:
    # create a folder to store the change log
    change_log_folder = f"{client_config.sync_folder}/{CLIENT_CHANGELOG_FOLDER}"
    os.makedirs(change_log_folder, exist_ok=True)

    n_changes = 0

    # get all the datasites
    datasites = get_datasites(client_config.sync_folder)
    for datasite in datasites:
        # get the top level perm file

        dir_filename = f"{change_log_folder}/{datasite}.json"

        datasite_path = os.path.join(client_config.sync_folder, datasite)
        perm_tree = PermissionTree.from_path(datasite_path)

        # get the new dir state
        new_dir_state = hash_dir(client_config.sync_folder, datasite, IGNORE_FOLDERS)
        remote_dir_state = get_remote_state(client_config, datasite)
        if not remote_dir_state:
            print(f"No remote state for dir: {datasite}")
            return None

        changes = diff_dirstate(new_dir_state, remote_dir_state)

        if len(changes) == 0:
            continue

        # fetch writes from the /read endpoint
        fetch_files = []
        for change in changes:
            if change.kind_write:
                fetch_files.append(change)

        results = pull_changes(client_config, fetch_files)

        # make writes
        changed_files = []
        for change, data in results:
            change.sync_folder = client_config.sync_folder
            if change.kind_write:
                result = change.write(data)
                if result:
                    changed_files.append(change.internal_path)

        # delete local files dont need the server
        deleted_files = []
        for change in changes:
            change.sync_folder = client_config.sync_folder
            if change.kind_delete:
                perm_file_at_path = perm_tree.permission_for_path(change.sub_path)
                if perm_file_at_path.read != [client_config.email]:
                    # the only reason we're wanting to delete this is because
                    # we skipped sending it to the server. and the raeson we
                    # skipped sending it to the server is because it's a file that
                    # only we can read, and so we don't want to share it with the
                    # server... who we might not trust. Aka... this is a private file/folder
                    # only for us.
                    continue
                result = change.delete()
                if result:
                    deleted_files.append(change.internal_path)

        synced_dir_state = prune_invalid_changes(new_dir_state, changed_files)

        # combine successfulc hanges qwith old dir state
        combined_tree = new_dir_state.tree
        combined_tree.update(synced_dir_state.tree)
        synced_dir_state.tree = combined_tree

        synced_dir_state = delete_files(new_dir_state, deleted_files)

        change_text = ""
        if len(changed_files):
            change_text += f"⏬ Syncing Down {len(changed_files)} Changes\n"
            change_text += ascii_for_change(changed_files)
        if len(deleted_files):
            change_text += f"❌ Syncing Down {len(deleted_files)} Deletes\n"
            change_text += ascii_for_change(deleted_files)

        if len(change_text) > 0:
            print(change_text)

        synced_dir_state.save(dir_filename)
        n_changes += len(changed_files) + len(deleted_files)

    return n_changes


def run(shared_state):
    try:
        if not stop_event.is_set():
            num_changes = 0
            if shared_state.client_config.token:
                try:
                    create_datasites(shared_state.client_config)
                except Exception as e:
                    print("failed to get_datasites", e)

                try:
                    num_changes += sync_up(shared_state.client_config)
                except Exception as e:
                    print("failed to sync up", e)

                try:
                    num_changes += sync_down(shared_state.client_config)
                except Exception as e:
                    print("failed to sync down", e)
            if num_changes == 0:
                print("✅ Synced")
    except Exception as e:
        print("Failed to run plugin", e)
