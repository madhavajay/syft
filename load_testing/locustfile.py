from locust import HttpUser, task

from syftbox.client.plugins.sync import endpoints


class SyftBoxUser(HttpUser):
    def on_start(self):
        self.datasites = []
        self.email = "aziz@openmined.org"
        self.remote_state: dict[str, list[endpoints.FileMetadata]] = {}

    @task
    def get_datasites(self):
        self.datasites = endpoints.list_datasites(self.client)

    @task
    def sync_datasites(self):
        for datasite in self.datasites:
            metadata_list = endpoints.get_remote_state(client=self.client, email=self.email, path=datasite)
            self.remote_state[datasite] = metadata_list

    @task
    def get_metadata(self):
        for datasite, metadata_list in self.remote_state.items():
            for metadata in metadata_list:
                endpoints.get_metadata(client=self.client, path=metadata.path)
