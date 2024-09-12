import base64
import json
import os
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

USER_GROUP_GLOBAL = "GLOBAL"


def perm_file_path(path: str) -> str:
    return f"{path}/_.syftperm"


def is_primitive_json_serializable(obj):
    if isinstance(obj, (list, dict, str, int, float, bool, type(None))):
        return True
    return False


def pack(obj) -> Any:
    if is_primitive_json_serializable(obj):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    raise Exception(f"Unable to pack type: {type(obj)} value: {obj}")


class Jsonable:
    def to_dict(self) -> dict:
        output = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            output[k] = pack(v)
        return output

    def __iter__(self):
        for key, val in self.to_dict().items():
            if key.startswith("_"):
                yield key, val

    def __getitem__(self, key):
        if key.startswith("_"):
            return None
        return self.to_dict()[key]

    @classmethod
    def load(cls, filepath: str) -> Self:
        try:
            with open(filepath) as f:
                data = f.read()
                d = json.loads(data)
                return cls(**d)
        except Exception as e:
            print(f"Unable to load file: {filepath}. {e}")
        return None

    def save(self, filepath: str) -> None:
        d = self.to_dict()
        with open(filepath, "w") as f:
            f.write(json.dumps(d))


@dataclass
class SyftPermission(Jsonable):
    admin: list[str]
    read: list[str]
    write: list[str]
    filepath: str | None = None

    def __repr__(self) -> str:
        string = "SyftPermission:\n"
        string += f"{self.filepath}\n"
        string += "ADMIN: ["
        for v in self.admin:
            string += v + ", "
        string += "]\n"

        string += "READ: ["
        for r in self.read:
            string += r + ", "
        string += "]\n"

        string += "WRITE: ["
        for w in self.write:
            string += w + ", "
        string += "]\n"
        return string


def bintostr(binary_data):
    return base64.b85encode(zlib.compress(binary_data)).decode("utf-8")


def strtobin(encoded_data):
    return zlib.decompress(base64.b85decode(encoded_data.encode("utf-8")))


class FileChangeKind(Enum):
    CREATE: str = "create"
    # READ: str "read"
    WRITE: str = "write"
    # append?
    DELETE: str = "delete"


@dataclass
class FileChange(Jsonable):
    kind: FileChangeKind
    parent_path: str
    sub_path: str
    file_hash: str
    sync_folder: str | None = None

    @property
    def kind_write(self) -> bool:
        return self.kind in [FileChangeKind.WRITE, FileChangeKind.CREATE]

    @property
    def kind_delete(self) -> bool:
        return self.kind == FileChangeKind.DELETE

    def to_dict(self) -> dict:
        output = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if k == "kind":
                v = v.value
            output[k] = pack(v)
        return output

    @property
    def full_path(self) -> str:
        return self.sync_folder + "/" + self.parent_path + "/" + self.sub_path

    @property
    def internal_path(self) -> str:
        return self.parent_path + "/" + self.sub_path

    def read(self) -> bytes:
        with open(self.full_path, "rb") as f:
            return f.read()

    def write(self, data: bytes) -> bool:
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
            return True
        except Exception as e:
            print("failed to write", path, e)
            return False
