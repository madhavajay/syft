import httpx

from syftbox.client.plugins.sync.queue import SyncQueue
from syftbox.client.plugins.sync.sync import FileChangeInfo


class SyncConsumer:
    def __init__(self, client: httpx.Client, queue: SyncQueue):
        self.client = client
        self.queue = queue

    def consume_all(self):
        while not self.queue.empty():
            item = self.queue.get()
            # TODO
