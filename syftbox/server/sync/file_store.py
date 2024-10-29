from pathlib import Path

from pydantic import BaseModel

from syftbox.server.settings import ServerSettings
from syftbox.server.sync import db
from syftbox.server.sync.db import get_db
from syftbox.server.sync.models import AbsolutePath, FileMetadata, RelativePath


class SyftFile(BaseModel):
    metadata: FileMetadata
    data: bytes
    absolute_path: AbsolutePath


class FileStore:
    def __init__(self, server_settings: ServerSettings) -> None:
        self.server_settings = server_settings

    @property
    def db_path(self) -> AbsolutePath:
        return self.server_settings.file_db_path

    def copy(self, from_path: Path, to_path: Path) -> None:
        pass

    def delete(self, path: RelativePath) -> None:
        conn = get_db(self.db_path)
        with conn:
            db.delete_file_metadata(conn, str(path))
            abs_path = self.server_settings.snapshot_folder / path
            abs_path.unlink(missing_ok=True)

    def get(self, path: RelativePath) -> SyftFile:
        conn = get_db(self.db_path)
        with conn:
            metadata = db.get_metadata(conn, path=str(path))
            abs_path = self.server_settings.snapshot_folder / metadata.path
            return SyftFile(metadata=metadata, data=self._read_bytes(abs_path), absolute_path=abs_path)

    def _read_bytes(self, path: AbsolutePath) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def put(self, path: Path, data: bytes) -> None:
        pass

    def list(self, path: Path) -> list[Path]:
        pass
