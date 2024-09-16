import os
from pathlib import Path

from syftbox.lib import PermissionTree, get_datasites


def run(shared_state):
    datasites = get_datasites(shared_state.client_config.sync_folder)
    for datasite in datasites:
        # only run on our own datasite
        if datasite != shared_state.client_config.email:
            continue

        # get the top level perm file
        datasite_path = os.path.join(shared_state.client_config.sync_folder, datasite)
        perm_tree = PermissionTree.from_path(datasite_path)

        runners = list(Path(datasite_path).rglob("*run.sh"))
        for runr in runners:
            run_from = str(runr.parent)
            perm = perm_tree.permission_for_path(str(runr))

            if (
                len(perm.write) == 1
                and perm.write[0] == shared_state.client_config.email
            ):
                os.system("cd " + run_from + "; sh run.sh")
