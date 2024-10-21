from pathlib import Path

from syftbox.client.plugins.sync.constants import IGNORE_FILENAME
from syftbox.client.plugins.sync.ignore import filter_paths
from syftbox.lib.lib import Client

ignore_file = """
# Exlude alice datasite
/alice@example.com

# exclude all occurrences bob@example.com
bob@example.com

# Exclude all "large" folders under any datasite
*/large/*

# Include important_file.pdf under excluded folder
!/john@example.com/large/important_file.pdf

# General excludes
*.tmp
_.syftignore
*.py[cod]
"""

paths_with_result = [
    # Should be ignored
    ("alice@example.com/file1.txt", True),
    ("john@example.com/results/bob@example.com/file1.txt", True),
    ("john@example.com/large/file1.txt", True),
    ("john@example.com/docs/file1.tmp", True),
    ("script.pyc", True),
    # Should not be ignored
    ("john@example.com/results/alice@example.com/file1.txt", False),
    ("john@example.com/large/important_file.pdf", False),
    ("john@example.com/docs/file3.pdf", False),
    ("script.py", False),
]


def test_ignore_file(datasite_1: Client):
    # without ignore file
    paths, results = zip(*paths_with_result)
    paths = [Path(p) for p in paths]
    filtered_paths = filter_paths(datasite_1, paths)
    assert filtered_paths == paths

    # with ignore file
    ignore_path = Path(datasite_1.sync_folder) / IGNORE_FILENAME
    ignore_path.write_text(ignore_file)

    expected_result = [p for p, r in zip(paths, results) if r is False]
    filtered_paths = filter_paths(datasite_1, paths)
    assert filtered_paths == expected_result
