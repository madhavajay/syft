import os
from enum import Enum
from pathlib import Path

from loguru import logger

from syftbox.client.plugins.sync.constants import (
    CLIENT_CHANGELOG_FOLDER,
    IGNORE_FOLDERS,
)
from syftbox.client.plugins.sync.endpoints import get_remote_state
from syftbox.lib import Client, DirState, FileInfo, hash_dir
from syftbox.server.models import SyftBaseModel


class SyncSide(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class FileChangeInfo(SyftBaseModel):
    path: Path
    side_last_modified: SyncSide
    date_last_modified: float
    date_local_modified: float | None = None
    date_remote_modified: float | None = None
    local_hash: str | None = None
    remote_hash: str | None = None
    num_bytes: int = 1  # TODO: get file size

    @property
    def priority(self) -> int:
        if self.path.name == "_.syftperm":
            return 0
        else:
            return self.num_bytes


class DatasiteState:
    def __init__(self, client: Client, datasite: str):
        """
        NOTE DatasiteState is not threadsafe, this should be handled by the caller
        """
        self.client = client
        self.datasite = datasite
        self.setup()

    @property
    def path(self) -> Path:
        p = Path(self.client.sync_folder) / self.datasite
        return p.expanduser().resolve()

    @property
    def changelog_file(self) -> Path:
        p = (
            Path(self.client.sync_folder)
            / CLIENT_CHANGELOG_FOLDER
            / f"{self.datasite}_changelog.json"
        )
        return p.expanduser().resolve()

    def setup(self):
        if self.changelog_file.exists():
            self.changelog = self.load_changelog()
        else:
            self.changelog = DirState(
                tree={},
                timestamp=0,
                sync_folder=self.client.sync_folder,
                sub_path=self.datasite,
            )
            self.changelog.save(self.changelog_file)

    def load_changelog(self) -> DirState:
        try:
            return DirState.load(str(self.changelog_file))
        except Exception as e:
            logger.exception(f"Failed to load changelog {self.changelog_file}: {e}")

    def set_changelog(self, state: DirState):
        self.changelog = state
        self.changelog.save(self.changelog_file)

    def get_current_state(self) -> DirState:
        return hash_dir(self.client.sync_folder, self.datasite, IGNORE_FOLDERS)

    def get_out_of_sync_files(
        self,
    ) -> tuple[list[FileChangeInfo], list[FileChangeInfo]]:
        """
        calculate the files that are out of sync

        NOTE: we are not handling local permissions here,
        they will be handled by the server and consumer
        TODO: we are not handling empty folders
        """
        local_state = self.get_current_state()
        remote_state = get_remote_state(self.client, self.datasite)

        all_changes = []
        all_files = set(local_state.tree.keys()) | set(remote_state.tree.keys())
        for afile in all_files:
            local_info = local_state.tree.get(afile)
            remote_info = remote_state.tree.get(afile)
            change_info = compare_fileinfo(afile, local_info, remote_info)
            if change_info is not None:
                all_changes.append(change_info)

        ignore_rules = get_ignore_rules(local_state)

        filtered_changes = filter_ignored_changes(all_changes, ignore_rules)
        permissions, changes = split_permissions(filtered_changes)
        # TODO debounce changes
        # filtered_changes = filter_recent_local_changes(filtered_changes)

        return permission_changes, file_changes


def compare_fileinfo(
    path: Path,
    local_info: FileInfo | None,
    remote_info: FileInfo | None,
) -> FileChangeInfo | None:
    if local_info is None:
        if remote_info is None:
            return None

        # File only exists on remote
        return FileChangeInfo(
            path=path,
            side_last_modified=SyncSide.REMOTE,
            date_last_modified=remote_info.last_modified,
            remote_hash=remote_info.file_hash,
        )

    if remote_info is None:
        # File only exists on local
        return FileChangeInfo(
            path=path,
            side_last_modified=SyncSide.LOCAL,
            date_last_modified=local_info.last_modified,
            local_hash=local_info.file_hash,
        )

    if local_info.file_hash != remote_info.file_hash:
        # File is different on both sides
        if local_info.last_modified > remote_info.last_modified:
            date_last_modified = local_info.last_modified
            side_last_modified = SyncSide.LOCAL
        else:
            date_last_modified = remote_info.last_modified
            side_last_modified = SyncSide.REMOTE

        return FileChangeInfo(
            path=path,
            side_last_modified=side_last_modified,
            date_last_modified=date_last_modified,
            local_hash=local_info.file_hash,
            remote_hash=remote_info.file_hash,
        )


def get_ignore_rules(dir_state: DirState) -> list[str, str, str]:
    """
    TODO refactor, abs/relative paths are not handled correctly
    returns a list of ignore rules (prefix, folder, ignore_file)
    """
    # get the ignore files
    syft_ignore_files = []
    folder_path = dir_state.sync_folder + "/" + dir_state.sub_path
    for afile, file_info in dir_state.tree.items():
        full_path = folder_path + "/" + afile
        sub_folder = os.path.dirname(full_path)

        if afile.endswith(".syftignore") and os.path.isfile(full_path):
            ignore_list = []
            with open(full_path) as f:
                ignore_list = f.readlines()
            for ignore_rule in ignore_list:
                ignore_rule = ignore_rule.strip()
                rule_prefix = sub_folder + "/" + ignore_rule
                syft_ignore_files.append((rule_prefix, sub_folder, afile))

    return syft_ignore_files


def filter_ignored_changes(
    all_changes: list[FileChangeInfo], ignore_rules: list[str, str, str]
) -> list[FileChangeInfo]:
    """
    Filter out changes that are ignored by .syftignore files
    """
    filtered_changes = []
    for change in all_changes:
        keep = True
        for rule_prefix, ignore_folder, ignore_file_path in ignore_rules:
            if change.path.startswith(rule_prefix):
                keep = False
                break
        if keep:
            filtered_changes.append(change)
    return filtered_changes


"""
fast thread
- selectively look at file changes from watchdog

slow thread
- loop through all datasites


producer:

for each local change:
    enqueue
    - can detect with watchdog
    - detect with loop over datasites
for each remote change:
    enqueue
    - detect with loop over datasites
"""
