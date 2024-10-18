from syftbox.client.plugins.sync.constants import CLIENT_CHANGELOG_FOLDER
from syftbox.client.plugins.sync.consumer import SyncConsumer
from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem
from syftbox.client.plugins.sync.sync import DatasiteState, FileChangeInfo
from syftbox.lib import Client


class SyncManager:
    def __init__(self, client: Client):
        self.queue = SyncQueue()
        self.consumer = SyncConsumer()

        self.datasites: list[DatasiteState] = []

        self.change_log_folder = client.sync_folder / CLIENT_CHANGELOG_FOLDER

        self.setup()

    def setup(self):
        self.change_log_folder.mkdir(exist_ok=True)

    def enqueue(self, change: FileChangeInfo) -> None:
        self.queue.put(SyncQueueItem(priority=change.priority, data=change))

    def get_datasites(self) -> list[DatasiteState]:
        """get all local and remote datasites"""
        pass  # TODO

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
