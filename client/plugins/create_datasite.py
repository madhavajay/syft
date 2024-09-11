import logging
import os

from lib import USER_GROUP_GLOBAL, SyftPermission, perm_file_path

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE = 10000
DESCRIPTION = "Creates a datasite with a permfile"


def claim_datasite(client_config):
    # create the directory
    os.makedirs(client_config.datasite_path, exist_ok=True)

    # add the first perm file
    file_path = perm_file_path(client_config.datasite_path)
    if os.path.exists(file_path):
        perm_file = SyftPermission.load(file_path)
    else:
        perm_file = SyftPermission(
            vote=[client_config.email],
            read=[client_config.email, USER_GROUP_GLOBAL],
            write=[client_config.email],
        )
        perm_file.save(file_path)


def run(shared_state):
    client_config = shared_state.client_config
    claim_datasite(client_config)
