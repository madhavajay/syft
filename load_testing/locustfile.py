from locust import FastHttpUser, between, task
from loguru import logger

from syftbox.client.plugins.sync import endpoints


class SyftBoxUser(FastHttpUser):
    network_timeout = 5.0
    connection_timeout = 5.0
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.datasites = []
        self.email = "aziz@openmined.org"
        self.remote_state: dict[str, list[endpoints.FileMetadata]] = {}

    @task
    def sync_datasites(self):
        remote_datasite_states = endpoints.get_datasite_states(
            self.client,
            email=self.email,
        )
        # logger.info(f"Syncing {len(remote_datasite_states)} datasites")
        all_files = []
        for email, remote_state in remote_datasite_states.items():
            all_files.extend(remote_state)

        all_paths = [str(f.path) for f in all_files][:10]
        logger.info(f"Downloading {len(all_paths)} files")
        endpoints.download_bulk(
            self.client,
            all_paths,
        )
