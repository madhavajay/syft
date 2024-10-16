import hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from loguru import logger


def hash_file(file_path: str) -> tuple[str, str]:
    try:
        with open(file_path, "rb") as f:
            sha256_hash = hashlib.file_digest(f, "sha256")
            return str(file_path), sha256_hash.hexdigest()
    except FileNotFoundError:
        logger.debug("File not found: %s", file_path)
        return str(file_path), None


def hash_files_parallel(files):
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
