import base64
import hashlib
import re
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

from loguru import logger
from py_fast_rsync import signature

from syftbox.server.sync.models import FileMetadata


def hash_file(file_path: Path, root_dir: Path) -> FileMetadata:
    # ignore files larger then 100MB
    if file_path.stat().st_size > 100_000_000:
        logger.warning("File too large: %s", file_path)
        return str(file_path), None

    with open(file_path, "rb") as f:
        # not ideal for large files
        # but py_fast_rsync does not support files yet.
        # TODO: add support for streaming hashing
        data = f.read()

    relative_path = file_path.relative_to(root_dir)
    return FileMetadata(
        path=relative_path,
        hash=hashlib.sha256(data).hexdigest(),
        signature=base64.b85encode(signature.calculate(data)),
        file_size=len(data),
        last_modified=file_path.stat().st_mtime,
    )


def hash_files_parallel(files: list[Path], root_dir: Path) -> list[FileMetadata]:
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(partial(hash_file, root_dir=root_dir), files))
    return results


def hash_files(files: list[Path], root_dir: Path) -> list[FileMetadata]:
    return [hash_file(file, root_dir) for file in files]


def hash_dir(dir: Path, root_dir: Path) -> list[FileMetadata]:
    """
    hash all files in dir recursively, return a list of FileMetadata.

    ignore_folders should be relative to root_dir.
    returned Paths are relative to root_dir.
    """
    files = collect_files(dir)
    return hash_files_parallel(files, root_dir)


def collect_files(
    dir: Path | str, pattern: str | re.Pattern | None = None
) -> list[Path]:
    """Recursively collect files in a directory

    Examples:
        >>> # list all .syftperm files
        >>> collect_files(snapshot_dir, r".*/.syftperm")

        >>> # list all files in a directory info
        >>> collect_files(snapshot_dir, r".*")


    """
    dir = Path(dir)
    files = []

    # Compile the regex pattern if it's a string
    if isinstance(pattern, str):
        pattern = re.compile(pattern)

    for entry in dir.iterdir():
        if entry.is_file():
            if pattern is None or pattern.match(entry.as_posix()):
                files.append(entry)
        elif entry.is_dir():
            files.extend(collect_files(entry, pattern))

    return files
