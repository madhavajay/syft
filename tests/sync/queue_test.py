import random
from pathlib import Path
from queue import Empty

import pytest

from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem


def test_sync_queue():
    queue = SyncQueue()

    n = 10

    paths = [Path(f"file_{i}.txt") for i in range(n)]
    priorities = [random.uniform(0, 1000) for _ in range(n)]
    priorities[0] = int(priorities[0])  # int and float should both work
    items = [SyncQueueItem(priority, path) for path, priority in zip(paths, priorities)]
    items_sorted = sorted(items, key=lambda x: x.priority)

    for item in items:
        queue.put(item)

    assert not queue.empty()
    assert queue.dedupe_set == set(paths)

    for item in items_sorted:
        assert queue.get() == item

    assert queue.empty()
    assert queue.dedupe_set == set()
    with pytest.raises(Empty):
        queue.get(block=False)


def test_sync_queue_dedupe():
    queue = SyncQueue()

    path = Path("file.txt")

    queue.put(SyncQueueItem(1, path))
    assert queue.dedupe_set == {path}
    assert not queue.empty()

    for _ in range(10):
        queue.put(SyncQueueItem(random.random(), path))

    assert queue.dedupe_set == {path}

    queue.get()
    assert queue.dedupe_set == set()
    assert queue.empty()


def test_sync_queue_force_put():
    queue = SyncQueue()

    path = Path("file.txt")
    other_path = Path("other_file.txt")

    # Add path to the front of the queue, even though it's already in the queue
    queue.put(SyncQueueItem(0, other_path))
    queue.put(SyncQueueItem(1, path))
    queue.force_put(SyncQueueItem(-1, path))

    assert queue.get().change == path
    assert queue.get().change == other_path
    assert queue.get().change == path
