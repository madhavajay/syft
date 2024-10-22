from syftbox.client.plugins.sync.manager import SyncManager
from syftbox.lib.lib import Client, SharedState


def run(shared_state: SharedState):
    client: Client = shared_state.client_config
    manager = SyncManager(client)
    while True:
        manager.sync_unthreaded()
