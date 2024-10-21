from pathlib import Path

import pathspec

from syftbox.client.plugins.sync.sync import FileChangeInfo
from syftbox.lib import Client

# from syftbox.client.plugins.sync.constants import IGNORE_FILENAME

IGNORE_FILENAME = "_.syftignore"


def get_ignore_rules(client: Client) -> pathspec.PathSpec | None:
    ignore_file = Path(client.sync_folder) / IGNORE_FILENAME
    if ignore_file.is_file():
        with open(ignore_file) as f:
            lines = f.readlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    return None


def filter_changes(
    client: Client, changes: list[FileChangeInfo]
) -> list[FileChangeInfo]:
    ignore_rules = get_ignore_rules(client)
    if ignore_rules is None:
        return changes

    filtered_changes = []
    for change in changes:
        if not ignore_rules.match_file(change.path):
            filtered_changes.append(change)


def filter_paths(client: Client, paths: list[Path]) -> list[Path]:
    ignore_rules = get_ignore_rules(client)
    if ignore_rules is None:
        return paths

    filtered_paths = []
    for path in paths:
        if not ignore_rules.match_file(path):
            filtered_paths.append(path)

    return filtered_paths
