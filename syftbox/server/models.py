from pydantic import BaseModel
from enum import Enum
from typing import Optional


import os

from syftbox.lib.lib import get_file_hash, get_file_last_modified


class FileChangeKind(Enum):
    CREATE: str = "create"
    # READ: str "read"
    WRITE: str = "write"
    # append?
    DELETE: str = "delete"


class FileChange(BaseModel):
    kind: FileChangeKind
    parent_path: str
    sub_path: str
    file_hash: str
    last_modified: float
    sync_folder: str | None = None

    @property
    def kind_write(self) -> bool:
        return self.kind in [FileChangeKind.WRITE, FileChangeKind.CREATE]

    @property
    def kind_delete(self) -> bool:
        return self.kind == FileChangeKind.DELETE

    @property
    def full_path(self) -> str:
        return self.sync_folder + "/" + self.parent_path + "/" + self.sub_path

    @property
    def internal_path(self) -> str:
        return self.parent_path + "/" + self.sub_path

    def hash_equal_or_none(self) -> bool:
        if not os.path.exists(self.full_path):
            return True

        local_file_hash = get_file_hash(self.full_path)
        return self.file_hash == local_file_hash

    def newer(self) -> bool:
        if not os.path.exists(self.full_path):
            return True

        local_last_modified = get_file_last_modified(self.full_path)
        if self.last_modified >= local_last_modified:
            return True

        return False

    def read(self) -> bytes:
        # if is_symlink(self.full_path):
        #     # write a text file with a syftlink
        #     data = convert_to_symlink(self.full_path).encode("utf-8")
        #     return data
        # else:
        with open(self.full_path, "rb") as f:
            return f.read()

    def write(self, data: bytes) -> bool:
        # if its a non private syftlink turn it into a symlink
        # if data.startswith(b"syft://") and not self.full_path.endswith(".private"):
        #     syft_link = SyftLink.from_url(data.decode("utf-8"))
        #     abs_path = os.path.join(
        #         os.path.abspath(self.sync_folder), syft_link.sync_path
        #     )
        #     if not os.path.exists(abs_path):
        #         raise Exception(
        #             f"Cant make symlink because source doesnt exist {abs_path}"
        #         )
        #     dir_path = os.path.dirname(self.full_path)
        #     os.makedirs(dir_path, exist_ok=True)
        #     if os.path.exists(self.full_path) and is_symlink(self.full_path):
        #         os.unlink(self.full_path)
        #     os.symlink(abs_path, self.full_path)
        #     os.utime(
        #         self.full_path,
        #         (self.last_modified, self.last_modified),
        #         follow_symlinks=False,
        #     )

        #     return True
        # else:
        return self.write_to(data, self.full_path)

    def delete(self) -> bool:
        try:
            os.unlink(self.full_path)
            return True
        except Exception as e:
            if "No such file" in str(e):
                return True
            print(f"Failed to delete file at {self.full_path}. {e}")
        return False

    def write_to(self, data: bytes, path: str) -> bool:
        base_dir = os.path.dirname(path)
        os.makedirs(base_dir, exist_ok=True)
        try:
            with open(path, "wb") as f:
                f.write(data)
            os.utime(
                path,
                (self.last_modified, self.last_modified),
                follow_symlinks=False,
            )
            return True
        except Exception as e:
            print("failed to write", path, e)
            return False


class WriteRequest(BaseModel):
    email: str
    change: FileChange
    is_directory: bool = False
    data: Optional[str] = None


class WriteResponse(BaseModel):
    accepted: bool
    change: FileChange
    status: str


class ListDatasitesResponse(BaseModel):
    datasites: list[str]
    status: str
