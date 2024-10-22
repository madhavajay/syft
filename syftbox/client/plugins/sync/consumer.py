import hashlib
from enum import Enum

import py_fast_rsync
from pydantic import BaseModel

from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem
from syftbox.client.plugins.sync.sync import SyncSide
from syftbox.lib.lib import Client
from syftbox.server.sync.hash import hash_file
from syftbox.server.sync.models import ApplyDiffRequest, DiffRequest, FileMetadata


class SyncDecisionType(Enum):
    NOOP = 0
    CREATE = 1
    MODIFY = 2
    DELETE = 3


class SyncInstruction(BaseModel):
    operation: SyncDecisionType
    diff: bytes | None

    # 1&2 (pull state from server)
    # a) local sends signature of their current state to remote (get_diff)
    # b) remote calculates difference and sends back to be updated blocks + desired hash
    # diff = py_fast_rsync.diff(local_contents, remote_signature)
    # c) check hash, apply locally

    # 3 (push state to server)
    # a) get signature from server (get metadata)
    # b) calculate diff locally
    # c) send diff and server applies + check (apply diff)


# class ModifiedSyncInstuction(BaseModel):
#     operation: SyncDecisionType = SyncDecisionType.MODIFY

#     @classmethod
#     def from_decision(cls):
#         pass

# original_state = b'''
# a
# b
# c
# e
# '''

# server = b'''
# a
# b
# c
# d  -> server change
# '''

# client = b'''
# a
# x -> client change
# c
# e
# '''

# server = b'''
# a
# b
# c
# d  -> server change
# '''

# 1. apply server state to local (in case of both modified)
# 2. apply server state to local (only server modified)
# 3. apply client state to server (only client modified)

# 1&2
# a) local sends signature of their current state to remote
# b) remote calculates difference and sends back to be updated blocks + desired hash
# diff = py_fast_rsync.diff(local_contents, remote_signature)
# c) check hash, apply locally

# 3
# a) get signature from server
# b) calculate diff locally
# c) send diff and server applies + check


class SyncDecision(BaseModel):
    operation: SyncDecisionType
    side_to_update: SyncSide
    local_metadata: FileMetadata
    remote_metadata: FileMetadata

    def execute(self, client):
        if self.decision_type == SyncDecisionType.CREATE:
            client.create(self.local_metadata.path, self.local_metadata.read())
        elif self.decision_type == SyncDecisionType.DELETE:
            client.delete(self.local_metadata.path)
        else:
            if self.side_to_update == SyncSide.LOCAL:
                # pass local path and signature
                diff_request = DiffRequest(
                    path=self.local_metadata.path,
                    signature=self.local_metadata.signature,
                )
                diff_result = client.get_diff(diff_request)
                desired_hash = diff_result.hash
                data_local = self.local_metadata.path.read()
                result = py_fast_rsync.apply(data_local, diff_result.diff)
                hash_result = hashlib.sha256(result).digest()
                # TODO: fallback
                assert hash_result == desired_hash
                self.metadata.path.write(result)
            elif self.side_to_update == SyncSide.REMOTE:
                data_local = self.local_metadata.read()
                diff = py_fast_rsync.diff(self.remote_metadata.signature, data_local)
                hash_local = hashlib.sha256(data_local).digest()
                # TODO: retries
                apply_diff_request = ApplyDiffRequest(
                    path=self.remote_metadata.path, diff=diff, expected_hash=hash_local
                )
                client.apply_diff(apply_diff_request)

    # a) get signature from server
    # b) calculate diff locally
    # c) send diff and server applies + check
    @classmethod
    def noop(
        cls,
        local_state: FileMetadata,
        remote_state: FileMetadata,
        side_to_update: SyncSide,
    ):
        return cls(
            SyncDecisionType.NOOP,
            side_to_update=side_to_update,
            local_metadata=local_state,
            remote_state=remote_state,
        )

    @classmethod
    def from_modified_states(
        cls,
        local_state: FileMetadata,
        remote_state: FileMetadata,
        side_to_update: SyncSide,
    ):
        """Asssumes at least on of the states is modified"""

        delete = (
            side_to_update == SyncSide.REMOTE
            and local_state.is_empty
            or side_to_update == SyncSide.LOCAL
            and remote_state.is_empty
        )

        create = (
            side_to_update == SyncSide.REMOTE
            and remote_state.is_empty
            or side_to_update == SyncSide.LOCAL
            and local_state.is_empty
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
        current_local_state: FileMetadata,
        previous_local_state: FileMetadata,
        current_remote_state: FileMetadata,
    ):
        local_modified = current_local_state != previous_local_state
        # TODO, make sure local state always is synced with server state after syncing
        remote_modified = previous_local_state == current_remote_state
        in_sync = current_remote_state == current_local_state
        conflict = local_modified and remote_modified and not in_sync

        if in_sync:
            return cls(
                remote_decision=SyncDecision.noop(), local_decision=SyncDecision.noop()
            )
        elif conflict:
            # in case of conflict we always use the server state, because it was updated earlier
            remote_decision = SyncDecision.noop()
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
                    local_decision=SyncDecision.noop(),
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
                    remote_decision=SyncDecision.noop(),
                )


class SyncConsumer:
    def __init__(self, client: Client, queue: SyncQueue):
        self.client = client
        self.queue = queue

    def consume_all(self):
        while not self.queue.empty():
            item = self.queue.get(timeout=0.1)
            try:
                self.process_filechange(item)
            except Exception as e:
                print(f"Failed to sync file {item.data.path}:\n{e}")

    def process_filechange(self, item: SyncQueueItem, client) -> None:
        path = item.data.path
        current_local_state: FileMetadata = self.get_current_local_state(path)
        previous_local_state = self.get_previous_local_state(path)
        # TODO, rename to remote
        current_server_state = self.get_current_server_state(
            client,
        )

        decision = SyncDecisionTuple.from_states(
            current_local_state, previous_local_state, current_server_state
        )

        decision.execute(self.client)

    def get_current_local_state(self, path) -> FileMetadata:
        return hash_file(path)

    def get_previous_local_state(self):
        pass

    def get_current_server_state(
        self,
    ):
        pass
