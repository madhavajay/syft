import base64
import hashlib
import json
import threading
from enum import Enum
from pathlib import Path

import py_fast_rsync
from pydantic import BaseModel

from syftbox.client.plugins.sync.endpoints import (
    SyftServerError,
    apply_diff,
    create,
    delete,
    download,
    get_diff,
    get_metadata,
)
from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem
from syftbox.client.plugins.sync.sync import SyncSide
from syftbox.lib.lib import Client
from syftbox.server.sync.hash import hash_file
from syftbox.server.sync.models import FileMetadata


class SyncDecisionType(Enum):
    NOOP = 0
    CREATE = 1
    MODIFY = 2
    DELETE = 3


def update_local(client: Client, local_metadata: FileMetadata, remote_metadata: FileMetadata):
    diff = get_diff(client.server_client, local_metadata.path, remote_metadata.signature_bytes)

    diff_bytes = base64.b85decode(diff.diff_bytes)

    new_data = py_fast_rsync.apply(local_metadata.read(), diff_bytes)
    new_hash = hashlib.sha256(new_data).hexdigest()

    if new_hash != diff.hash:
        # TODO handle
        raise ValueError("hash mismatch")

    abs_path = client.sync_folder / local_metadata.path
    # TODO implement safe write with tempfile + rename
    abs_path.write_bytes(new_data)


def update_remote(client: Client, local_metadata: FileMetadata, remote_metadata: FileMetadata):
    abs_path = client.sync_folder / local_metadata.path
    local_data = abs_path.read_bytes()

    diff = py_fast_rsync.diff(remote_metadata.signature_bytes, local_data)
    apply_diff(client.server_client, local_metadata.path, diff, local_metadata.hash)


def delete_local(client: Client, remote_metadata: FileMetadata):
    abs_path = client.sync_folder / remote_metadata.path
    abs_path.unlink()


def delete_remote(client: Client, local_metadata: FileMetadata):
    delete(client.server_client, local_metadata.path)


def create_local(client: Client, remote_metadata: FileMetadata):
    abs_path = client.sync_folder / remote_metadata.path
    content_bytes = download(client.server_client, remote_metadata.path)
    abs_path.write_bytes(content_bytes)


def create_remote(client: Client, local_metadata: FileMetadata):
    abs_path = client.sync_folder / local_metadata.path
    data = abs_path.read_bytes()
    create(client.server_client, local_metadata.path, data)


class SyncDecision(BaseModel):
    operation: SyncDecisionType
    side_to_update: SyncSide
    local_metadata: FileMetadata | None
    remote_metadata: FileMetadata | None

    def execute(self, client: Client):
        if self.decision_type == SyncDecisionType.NOOP:
            return

        to_local = self.side_to_update == SyncSide.LOCAL
        to_remote = self.side_to_update == SyncSide.REMOTE

        if self.decision_type == SyncDecisionType.CREATE and to_remote:
            create_remote(client, self.local_metadata)
        elif self.decision_type == SyncDecisionType.CREATE and to_local:
            create_local(client, self.remote_metadata)
        elif self.decision_type == SyncDecisionType.DELETE and to_remote:
            delete_remote(client, self.local_metadata)
        elif self.decision_type == SyncDecisionType.DELETE and to_local:
            delete_local(client, self.remote_metadata)
        elif self.decision_type == SyncDecisionType.MODIFY and to_remote:
            update_remote(client, self.local_metadata, self.remote_metadata)
        elif self.decision_type == SyncDecisionType.MODIFY and to_local:
            update_local(client, self.local_metadata, self.remote_metadata)

    def result_metadata(self):
        if self.side_to_update == SyncSide.REMOTE:
            return self.local_metadata
        else:
            return self.remote_metadata

    @classmethod
    def noop(
        cls,
        local_state: FileMetadata,
        remote_state: FileMetadata,
    ):
        return cls(
            SyncDecisionType.NOOP,
            side_to_update=SyncSide.LOCAL,
            local_metadata=local_state,
            remote_state=remote_state,
        )

    @classmethod
    def from_modified_states(
        cls,
        local_state: FileMetadata | None,
        remote_state: FileMetadata | None,
        side_to_update: SyncSide,
    ):
        """Asssumes at least on of the states is modified"""

        delete = (
            side_to_update == SyncSide.REMOTE
            and local_state is None
            or side_to_update == SyncSide.LOCAL
            and remote_state is None
        )

        create = (
            side_to_update == SyncSide.REMOTE
            and remote_state is None
            or side_to_update == SyncSide.LOCAL
            and local_state is None
        )

        if delete:
            sync_decision_type = SyncDecisionType.DELETE
        elif create:
            sync_decision_type = SyncDecisionType.CREATE
        else:
            sync_decision_type = SyncDecisionType.MODIFY

        return cls(
            sync_decision_type,
            side_to_update=side_to_update,
            local_metadata=local_state,
            remote_state=remote_state,
        )


class SyncDecisionTuple(BaseModel):
    remote_decision: SyncDecision
    local_decision: SyncDecision

    @classmethod
    def from_states(
        cls,
        current_local_state: FileMetadata | None,
        previous_local_state: FileMetadata | None,
        current_remote_state: FileMetadata | None,
    ):
        def noop() -> SyncDecision:
            return SyncDecision.noop(
                local_state=current_local_state,
                remote_state=current_remote_state,
            )

        local_modified = current_local_state != previous_local_state
        remote_modified = previous_local_state != current_remote_state
        in_sync = current_remote_state == current_local_state
        conflict = local_modified and remote_modified and not in_sync

        if in_sync:
            return cls(
                remote_decision=noop(),
                local_decision=noop(),
            )
        elif conflict:
            # in case of conflict we always use the server state, because it was updated earlier
            remote_decision = noop()
            # we apply the server state locally
            local_decision = SyncDecision.from_modified_states(
                local_state=current_local_state,
                remote_state=current_remote_state,
                side_to_update=SyncSide.LOCAL,
            )
            return cls(remote_decision=remote_decision, local_decision=local_decision)
        else:
            # here we can assume only one party changed
            # assert (local_modified and not server_modified) or (server_modified and not local_modified)
            if local_modified:
                return cls(
                    local_decision=noop(),
                    remote_decision=SyncDecision.from_modified_states(
                        local_state=current_local_state,
                        remote_state=current_remote_state,
                        side_to_update=SyncSide.REMOTE,
                    ),
                )
            else:
                return cls(
                    local_decision=SyncDecision.from_modified_states(
                        local_state=current_local_state,
                        remote_state=current_remote_state,
                        side_to_update=SyncSide.LOCAL,
                    ),
                    remote_decision=noop(),
                )


class LocalState(BaseModel):
    path: Path
    states: dict[Path, FileMetadata] = {}

    def insert(self, path: Path, state: FileMetadata):
        self.states[path] = state
        self.save()

    def save(self):
        with threading.Lock():
            self.path.write_text(self.model_dump_json())

    def load(self):
        with threading.Lock():
            if self.path.exists():
                data = self.path.read_text()
                self.states = {k: FileMetadata(**v) for k, v in json.loads(data).items()}


class SyncConsumer:
    def __init__(self, client: Client, queue: SyncQueue):
        self.client = client
        self.queue = queue
        self.previous_state = LocalState(path=Path(client.sync_folder) / ".syft" / "local_state.json")
        self.previous_state.load()

    def consume_all(self):
        while not self.queue.empty():
            item = self.queue.get()
            self.process_filechange(item)

    def process_filechange(self, item: SyncQueueItem, client) -> None:
        path = item.data.path
        current_local_state: FileMetadata = self.get_current_local_state(path)
        previous_local_state = self.get_previous_local_state(path)
        # TODO, rename to remote
        current_server_state = self.get_current_server_state(
            client,
        )

        decisions = SyncDecisionTuple.from_states(current_local_state, previous_local_state, current_server_state)

        decisions.remote_decision.execute(client)
        result_state = decisions.local_decision.execute(client)
        self.previous_state.insert(path, result_state)

    def get_current_local_state(self, path: Path) -> FileMetadata | None:
        abs_path = self.client.sync_folder / path
        if not abs_path.is_file():
            return None
        return hash_file(abs_path, root_dir=self.client.sync_folder)

    def get_previous_local_state(self, path: Path) -> FileMetadata | None:
        return self.previous_state.states.get(path, None)

    def get_current_server_state(self, path: Path) -> FileMetadata | None:
        try:
            return get_metadata(self.client.server_client, path)
        except SyftServerError:
            return None
