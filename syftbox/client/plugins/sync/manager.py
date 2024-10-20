from pathlib import Path

from syftbox.client.plugins.sync.constants import CLIENT_CHANGELOG_FOLDER
from syftbox.client.plugins.sync.endpoints import list_datasites
from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem
from syftbox.client.plugins.sync.sync import DatasiteState, FileChangeInfo
from syftbox.lib import Client


class SyncManager:
    def __init__(self, client: Client):
        self.client = client
        self.queue = SyncQueue()

        self.change_log_folder = Path(client.sync_folder) / CLIENT_CHANGELOG_FOLDER

        self.setup()

    def setup(self):
        self.change_log_folder.mkdir(exist_ok=True)

    def enqueue(self, change: FileChangeInfo) -> None:
        self.queue.put(SyncQueueItem(priority=change.get_priority(), data=change))

    def get_datasites(self) -> list[DatasiteState]:
        datasites_from_server = list_datasites(self.client)
        datasites = [
            DatasiteState(client=self.client, email=email)
            for email in datasites_from_server
        ]

        return datasites

    def sync_unthreaded(self):
        # NOTE first implementation will be unthreaded and just loop through all datasites
        # TODO implement
        self.datasites = self.get_datasites()

        for datasite in self.datasites:
            permission_changes, file_changes = datasite.get_out_of_sync_files()
            for change in permission_changes:
                self.enqueue(change)
            for change in file_changes:
                self.enqueue(change)

        self.consumer.consume_all()
