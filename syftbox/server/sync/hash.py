import base64
import hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from loguru import logger
from py_fast_rsync import signature

from syftbox.server.sync.models import FileMetadata


def hash_file(snapshot_folder: Path, file_path: Path) -> FileMetadata:
    # ignore files larger then 100MB
    if file_path.stat().st_size > 100_000_000:
        logger.warning("File too large: %s", file_path)
        return str(file_path), None

    with open(file_path, "rb") as f:
        # not ideal for large files
        # but py_fast_rsync does not support files yet.
        # TODO: add support for streaming hashing
        data = f.read()

    return FileMetadata(
        relative_path=file_path.relative_to(snapshot_folder),
        path=file_path,
        hash=hashlib.sha256(data).hexdigest(),
        signature=base64.b85encode(signature.calculate(data)),
        file_size=len(data),
        last_modified=file_path.stat().st_mtime,
    )


def hash_files_parallel(files: list[str]):
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(hash_file, files))
    return results


def collect_files(dir: Path | str) -> list[Path]:
    dir = Path(dir)
    files = []
    for entry in dir.iterdir():
        if entry.is_file():
            files.append(entry)
        elif entry.is_dir():
            files.extend(collect_files(entry))
    return files
