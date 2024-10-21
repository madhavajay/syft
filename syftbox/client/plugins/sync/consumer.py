import httpx
import py_fast_rsync

from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem
from syftbox.client.plugins.sync.sync import FileChangeInfo

from enum import Enum

from syftbox.server.sync.hash import hash_file
from syftbox.server.sync.models import FileMetadata
from pydantic import BaseModel


class SyncDecisionType(Enum):
    NOOP = 0
    CREATE = 1
    MODIFY = 2
    DELETE = 3


class SyncInstruction(BaseModel):
    operation: SyncDecisionType

class ModifiedSyncInstuction(BaseModel):
    operation: SyncDecisionType = SyncDecisionType.MODIFY

class SyncDecision(BaseModel):
    operation: SyncDecisionType
    diff: bytes | None

    @classmethod
    def noop(cls):
        return cls(SyncDecisionType.NOOP)

    @classmethod
    def noop(cls):
        return cls(SyncDecisionType.NOOP)

    @classmethod
    def create(cls):
        return cls(SyncDecisionType.CREATE)

    @classmethod
    def from_modified_states(
        cls, current_state: FileMetadata, target_state: FileMetadata
    ):
        """Asssumes at least on of the states is modified"""

        if target_state.is_empty:
            return SyncDecision.delete
        elif current_state.is_empty:
            return SyncDecision.create()
        else:
            local_contents = current_state.read()
            remote_contents = target_state.read()
            diff = py_fast_rsync.diff(local_contents, remote_contents)
            cls(SyncDecisionType.MODIFY, diff=diff)

        raise ValueError("This shouldnt happen")


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
                current_state=current_local_state, target_state=current_remote_state
            )
            return cls(remote_decision=remote_decision, local_decision=local_decision)
        else:
            # here we can assume only one party changed
            # assert (local_modified and not server_modified) or (server_modified and not local_modified)
            if local_modified:
                return cls(
                    local_decision=SyncDecision.noop(),
                    remote_decision=SyncDecision.from_modified_states(
                        current_state=current_remote_state,
                        target_state=current_local_state,
                    ),
                )
            else:
                return cls(
                    local_decision=SyncDecision.from_modified_states(
                        current_state=current_local_state,
                        target_state=current_remote_state,
                    ),
                    remote_decision=SyncDecision.noop(),
                )

        # When is there a conflict?
        # if both modified

        # If we can assume there is no conflict? what can we say
        # we just need to know who modified, if its us, we dont need to do anything
        # if its the server, we need to update locally

        # When is there a change locally?

        # return SyncDecision.noop()

    # @classmethod
    # def local_from_states(cls, current_local_state: FileMetadata, previous_local_state: FileMetadata, current_server_state: FileMetadata):
    #     local_change
    #     local_exists_unchanged

    #     if local_create:
    #         if current_server_state.not_exists:
    #             return SyncDecision.noop()
    #         elif current_server_state != current_local_state:
    #             pass
    #             # we fall back to the server state?
    #         else:
    #             return SyncDecision.noop()
    #     elif local_exists_unchanged:
    #         if current_server_state == current_local_state:
    #             return SyncDecision.noop()
    #         elif current_server_state.not_exists:
    #             return SyncDecision.delete
    #         else:
    #             return SyncDecision.modification
    #     elif local_not_exists_unchanged:
    #         if current_server_state.empty:
    #             return SyncDecision.noop
    #         else:
    #             return SyncDecision.create
    #     elif local_changed:


class SyncConsumer:
    def __init__(self, client: httpx.Client, queue: SyncQueue):
        self.client = client
        self.queue = queue

    def consume_all(self):
        while not self.queue.empty():
            item = self.queue.get()
            self.process_filechange(item)
            # - [ ] create remote/local
            # - [ ] delete remote/local
            # - [ ] modify (conflict)

    def process_filechange(self, item: SyncQueueItem) -> None:

        path = item.data.path
        current_local_state: FileMetadata = self.get_current_local_state(path)
        previous_local_state = self.get_previous_local_state(path)
        # TODO, rename to remote
        current_server_state = self.get_current_server_state()

        decision = SyncDecisionTuple.from_states(
            current_local_state, previous_local_state, current_server_state
        )

        # process locally
        # process serverside

    def process_local_change(self, sync_decision):
        pass

    def process_server_change(self, sync_decision):
        pass

    def get_current_local_state(self, path) -> FileMetadata:
        return hash_file(path)

    def get_previous_local_state(self):
        pass

    def get_current_server_state(self):
        pass
