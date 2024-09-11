import logging
import os

from lib.lib import USER_GROUP_GLOBAL, SyftPermission

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 10000
DESCRIPTION = (
    "A plugin that synchronizes datasite folders between Syft and SyftBox folders."
)


def perm_file_path(path: str) -> str:
    return f"{path}/_.syftperm"


def claim_datasite(client_config):
    # create the directory
    print("claiming datasiet", client_config.datasite_path)
    os.makedirs(client_config.datasite_path, exist_ok=True)

    # add the first perm file
    file_path = perm_file_path(client_config.datasite_path)
    print("perm file path", file_path)
    if os.path.exists(file_path):
        print("loading perm")
        perm_file = SyftPermission.load(file_path)
    else:
        print("creating perm")
        perm_file = SyftPermission(
            vote=[client_config.email],
            read=[client_config.email, USER_GROUP_GLOBAL],
            write=[client_config.email],
        )
        perm_file.save(file_path)
    print("finished claiming datasite")


def run(shared_state):
    client_config = shared_state.client_config
    claim_datasite(client_config)
