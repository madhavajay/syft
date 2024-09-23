from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json
import os
import pkgutil
import re
import shutil
import subprocess
import sys
import sysconfig
import textwrap
import threading
import types
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import markdown
import pandas as pd
import pkg_resources
import requests
from typing_extensions import Self

USER_GROUP_GLOBAL = "GLOBAL"

ICON_FILE = "Icon"  # special
IGNORE_FILES = []


def perm_file_path(path: str) -> str:
    return f"{path}/_.syftperm"


def is_primitive_json_serializable(obj):
    if isinstance(obj, (str, int, float, bool, type(None))):
        return True
    return False


def pack(obj) -> Any:
    if is_primitive_json_serializable(obj):
        return obj

    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    if isinstance(obj, list):
        return [pack(val) for val in obj]

    if isinstance(obj, dict):
        return {k: pack(v) for k, v in obj.items()}

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
            raise e
            print(f"Unable to load jsonable file: {filepath}. {e}")
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
    terminal: bool = False

    @classmethod
    def datasite_default(cls, email: str) -> Self:
        return SyftPermission(
            admin=[email],
            read=[email],
            write=[email],
        )

    def __eq__(self, other):
        if not isinstance(other, SyftPermission):
            return NotImplemented
        return (
            self.admin == other.admin
            and self.read == other.read
            and self.write == other.write
            and self.filepath == other.filepath
            and self.terminal == other.terminal
        )

    def perm_path(self, path=None) -> str:
        if path is not None:
            self.filepath = path

        if self.filepath is None:
            raise Exception(f"Saving requites a path: {self}")

        if os.path.isdir(self.filepath):
            self.filepath = perm_file_path(self.filepath)
        return self.filepath

    def save(self, path=None) -> bool:
        self.perm_path(path=path)
        if self.filepath.endswith(".syftperm"):
            super().save(self.filepath)
        else:
            raise Exception(f"Perm file must end in .syftperm. {self.filepath}")
        return True

    def ensure(self, path=None) -> bool:
        # make sure the contents matches otherwise write it
        self.perm_path(path=path)
        try:
            prev_perm_file = SyftPermission.load(self.filepath)
            if self == prev_perm_file:
                # no need to write
                return True
        except Exception:
            pass
        return self.save(path)

    @classmethod
    def no_permission(self) -> Self:
        return SyftPermission(admin=[], read=[], write=[])

    @classmethod
    def mine_no_permission(self, email: str) -> Self:
        return SyftPermission(admin=[email], read=[], write=[])

    @classmethod
    def mine_with_public_read(self, email: str) -> Self:
        return SyftPermission(admin=[email], read=[email, "GLOBAL"], write=[email])

    @classmethod
    def mine_with_public_write(self, email: str) -> Self:
        return SyftPermission(
            admin=[email], read=[email, "GLOBAL"], write=[email, "GLOBAL"]
        )

    @classmethod
    def theirs_with_my_read(self, their_email, my_email: str) -> Self:
        return SyftPermission(
            admin=[their_email], read=[their_email, my_email], write=[their_email]
        )

    @classmethod
    def theirs_with_my_read_write(self, their_email, my_email: str) -> Self:
        return SyftPermission(
            admin=[their_email],
            read=[their_email, my_email],
            write=[their_email, my_email],
        )

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
    last_modified: float
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
        if is_symlink(self.full_path):
            # write a text file with a syftlink
            data = convert_to_symlink(self.full_path).encode("utf-8")
            return data
        else:
            with open(self.full_path, "rb") as f:
                return f.read()

    def write(self, data: bytes) -> bool:
        # if its a non private syftlink turn it into a symlink
        if data.startswith(b"syft://") and not self.full_path.endswith(".private"):
            syft_link = SyftLink.from_url(data.decode("utf-8"))
            abs_path = os.path.join(
                os.path.abspath(self.sync_folder), syft_link.sync_path
            )
            if not os.path.exists(abs_path):
                raise Exception(
                    f"Cant make symlink because source doesnt exist {abs_path}"
                )
            dir_path = os.path.dirname(self.full_path)
            os.makedirs(dir_path, exist_ok=True)
            if os.path.exists(self.full_path) and is_symlink(self.full_path):
                os.unlink(self.full_path)
            os.symlink(abs_path, self.full_path)
            os.utime(
                self.full_path,
                (self.last_modified, self.last_modified),
                follow_symlinks=False,
            )

            return True
        else:
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


@dataclass
class DirState(Jsonable):
    tree: dict[str, FileInfo]
    timestamp: float
    sync_folder: str
    sub_path: str


def get_symlink(file_path) -> str:
    return os.readlink(file_path)


def is_symlink(file_path) -> bool:
    return os.path.islink(file_path)


def symlink_to_syftlink(file_path):
    return SyftLink.from_path(file_path)


def convert_to_symlink(path):
    if not is_symlink(path):
        raise Exception(f"Cant convert a non symlink {path}")
    abs_path = get_symlink(path)
    syft_link = symlink_to_syftlink(abs_path)
    return str(syft_link)


def get_file_last_modified(file_path: str) -> float:
    return os.path.getmtime(file_path)


def get_file_hash(file_path: str) -> str:
    if is_symlink(file_path):
        # return the hash of the syftlink instead
        sym_link_string = convert_to_symlink(file_path)
        return hashlib.md5(sym_link_string.encode("utf-8")).hexdigest()
    else:
        with open(file_path, "rb") as file:
            return hashlib.md5(file.read()).hexdigest()


def ignore_dirs(directory: str, root: str, ignore_folders=None) -> bool:
    if ignore_folders is not None:
        for ignore_folder in ignore_folders:
            if root.endswith(ignore_folder):
                return True
    return False


@dataclass
class FileInfo(Jsonable):
    file_hash: str
    last_modified: float


def hash_dir(
    sync_folder: str,
    sub_path: str,
    ignore_folders: list | None = None,
) -> DirState:
    state_dict = {}
    full_path = os.path.join(sync_folder, sub_path)
    for root, dirs, files in os.walk(full_path):
        if not ignore_dirs(full_path, root, ignore_folders):
            for file in files:
                if not ignore_file(full_path, root, file):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, full_path)
                    file_info = FileInfo(
                        file_hash=get_file_hash(path),
                        last_modified=get_file_last_modified(path),
                    )
                    state_dict[rel_path] = file_info

    utc_unix_timestamp = datetime.now().timestamp()
    dir_state = DirState(
        tree=state_dict,
        timestamp=utc_unix_timestamp,
        sync_folder=sync_folder,
        sub_path=sub_path,
    )
    return dir_state


def ignore_file(directory: str, root: str, filename: str) -> bool:
    if directory == root:
        if filename.startswith(ICON_FILE):
            return True
        if filename in IGNORE_FILES:
            return True
    if filename == ".DS_Store":
        return True
    return False


def get_datasites(sync_folder: str) -> list[str]:
    datasites = []
    folders = os.listdir(sync_folder)
    for folder in folders:
        if "@" in folder:
            datasites.append(folder)
    return datasites


def build_tree_string(paths_dict, prefix=""):
    lines = []
    items = list(paths_dict.items())

    for index, (key, value) in enumerate(items):
        # Determine if it's the last item in the current directory level
        connector = "└── " if index == len(items) - 1 else "├── "
        lines.append(f"{prefix}{connector}{repr(key)}")

        # Prepare the prefix for the next level
        if isinstance(value, dict):
            extension = "    " if index == len(items) - 1 else "│   "
            lines.append(build_tree_string(value, prefix + extension))

    return "\n".join(lines)


@dataclass
class PermissionTree(Jsonable):
    tree: dict[str, SyftPermission]
    parent_path: str
    root_perm: SyftPermission | None

    @classmethod
    def from_path(cls, parent_path) -> Self:
        perm_dict = {}
        for root, dirs, files in os.walk(parent_path):
            for file in files:
                if file.endswith(".syftperm"):
                    path = os.path.join(root, file)
                    perm_dict[path] = SyftPermission.load(path)

        root_perm = None
        root_perm_path = perm_file_path(parent_path)
        if root_perm_path in perm_dict:
            root_perm = perm_dict[root_perm_path]

        return PermissionTree(
            root_perm=root_perm, tree=perm_dict, parent_path=parent_path
        )

    @property
    def root_or_default(self) -> SyftPermission:
        if self.root_perm:
            return self.root_perm
        return SyftPermission.no_permission()

    def permission_for_path(self, path: str) -> SyftPermission:
        parent_path = os.path.normpath(self.parent_path)
        current_perm = self.root_or_default

        # default
        if parent_path not in path:
            return current_perm

        sub_path = path.replace(parent_path, "")
        current_perm_level = parent_path
        for part in sub_path.split("/"):
            if part == "":
                continue

            current_perm_level += "/" + part
            next_perm_file = perm_file_path(current_perm_level)
            if next_perm_file in self.tree:
                # we could do some overlay with defaults but
                # for now lets just use a fully defined overwriting perm file
                next_perm = self.tree[next_perm_file]
                current_perm = next_perm

            if current_perm.terminal:
                return current_perm

        return current_perm

    def __repr__(self) -> str:
        return f"PermissionTree: {self.parent_path}\n" + build_tree_string(self.tree)


def filter_read_state(user_email: str, dir_state: DirState, perm_tree: PermissionTree):
    filtered_tree = {}
    root_dir = dir_state.sync_folder + "/" + dir_state.sub_path
    for file_path, file_info in dir_state.tree.items():
        full_path = root_dir + "/" + file_path
        perm_file_at_path = perm_tree.permission_for_path(full_path)
        if (
            user_email in perm_file_at_path.read
            or "GLOBAL" in perm_file_at_path.read
            or user_email in perm_file_at_path.admin
        ):
            filtered_tree[file_path] = file_info
    return filtered_tree


def validate_email(email: str) -> bool:
    # Define a regex pattern for a valid email
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    # Use the match method to check if the email fits the pattern
    if re.match(email_regex, email):
        return True
    return False


def extract_leftmost_email(text: str) -> str:
    # Define a regex pattern to match an email address
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"

    # Search for all matches of the email pattern in the text
    matches = re.findall(email_regex, text)

    # Return the first match, which is the left-most email
    if matches:
        return matches[0]
    return None


class Dataset:
    sync_path: str


@dataclass
class DatasiteManifest(Jsonable):
    datasite: str
    file_path: str
    datasets: dict = field(default_factory=dict)
    code: dict = field(default_factory=dict)

    @classmethod
    def load_from_datasite(cls, path: str) -> DatasiteManifest | None:
        datasite_path = Path(os.path.abspath(path))
        manifest_path = datasite_path / "manifest" / "manifest.json"
        try:
            manifest = DatasiteManifest.load(manifest_path)
            return manifest
        except Exception:
            pass
        return None

    @classmethod
    def create_manifest(cls, path: str, email: str):
        # make a dir and set the permissions
        manifest_dir = os.path.dirname(path)
        os.makedirs(manifest_dir, exist_ok=True)

        public_read = SyftPermission.mine_with_public_read(email=email)
        public_read.save(manifest_dir)

        datasite_manifest = DatasiteManifest(datasite=email, file_path=path)
        datasite_manifest.save(path)
        return datasite_manifest

    def create_folder(self, path: str, permission: SyftPermission):
        os.makedirs(path, exist_ok=True)
        permission.save(path)

    @property
    def root_dir(self) -> Path:
        root_dir = Path(os.path.abspath(os.path.dirname(self.file_path) + "/../"))
        return root_dir

    def create_public_folder(self, path: str):
        full_path = self.root_dir / path
        os.makedirs(str(full_path), exist_ok=True)
        public_read = SyftPermission.mine_with_public_read(email=self.datasite)
        public_read.save(full_path)
        return Path(full_path)

    def publish(self, item, overwrite: bool = False):
        if isinstance(item, Callable):
            syftbox_code(item).publish(self, overwrite=overwrite)


@dataclass
class ClientConfig(Jsonable):
    config_path: Path
    sync_folder: Path | None = None
    port: int | None = None
    email: str | None = None
    token: int | None = None
    server_url: str = "http://localhost:5001"
    email_token: str | None = None

    def save(self, path: str | None = None) -> None:
        if path is None:
            path = self.config_path
        super().save(path)

    @property
    def datasite_path(self) -> Path:
        return os.path.join(self.sync_folder, self.email)

    @property
    def manifest_path(self) -> Path:
        return os.path.join(self.datasite_path, "manifest/manifest.json")

    @property
    def manifest(self) -> DatasiteManifest:
        datasite_manifest = None
        try:
            datasite_manifest = DatasiteManifest.load(self.manifest_path)
        except Exception:
            datasite_manifest = DatasiteManifest.create_manifest(
                path=self.manifest_path, email=self.email
            )

        return datasite_manifest

    def get_datasites(self: str) -> list[str]:
        datasites = []
        folders = os.listdir(self.sync_folder)
        for folder in folders:
            if "@" in folder:
                datasites.append(folder)
        return datasites

    def get_all_manifests(self):
        manifests = {}
        for datasite in get_datasites(self.sync_folder):
            datasite_path = Path(self.sync_folder + "/" + datasite)
            datasite_manifest = DatasiteManifest.load_from_datasite(datasite_path)
            if datasite_manifest:
                manifests[datasite] = datasite_manifest
        return manifests

    def get_datasets(self):
        manifests = self.get_all_manifests()
        datasets = []
        for datasite, manifest in manifests.items():
            for dataset_name, dataset_dict in manifest.datasets.items():
                try:
                    dataset = TabularDataset(**dataset_dict)
                    dataset.syft_link = SyftLink(**dataset_dict["syft_link"])
                    dataset.readme_link = SyftLink(**dataset_dict["readme_link"])
                    dataset.loader_link = SyftLink(**dataset_dict["loader_link"])
                    dataset._client_config = self
                    datasets.append(dataset)
                except Exception as e:
                    print(f"Bad dataset format. {datasite} {e}")

        return DatasetResults(datasets)

    def get_code(self):
        manifests = self.get_all_manifests()
        all_code = []
        for datasite, manifest in manifests.items():
            for func_name, code_dict in manifest.code.items():
                try:
                    code = Code(**code_dict)
                    code.syft_link = SyftLink(**code_dict["syft_link"])
                    code.readme_link = SyftLink(**code_dict["readme_link"])
                    code.requirements_link = SyftLink(**code_dict["requirements_link"])
                    code._client_config = self
                    all_code.append(code)
                except Exception as e:
                    print(f"Bad dataset format. {datasite} {e}")

        return CodeResults(all_code)

    def resolve_link(self, link: SyftLink) -> Path:
        return Path(os.path.join(os.path.abspath(self.sync_folder), link.sync_path))

    def use(self):
        os.environ["SYFTBOX_CURRENT_CLIENT"] = self.config_path
        os.environ["SYFTBOX_SYNC_DIR"] = self.sync_folder
        print(f"> Setting Sync Dir to: {self.sync_folder}")


class ResettableTimer:
    def __init__(self, timeout, callback, *args, **kwargs):
        self.timeout = timeout
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.timer = None
        self.lock = threading.Lock()

    def _run_callback(self):
        with self.lock:
            self.timer = None
        self.callback(*self.args, **self.kwargs)

    def start(self, *args, **kwargs):
        with self.lock:
            if self.timer:
                self.timer.cancel()

            # If new arguments are passed in start, they will overwrite the initial ones
            if args or kwargs:
                self.args = args
                self.kwargs = kwargs

            self.timer = threading.Timer(self.timeout, self._run_callback)
            self.timer.start()

    def cancel(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None


class SharedState:
    def __init__(self, client_config: ClientConfig):
        self.data = {}
        self.lock = Lock()
        self.client_config = client_config
        self.timers: dict[str:ResettableTimer] = {}
        self.fs_events = []

    @property
    def sync_folder(self) -> str:
        return self.client_config.sync_folder

    def get(self, key, default=None):
        with self.lock:
            if key == "my_datasites":
                return self._get_datasites()
            return self.data.get(key, default)

    def set(self, key, value):
        with self.lock:
            self.data[key] = value

    def _get_datasites(self):
        syft_folder = self.data.get(self.client_config.sync_folder)
        if not syft_folder or not os.path.exists(syft_folder):
            return []

        return [
            folder
            for folder in os.listdir(syft_folder)
            if os.path.isdir(os.path.join(syft_folder, folder))
        ]


def get_root_data_path() -> Path:
    # get the PySyft / data directory to share datasets between notebooks
    # on Linux and MacOS the directory is: ~/.syft/data"
    # on Windows the directory is: C:/Users/$USER/.syft/data

    data_dir = Path.home() / ".syft" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    return data_dir


def autocache(
    url: str, extension: str | None = None, cache: bool = True
) -> Path | None:
    try:
        data_path = get_root_data_path()
        file_hash = hashlib.sha256(url.encode("utf8")).hexdigest()
        filename = file_hash
        if extension:
            filename += f".{extension}"
        file_path = data_path / filename
        if os.path.exists(file_path) and cache:
            return file_path
        return download_file(url, file_path)
    except Exception as e:
        print(f"Failed to autocache: {url}. {e}")
        return None


def download_file(url: str, full_path: str | Path) -> Path | None:
    full_path = Path(full_path)
    if not full_path.exists():
        r = requests.get(url, allow_redirects=True, verify=verify_tls())  # nosec
        if not r.ok:
            print(f"Got {r.status_code} trying to download {url}")
            return None
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(r.content)
    return full_path


def verify_tls() -> bool:
    return not str_to_bool(str(os.environ.get("IGNORE_TLS_ERRORS", "0")))


def str_to_bool(bool_str: str | None) -> bool:
    result = False
    bool_str = str(bool_str).lower()
    if bool_str == "true" or bool_str == "1":
        result = True
    return result


@dataclass
class SyftLink(Jsonable):
    @classmethod
    def from_file(cls, path: str) -> SyftLink:
        if not os.path.exists(path):
            raise Exception(f"{path} does not exist")
        with open(path, "r") as f:
            return cls.from_url(f.read())

    def from_path(path: str) -> SyftLink | None:
        parts = []
        collect = False
        for part in str(path).split("/"):
            # quick hack find the first email and thats the datasite
            if collect:
                parts.append(part)
            elif validate_email(part):
                collect = True
                parts.append(part)

        if len(parts):
            sync_path = "/".join(parts)
            return SyftLink.from_url(f"syft://{sync_path}")
        return None

    @classmethod
    def from_url(cls, url: str | SyftLink) -> SyftLink:
        if isinstance(url, SyftLink):
            return url
        try:
            # urlparse doesnt handle no protocol properly
            if "://" not in url:
                url = "http://" + url
            parts = urlparse(url)
            host_or_ip_parts = parts.netloc.split(":")
            # netloc is host:port
            port = 80
            if len(host_or_ip_parts) > 1:
                port = int(host_or_ip_parts[1])
            host_or_ip = host_or_ip_parts[0]
            if parts.scheme == "https":
                port = 443

            return SyftLink(
                host_or_ip=host_or_ip,
                path=parts.path,
                port=port,
                protocol=parts.scheme,
                query=getattr(parts, "query", ""),
            )
        except Exception as e:
            raise e

    def to_file(self, path: str) -> bool:
        with open(path, "w") as f:
            f.write(str(self))

    def __init__(
        self,
        protocol: str = "http",
        host_or_ip: str = "localhost",
        port: int | None = 5001,
        path: str = "",
        query: str = "",
    ) -> None:
        # in case a preferred port is listed but its not clear if an alternative
        # port was included in the supplied host_or_ip:port combo passed in earlier
        match_port = re.search(":[0-9]{1,5}", host_or_ip)
        if match_port:
            sub_server_url: SyftLink = SyftLink.from_url(host_or_ip)
            host_or_ip = str(sub_server_url.host_or_ip)  # type: ignore
            port = int(sub_server_url.port)  # type: ignore
            protocol = str(sub_server_url.protocol)  # type: ignore
            path = str(sub_server_url.path)  # type: ignore

        prtcl_pattrn = "://"
        if prtcl_pattrn in host_or_ip:
            protocol = host_or_ip[: host_or_ip.find(prtcl_pattrn)]
            start_index = host_or_ip.find(prtcl_pattrn) + len(prtcl_pattrn)
            host_or_ip = host_or_ip[start_index:]

        self.host_or_ip = host_or_ip
        self.path: str = path
        self.port = port
        self.protocol = protocol
        self.query = query

    def with_path(self, path: str) -> Self:
        dupe = copy.copy(self)
        dupe.path = path
        return dupe

    @property
    def query_string(self) -> str:
        query_string = ""
        if len(self.query) > 0:
            query_string = f"?{self.query}"
        return query_string

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.path}{self.query_string}"

    @property
    def url_no_port(self) -> str:
        return f"{self.base_url_no_port}{self.path}{self.query_string}"

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host_or_ip}:{self.port}"

    @property
    def base_url_no_port(self) -> str:
        return f"{self.protocol}://{self.host_or_ip}"

    @property
    def url_no_protocol(self) -> str:
        return f"{self.host_or_ip}:{self.port}{self.path}"

    @property
    def url_path(self) -> str:
        return f"{self.path}{self.query_string}"

    def to_tls(self) -> Self:
        if self.protocol == "https":
            return self

        # TODO: only ignore ssl in dev mode
        r = requests.get(  # nosec
            self.base_url, verify=verify_tls()
        )  # ignore ssl cert if its fake
        new_base_url = r.url
        if new_base_url.endswith("/"):
            new_base_url = new_base_url[0:-1]
        return self.__class__.from_url(
            url=f"{new_base_url}{self.path}{self.query_string}"
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.url}>"

    def __str__(self) -> str:
        return self.url

    def __hash__(self) -> int:
        return hash(self.__str__())

    def __copy__(self) -> Self:
        return self.__class__.from_url(self.url)

    def set_port(self, port: int) -> Self:
        self.port = port
        return self

    @property
    def sync_path(self) -> str:
        return self.host_or_ip + self.path

    @property
    def datasite(self) -> str:
        return extract_leftmost_email(str(self))


@dataclass
class SyftVault(Jsonable):
    mapping: dict

    @classmethod
    def reset(cls) -> None:
        print("> Resetting Vault")
        vault = cls.load_vault()
        vault.mapping = {}
        vault.save_vault()

    @classmethod
    def load_vault(cls, override_path: str | None = None) -> SyftVault:
        vault_file_path = "~/.syft/vault.json"
        if override_path:
            vault_file_path = override_path
        vault_file_path = os.path.abspath(os.path.expanduser(vault_file_path))
        vault = cls.load(vault_file_path)
        if vault is None:
            vault = SyftVault(mapping={})
            vault.save(vault_file_path)
        return vault

    def save_vault(self, override_path: str | None = None) -> bool:
        try:
            vault_file_path = "~/.syft/vault.json"
            if override_path:
                vault_file_path = override_path
            vault_file_path = os.path.abspath(os.path.expanduser(vault_file_path))
            self.save(vault_file_path)
            return True
        except Exception as e:
            print("Failed to write vault", e)
        return False

    def set_private(self, public: SyftLink, private_path: str) -> bool:
        self.mapping[public.sync_path] = private_path
        return True

    def get_private(self, public: SyftLink) -> str:
        public = public.sync_path
        # bug where .private is getting added to the internal link content need to fix
        private_extension = ".private"
        if public.endswith(private_extension):
            public = public[: -len(private_extension)]
        if public in self.mapping:
            return self.mapping[public]
        return None

    @classmethod
    def link_private(cls, public_path: str, private_path: str) -> bool:
        syft_link = SyftLink.from_path(public_path)
        link_file_path = syftlink_private_path(public_path)
        syft_link.to_file(link_file_path)
        vault = cls.load_vault()
        vault.set_private(syft_link, private_path)
        vault.save_vault()
        return True


def syftlink_path(path):
    return f"{path}.syftlink"


def syftlink_private_path(path):
    return f"{path}.private"


def sy_path(path, resolve_private: bool | None = None):
    if resolve_private is None:
        resolve_private = str_to_bool(os.environ.get("RESOLVE_PRIVATE", "False"))

    if not os.path.exists(path):
        raise Exception(f"No file at: {path}")
    if resolve_private:
        link_path = syftlink_private_path(path)
        if not os.path.exists(link_path):
            raise Exception(f"No private link at: {link_path}")
        syft_link = SyftLink.from_file(link_path)
        vault = SyftVault.load_vault()
        private_path = vault.get_private(syft_link)
        print("> 🕵️‍♀️ Resolved private link", private_path)
        return private_path
    return path


def datasite(sync_path: str | None, datasite: str):
    return os.path.join(sync_path, datasite)


def extract_datasite(sync_import_path: str) -> str:
    datasite_parts = []
    for part in sync_import_path.split("."):
        if part in ["datasets", "code"]:
            break

        datasite_parts.append(part)
    email_string = ".".join(datasite_parts)
    email_string = email_string.replace(".at.", "@")
    return email_string


def create_datasite_import_path(datasite: str) -> str:
    # Replace '@' with '.at.'
    import_path = datasite.replace("@", ".at.")
    # Append '.datasets' to the import path
    return import_path


def attrs_for_datasite_dataset_import(module, sync_import_path: str) -> dict[str, Any]:
    import os

    client_config_path = os.environ.get("SYFTBOX_CURRENT_CLIENT", None)
    if client_config_path is None:
        raise Exception("run client_config.use()")
    client_config = ClientConfig.load(client_config_path)

    datasite = extract_datasite(sync_import_path)
    datasite_path = os.path.join(client_config.sync_folder, datasite)
    datasets = []
    try:
        manifest = DatasiteManifest.load_from_datasite(datasite_path)
        if hasattr(manifest, "datasets"):
            for dataset_name, dataset_dict in manifest.datasets.items():
                try:
                    dataset = TabularDataset(**dataset_dict)
                    dataset.syft_link = SyftLink(**dataset_dict["syft_link"])
                    dataset.readme_link = SyftLink(**dataset_dict["readme_link"])
                    dataset.loader_link = SyftLink(**dataset_dict["loader_link"])
                    dataset._client_config = client_config
                    datasets.append(dataset)
                    setattr(module, dataset.clean_name, dataset)
                except Exception as e:
                    print(f"Bad dataset format. {datasite} {e}")
    except Exception:
        pass

    dataset_results = DatasetResults(datasets)
    # Assign the dataset_results to the module
    module.dataset_results = dataset_results

    # Override the module's methods to delegate to dataset_results
    module.__getitem__ = dataset_results.__getitem__
    module.__len__ = dataset_results.__len__
    module._repr_html_ = dataset_results._repr_html_


def attrs_for_datasite_code_import(module, sync_import_path: str) -> dict[str, Any]:
    client_config_path = os.environ.get("SYFTBOX_CURRENT_CLIENT", None)
    if client_config_path is None:
        raise Exception("run client_config.use()")
    client_config = ClientConfig.load(client_config_path)
    datasite = extract_datasite(sync_import_path)
    datasite_path = os.path.join(client_config.sync_folder, datasite)
    all_code = []
    try:
        manifest = DatasiteManifest.load_from_datasite(datasite_path)
        if hasattr(manifest, "code"):
            for func_name, code_dict in manifest.code.items():
                try:
                    code = Code(**code_dict)
                    code.syft_link = SyftLink(**code_dict["syft_link"])
                    code.readme_link = SyftLink(**code_dict["readme_link"])
                    code.requirements_link = SyftLink(**code_dict["requirements_link"])
                    code._client_config = client_config
                    all_code.append(code)
                    setattr(module, code.func_name, code)
                except Exception as e:
                    print(f"Bad dataset format. {datasite} {e}")
    except Exception:
        pass

    code_results = CodeResults(all_code)
    # Assign the dataset_results to the module
    module.code_results = code_results

    # Override the module's methods to delegate to dataset_results
    module.__getitem__ = code_results.__getitem__
    module.__len__ = code_results.__len__
    module._repr_html_ = code_results._repr_html_


def config_for_user(email: str, root_path: str | None = None) -> str:
    if root_path is None:
        root_path = os.path.abspath("../")
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            # try loading it
            if file.endswith(".json"):
                try:
                    path = os.path.join(root, file)
                    client_config = ClientConfig.load(path)
                    if client_config.email == email:
                        return client_config
                except Exception:
                    pass
    return None


# Custom loader that dynamically creates the modules under syftbox.lib
class DynamicLibSubmodulesLoader(Loader):
    def __init__(self, fullname, sync_path):
        self.fullname = fullname
        self.sync_path = sync_path

    def create_module(self, spec):
        # Create a new module object
        module = types.ModuleType(spec.name)
        return module

    def exec_module(self, module):
        # Register the module in sys.modules
        sys.modules[self.fullname] = module

        # Determine if the module is a package (i.e., it has submodules)
        if not self.fullname.endswith(".datasets"):
            # This module is a package; set the __path__ attribute
            module.__path__ = []  # Empty list signifies a namespace package

        # Attach the module to the parent module
        parent_name = self.fullname.rpartition(".")[0]
        parent_module = sys.modules.get(parent_name)
        if parent_module:
            setattr(parent_module, self.fullname.rpartition(".")[2], module)

        # If this is the datasets module, populate it dynamically
        if self.fullname.endswith(".datasets"):
            self.populate_datasets_module(module)

        if self.fullname.endswith(".code"):
            self.populate_code_module(module)

    def populate_datasets_module(self, module):
        attrs_for_datasite_dataset_import(module, self.sync_path)

    def populate_code_module(self, module):
        attrs_for_datasite_code_import(module, self.sync_path)


# Custom finder to locate and use the DynamicLibSubmodulesLoader
class DynamicLibSubmodulesFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        # Check if the module starts with 'syftbox.lib.' and has additional submodules
        if fullname.startswith("syftbox.lib."):
            # Split the fullname to extract the email path after 'syftbox.lib.'
            sync_path = fullname[len("syftbox.lib.") :]
            # Return a spec with our custom loader
            return spec_from_loader(
                fullname, DynamicLibSubmodulesLoader(fullname, sync_path)
            )
        return None


# Register the custom finder in sys.meta_path
sys.meta_path.insert(0, DynamicLibSubmodulesFinder())


def to_safe_function_name(name: str) -> str:
    # Convert to lowercase
    name = name.lower()
    # Replace any character that is not alphanumeric or underscore with an underscore
    name = re.sub(r"[^a-z0-9_]", "_", name)
    # Ensure the name does not start with a digit
    if name and name[0].isdigit():
        name = "_" + name
    return name


def markdown_to_html(markdown_text):
    html = markdown.markdown(markdown_text)
    return html


@dataclass
class TabularDataset(Jsonable):
    name: str
    syft_link: SyftLink
    schema: dict | None = None
    readme_link: SyftLink | None = None
    loader_link: SyftLink | None = None
    _client_config: ClientConfig | None = None
    has_private: bool = False

    def _repr_html_(self):
        output = f"<strong>{self.name}</strong>\n"
        table_data = {
            "Attribute": ["Name", "Syft Link", "Schema", "Readme", "Loader"],
            "Value": [
                self.name,
                "..." + str(self.syft_link)[-20:],
                str(self.schema),
                "..." + str(self.readme_link)[-20:],
                "..." + str(self.loader_link)[-20:],
            ],
        }

        # Create a DataFrame from the transposed data
        df = pd.DataFrame(table_data)
        if self._client_config:
            readme = self._client_config.resolve_link(self.readme_link)
            with open(readme) as f:
                output += "\nREADME:\n" + markdown_to_html(f.read()) + "\n"

        return output + df._repr_html_()

    # can also do from df where you specify the destination
    @classmethod
    def from_csv(
        self, file_path: str, name: str | None = None, has_private: bool = False
    ):
        if name is None:
            name = os.path.basename(file_path)
        syft_link = SyftLink.from_path(file_path)
        df = pd.read_csv(file_path)
        schema = self.create_schema(df)
        return TabularDataset(
            name=name, syft_link=syft_link, schema=schema, has_private=has_private
        )

    @property
    def import_string(self) -> str:
        string = "from syftbox.lib."
        string += create_datasite_import_path(self.syft_link.datasite)  # a.at.b.com
        string += ".datasets import "
        string += self.clean_name
        return string

    def readme_template(self) -> str:
        private = f"\nPrivate data: {self.has_private}\n" if self.has_private else ""
        readme = f"""
        # {self.name}
        {private}
        Schema: {self.schema}

        ## Import Syntax
        client_config.use()
        {self.import_string}

        ## Python Loader Example
        df = pd.read_csv(sy_path({self.syft_link}))
        """
        return textwrap.dedent(readme)

    def load(self) -> Any:
        if self._client_config:
            loader = self._client_config.resolve_link(self.loader_link)
            with open(loader) as f:
                code = f.read()

            # Evaluate the code and store the function in memory
            local_vars = {}
            exec(code, {}, local_vars)

            # Get the function name
            function_name = f"load_{self.clean_name}"
            if function_name not in local_vars:
                raise ValueError(
                    f"Function {function_name} not found in the loader code."
                )

            # Get the function from the local_vars
            inner_function = local_vars[function_name]

            # Return a new function that wraps the inner function call
            file_path = self._client_config.resolve_link(self.syft_link)
            return inner_function(file_path)

    def loader_template_python(self) -> str:
        code = f"""
        def load_{self.clean_name}(file_path: str):
            import pandas as pd
            from syftbox.lib import sy_path
            return pd.read_csv(sy_path(file_path))
        """
        return textwrap.dedent(code)

    @classmethod
    def create_schema(cls, df) -> dict[str, str]:
        try:
            schema = {}
            for col in df.columns:
                schema[col] = str(df[col].dtype)

            return schema
        except Exception:
            pass
        return None

    @property
    def clean_name(self) -> str:
        return to_safe_function_name(self.name)

    def write_files(self, manifest) -> bool:
        dataset_dir = manifest.root_dir / "datasets" / self.clean_name
        manifest.create_public_folder(dataset_dir)
        # write readme
        readme_link = dataset_dir / "README.md"
        with open(readme_link, "w") as f:
            f.write(self.readme_template())
        self.readme_link = SyftLink.from_path(readme_link)

        # write loader
        loader_link = dataset_dir / "loader.py"
        with open(loader_link, "w") as f:
            f.write(self.loader_template_python())
        self.loader_link = SyftLink.from_path(loader_link)

    def publish(self, manifest: DatasiteManifest, overwrite: bool = False):
        if self.name in manifest.datasets and not overwrite:
            raise Exception(f"Dataset: {self.name} already in manifest")
        self.write_files(manifest)
        manifest.datasets[self.name] = self.to_dict()
        manifest.save(manifest.file_path)
        print("✅ Dataset Published")

    @property
    def file_path(self):
        if self._client_config:
            return self._client_config.resolve_link(self.syft_link)


@dataclass
class DatasetResults:
    data: list = field(default_factory=list)

    def __getitem__(self, index):
        return self.data[index]

    def __len__(self):
        return len(self.data)

    def _repr_html_(self):
        import pandas as pd

        table_data = []
        for item in self.data:
            table_data.append(
                {
                    "Name": item.name,
                    "Private": item.has_private,
                    "Syft Link": "..." + str(item.syft_link)[-20:],
                    "Schema": str(list(item.schema.keys()))[0:100] + "...",
                    "Readme": str(item.readme_link)[-20:],
                    "Loader": str(item.loader_link)[-20:],
                }
            )

        df = pd.DataFrame(table_data)
        return df._repr_html_()


@dataclass
class CodeResults:
    data: list = field(default_factory=list)

    def __getitem__(self, index):
        return self.data[index]

    def __len__(self):
        return len(self.data)

    def _repr_html_(self):
        table_data = []
        for item in self.data:
            table_data.append(
                {
                    "Name": item.name,
                    "Syft Link": "..." + str(item.syft_link)[-20:],
                    "Schema": str(list(item.requirements.keys()))[0:100] + "...",
                    "Readme": str(item.readme_link)[-20:],
                }
            )

        df = pd.DataFrame(table_data)
        return df._repr_html_()


@dataclass
class Code(Jsonable):
    name: str
    func_name: str
    syft_link: SyftLink | None = None
    readme_link: SyftLink | None = None
    requirements_link: SyftLink | None = None
    requirements: dict[str, str] | None = None
    _func: Callable | None = None
    _client_config: ClientConfig | None = None

    def _repr_html_(self):
        import pandas as pd

        output = f"<strong>{self.name}</strong>\n"
        table_data = {
            "Attribute": ["Name", "Syft Link", "Readme", "Requirements"],
            "Value": [
                self.name,
                "..." + str(self.syft_link)[-20:],
                "..." + str(self.readme_link)[-20:],
                "..." + str(self.requirements_link)[-20:],
            ],
        }

        # Create a DataFrame from the transposed data
        df = pd.DataFrame(table_data)
        if self._client_config:
            readme = self._client_config.resolve_link(self.readme_link)
            with open(readme) as f:
                output += "\nREADME:\n" + markdown_to_html(f.read()) + "\n"

        return output + df._repr_html_()

    # can also do from df where you specify the destination
    @classmethod
    def from_func(self, func: Callable):
        name = func.__name__
        code = Code(func_name=name, _func=func, name=name)
        # code.write_files(manifest)
        return code

    def get_function_source(self, func):
        source_code = inspect.getsource(func)
        dedented_code = textwrap.dedent(source_code)
        dedented_code = dedented_code.strip()
        decorator = "@syftbox_code"
        if dedented_code.startswith(decorator):
            dedented_code = dedented_code[len(decorator) :]
        return dedented_code

    @property
    def import_string(self) -> str:
        string = "from syftbox.lib."
        string += create_datasite_import_path(self.syft_link.datasite)  # a.at.b.com
        string += ".code import "
        string += self.clean_name
        return string

    def readme_template(self) -> str:
        readme = f"""
        # {self.name}

        Code:

        ## Import Syntax
        client_config.use()
        {self.import_string}

        ## Python Usage Example
        result = {self.func_name}()
        """
        return textwrap.dedent(readme)

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    @property
    def raw_code(self) -> str:
        if self._func:
            return self.get_function_source(self._func)

        code = ""
        if self._client_config:
            code_link = self._client_config.resolve_link(self.syft_link)
            with open(code_link) as f:
                code = f.read()
        return code

    @property
    def code(self):
        from IPython.display import Markdown

        return Markdown(f"```python\n{self.raw_code}\n```")

    def run(self, *args, resolve_private: bool = False, **kwargs):
        # todo figure out how to override sy_path in the sub code
        if self._client_config:
            code = self.raw_code

            # Evaluate the code and store the function in memory
            local_vars = {}
            exec(code, {}, local_vars)

            # Get the function name
            function_name = f"{self.clean_name}"
            if function_name not in local_vars:
                raise ValueError(
                    f"Function {function_name} not found in the loader code."
                )

            # Get the function from the local_vars
            inner_function = local_vars[function_name]

            return inner_function(*args, **kwargs)
        else:
            raise Exception("run client_config.use()")

    @classmethod
    def extract_imports(cls, source_code):
        imports = set()
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module.split(".")[0])
        return imports

    @property
    def clean_name(self) -> str:
        return to_safe_function_name(self.name)

    def write_files(self, manifest) -> bool:
        code_dir = Path(manifest.root_dir / "code" / self.clean_name)
        manifest.create_public_folder(code_dir)

        # write code
        code_path = code_dir / (self.clean_name + ".py")
        source = self.get_function_source(self._func)
        with open(code_path, "w") as f:
            f.write(source)
        self.syft_link = SyftLink.from_path(code_path)

        # write readme
        readme_link = code_dir / "README.md"
        with open(readme_link, "w") as f:
            f.write(self.readme_template())
        self.readme_link = SyftLink.from_path(readme_link)

        # write requirements.txt
        imports = self.extract_imports(source)
        requirements = {}

        installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
        requirements_txt_path = code_dir / "requirements.txt"
        with open(requirements_txt_path, "w") as f:
            for package in imports:
                if package in installed_packages:
                    requirements[package] = installed_packages[package]
                    f.write(f"{package}=={installed_packages[package]}\n")
                else:
                    requirements[package] = ""
                    f.write(f"{package}\n")
                    print(
                        f"Warning: {package} is not installed in the current environment."
                    )
        self.requirements_link = SyftLink.from_path(requirements_txt_path)
        self.requirements = requirements

    def publish(self, manifest: DatasiteManifest, overwrite: bool = False):
        if self.name in manifest.code and not overwrite:
            raise Exception(f"Code: {self.name} already in manifest")
        self.write_files(manifest)
        manifest.code[self.name] = self.to_dict()
        manifest.save(manifest.file_path)
        print("✅ Code Published")

    @property
    def file_path(self):
        if self._client_config:
            return self._client_config.resolve_link(self.syft_link)

    def to_flow(
        self,
        client_config,
        inputs=None,
        output=None,
        template="python",
        path=None,
        write_back_approved_path: str | None = None,
        write_back_denied_path: str | None = None,
    ) -> str:
        if path is None:
            path = Path(client_config.sync_folder) / "staging"
            os.makedirs(path, exist_ok=True)
        if output is None:
            output = {}

        if "name" not in output:
            output["name"] = "result"
        if "format" not in output:
            output["format"] = "json"

        their_email = list(inputs.values())[0].syft_link.datasite
        if "permission" not in output:
            perm = SyftPermission.theirs_with_my_read_write(
                their_email=their_email, my_email=client_config.email
            )
            output["permission"] = perm

        # create folders
        init_flow(client_config, path, self.name, inputs, output, template)
        # save main.py
        main_code = create_main_py(client_config, inputs, output, self)

        flow_dir = Path(os.path.abspath(f"{path}/{self.name}"))

        main_code_path = flow_dir / "main.py"
        with open(main_code_path, "w") as f:
            f.write(main_code)
        main_shell_path = flow_dir / "run.sh"
        main_shell_code = make_run_sh()
        with open(main_shell_path, "w") as f:
            f.write(main_shell_code)
        make_executable(main_shell_path)

        if write_back_approved_path is None:
            write_back_approved_path = "results/2_approved"

        if write_back_denied_path is None:
            write_back_denied_path = "results/3_denied"

        task_manifest = TaskManifest(
            author=client_config.email,
            result_datasite=client_config.email,
            execution_datasite=their_email,
            write_back_approved_path=write_back_approved_path,
            write_back_denied_path=write_back_denied_path,
        )

        task_manifest_path = flow_dir / "manifest.json"
        task_manifest.save(task_manifest_path)

        return str(flow_dir)


def syftbox_code(func):
    code = Code.from_func(func)
    return code


def get_syftbox_editable_path():
    commands = [
        ["uv", "pip", "list", "--format=columns"],
        ["pip", "list", "--format=columns"],
    ]

    for command in commands:
        try:
            # Run the pip list command and filter for 'syftbox'
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if "syftbox" in line:
                    parts = line.split()
                    if (
                        len(parts) > 2 and "/" in parts[-1]
                    ):  # Path is typically the last part
                        return parts[-1]
        except subprocess.CalledProcessError:
            # Ignore errors and continue with the next command
            continue

    return None


def make_executable(file_path):
    import os
    import stat

    current_permissions = os.stat(file_path).st_mode
    os.chmod(
        file_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )


def make_run_sh() -> str:
    return """#!/bin/sh
uv run main.py $( [ "$1" = "--private" ] && echo '--private' )
"""


def init_flow(
    client_config,
    path,
    name: str,
    inputs: dict[str, Any],
    output: dict[str, Any],
    template: str = "python",
):
    flow_dir = Path(os.path.abspath(f"{path}/{name}"))
    os.makedirs(flow_dir, exist_ok=True)
    # make inputs
    for inp, value in inputs.items():
        inp_path = flow_dir / "inputs" / inp
        os.makedirs(inp_path, exist_ok=True)

        if isinstance(value, TabularDataset):
            syft_link = value.syft_link
            local_path = client_config.resolve_link(syft_link)
            filename = os.path.basename(str(syft_link))
            inp_link_path = inp_path / filename
            if not os.path.exists(inp_link_path):
                os.symlink(local_path, inp_link_path)
            if value.has_private:
                local_path_private = str(local_path) + ".private"
                if os.path.exists(local_path_private):
                    inp_link_path_private = str(inp_link_path) + ".private"
                    if not os.path.exists(inp_link_path_private):
                        os.symlink(local_path_private, inp_link_path_private)

    # create output
    out_format = output["format"]
    if out_format != "json":
        raise Exception("Only supports json")
    out_permission = output["permission"]
    out_path = flow_dir / "output" / output["name"]
    os.makedirs(out_path, exist_ok=True)
    out_permission.save(out_path)


def make_input_code(inputs):
    code = """
def input_reader(private: bool = False):
    from syftbox.lib import sy_path
    import pandas as pd

    inputs = {}
"""
    for key, value in inputs.items():
        if isinstance(value, TabularDataset):
            path = "./inputs/trade_data/trade_mock.csv"
            code += f"    inputs['{key}'] = pd.read_csv(sy_path(\"{path}\", resolve_private=private))"
    code += """
    return inputs
"""
    return textwrap.dedent(code)


def make_output_code(output):
    code = ""
    name = output["name"]
    if output["format"] == "json":
        output_path = f"./output/{name}/{name}.json"
        code += f"""
def output_writer({name}, private: bool = False):
    import json
    output_path = "{output_path}"
    if not private:
        output_path = output_path.replace(".json", ".mock.json")
    with open(output_path, "w") as f:
        f.write(json.dumps({name}))
"""
    return textwrap.dedent(code)


def get_standard_lib_modules():
    """Return a set of standard library module names."""
    standard_lib_path = sysconfig.get_path("stdlib")
    return {module.name for module in pkgutil.iter_modules([standard_lib_path])}


def get_deps(code):
    imports = set()
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])

    deps = {}
    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    standard_lib_modules = get_standard_lib_modules()

    for package in imports:
        # Skip standard library packages
        if package not in standard_lib_modules:
            if package in installed_packages:
                deps[package] = installed_packages[package]
            else:
                deps[package] = ""

    return deps


def make_main_code(code_obj):
    code = """
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Process some input.")
    parser.add_argument('--private', action='store_true', help='Run in private mode')
    args = parser.parse_args()

    print(f"Running: {__name__} from {__author__}")
    inputs = input_reader(private=args.private)
    print("> Reading Inputs", inputs)
"""
    code += f"""
    output = {code_obj.clean_name}(**inputs)
"""
    code += """
    print("> Writing Outputs", output)
    output_writer(output, private=args.private)
    print(f"> ✅ Running {__name__} Complete!")

main()
"""
    return textwrap.dedent(code)


def make_deps_comments(deps):
    code = """
# /// script
# dependencies = [
"""
    for key, value in deps.items():
        code += f'#    "{key}'
        if value != "":
            code += f"=={value}"
        code += '",' + "\n"
    code += "# ]\n"
    code += "#"
    syftbox_path = get_syftbox_editable_path()
    if syftbox_path:
        code += (
            """
# [tool.uv.sources]
# syftbox = { path = \""""
            + syftbox_path
            + '", editable = true }'
            ""
        )

    code += """
# ///
"""
    return textwrap.dedent(code)


def create_main_py(client_config, inputs, output, code_obj):
    code = ""
    code += f"__name__ = '{code_obj.name}'\n"
    code += f"__author__ = '{client_config.email}'\n"
    code += make_input_code(inputs)
    code += "\n"
    code += make_output_code(output)
    code += "\n"
    code += "\n# START YOUR CODE\n"
    code += code_obj.raw_code
    code += "\n"
    code += "\n# END YOUR CODE\n"
    code += "\n"
    code += make_main_code(code_obj)
    code += "\n"

    deps = get_deps(code)

    # prepend
    deps_code = make_deps_comments(deps)
    code = deps_code + "\n" + code
    code += "\n"

    code = textwrap.dedent(code)
    return code


def create_dirs(pipeline, path):
    for sub_dir in pipeline.rules.keys():
        sub_path = path + "/" + sub_dir
        os.makedirs(sub_path, exist_ok=True)


def get_top_dirs(path):
    directories = []
    for dirname in os.listdir(path):
        if os.path.isdir(path + "/" + dirname):
            directories.append(dirname)
    return sorted(directories)


@dataclass
class PipelineAction(Jsonable):
    def run(self, client_config, state, task_path):
        print(f"Running base run: {state} {task_path}")
        return state

    def is_complete(self, client_config, state, task_path) -> bool:
        print("Is this step complete", self, state, task_path)
        return True


@dataclass
class TaskManifest(Jsonable):
    author: str
    execution_datasite: str
    result_datasite: str
    write_back_approved_path: str
    write_back_denied_path: str


def find_and_run_script(task_path, extra_args):
    script_path = os.path.join(task_path, "run.sh")
    # Check if the script exists
    if os.path.isfile(script_path):
        # Set execution bit (+x)
        os.chmod(script_path, os.stat(script_path).st_mode | 0o111)

        # Run the script with extra command line arguments and capture the output
        command = [script_path] + extra_args
        try:
            result = subprocess.run(
                command, cwd=task_path, check=True, capture_output=True, text=True
            )

            print("✅ Script run.sh executed successfully.")
            return result
        except Exception as e:
            print(e)
    else:
        raise FileNotFoundError(f"run.sh not found in {task_path}")


@dataclass
class PipelineActionRun(PipelineAction):
    exit_code: int | None = None

    def run(self, client_config, state, task_path):
        extra_args = ["--private"]
        try:
            result = find_and_run_script(task_path, extra_args)
            if hasattr(result, "returncode"):
                self.exit_code = result.returncode
                print(result.stdout)
        except Exception as e:
            print(f"Failed to run. {e}")
        return state

    def is_complete(self, client_config, state, task_path) -> bool:
        return self.exit_code == 0  # 0 means success


def make_email_body_incoming(
    client_config, state, task_path, manifest, from_email, to_email
):
    task_name = os.path.basename(task_path)
    return f"""
    Hi,<br />
    You have recieved a task `{task_name}` from: {from_email}.<br />
    The files are in: {task_path}.<br />
<br />
    Either move them to 1_review or 5_rejected.<br />
"""


def make_email_body_review(
    client_config, state, task_path, manifest, from_email, to_email
):
    task_name = os.path.basename(task_path)
    return f"""
    Hi,<br />
    Your task `{task_name}` is being reviewed by: {from_email}.<br />
    You will be notified when it is either accepted or rejected.<br />
"""


def make_email_body_verify(
    client_config, state, task_path, manifest, from_email, to_email
):
    task_name = os.path.basename(task_path)
    return f"""
    Hi,<br />
    The task `{task_name}` has run with private data and completed.<br />
    The files are in: {task_path}.<br />
<br />
    Please ensure you are happy to release the results, and either move<br />
    the task `{task_name}` to 4_release or 5_rejected.<br />
"""


def make_email_body_error(
    client_config, state, task_path, manifest, from_email, to_email
):
    task_name = os.path.basename(task_path)
    return f"""
    Hi,<br />
    An error occured running `{task_name}` from: {from_email}.<br />
    The files are in: {task_path}.<br />
<br />
    You could retry by moving the folder back to 2_queue or simply to 7_trash.<br />
"""


def make_email_body_denied(
    client_config, state, task_path, manifest, from_email, to_email
):
    task_name = os.path.basename(task_path)
    write_back = manifest.write_back_denied_path
    return f"""
    Hi,<br />
    Your task `{task_name}` was denied by: {to_email}.<br />
    Your files here: {write_back}<br />
"""


def make_email_body_released(
    client_config, state, task_path, manifest, from_email, to_email
):
    task_name = os.path.basename(task_path)
    write_back = manifest.write_back_approved_path
    return f"""
    Hi,<br />
    Your task `{task_name}` has completed.<br />
    {to_email} have released the private results back to you here: {write_back}<br />
"""


email_templates = {
    "incoming": make_email_body_incoming,
    "review": make_email_body_review,
    "verify": make_email_body_verify,
    "error": make_email_body_error,
    "denied": make_email_body_denied,
    "released": make_email_body_released,
}


@dataclass
class PipelineActionEmail(PipelineAction):
    subject: str
    email_template: str
    sent: bool | None = None

    def run(self, client_config, state, task_path):
        manifest = TaskManifest.load(task_path + "/manifest.json")
        from_email = self.get_from(client_config, manifest)
        to_email = self.get_to(client_config, manifest)
        constructor = email_templates[self.email_template]
        message = constructor(
            client_config, state, task_path, manifest, from_email, to_email
        )
        success = send_email(
            client_config.email_token, from_email, to_email, self.subject, message
        )
        self.sent = success
        return state

    def is_complete(self, client_config, state, task_path) -> bool:
        return bool(self.sent)

    def get_to(self, client_config, manifest) -> str:
        pass

    def get_from(self, client_config, manifest) -> str:
        pass


@dataclass
class PipelineActionEmailToAuthor(PipelineActionEmail):
    def get_to(self, client_config, manifest) -> str:
        return manifest.result_datasite

    def get_from(self, client_config, manifest) -> str:
        return client_config.email


@dataclass
class PipelineActionEmailToDatasite(PipelineActionEmail):
    # when running on the destination machine, this will need
    # to change when the pipeline is on the sender as well
    def get_to(self, client_config, manifest) -> str:
        return client_config.email

    def get_from(self, client_config, manifest) -> str:
        return manifest.result_datasite


@dataclass
class PipelineActionDelete(PipelineAction):
    def run(self, client_config, state, task_path):
        try:
            shutil.rmtree(task_path)
            print(f"Task Deleted {task_path}")
        except Exception as e:
            print(f"Error: {e}")
        return state

    def is_complete(self, client_config, state, task_path) -> bool:
        return not os.path.exists(task_path)


@dataclass
class PipelineActionMove(PipelineAction):
    destination: str
    datasite: str | None = None
    temp_destination_path: str | None = None

    def destination_path(self, client_config, task_path) -> str:
        if self.datasite == "__author__":
            manifest = TaskManifest.load(task_path + "/manifest.json")
            if self.destination == "__write_back_approved__":
                destination = manifest.write_back_approved_path
            elif self.destination == "__write_back_denied__":
                destination = manifest.write_back_denied_path

            remote_path = (
                client_config.sync_folder
                + "/"
                + manifest.result_datasite
                + "/"
                + destination
                + "/"
                + os.path.basename(task_path)
            )
            return os.path.abspath(remote_path)
        return os.path.abspath(f"{task_path}/../../{self.destination}")

    def run(self, client_config, state, task_path):
        try:
            self.temp_destination_path = self.destination_path(client_config, task_path)

            if os.path.exists(self.temp_destination_path):
                print(f"> Overwriting destination: {self.temp_destination_path}")
                shutil.rmtree(self.temp_destination_path)
                # in move you do want the directory?
                os.makedirs(self.temp_destination_path, exist_ok=True)

            shutil.move(task_path, self.temp_destination_path)
        except Exception as e:
            print(f"Error: {e}")
        return state

    def is_complete(self, client_config, state, task_path) -> bool:
        if (
            not os.path.exists(task_path)
            and self.temp_destination_path
            and os.path.exists(self.temp_destination_path)
        ):
            return True
        return False


@dataclass
class PipelineActionCopy(PipelineAction):
    destination: str
    datasite: str | None = None
    temp_destination_path: str | None = None

    def destination_path(self, client_config, task_path) -> str:
        if self.datasite == "__author__":
            manifest = TaskManifest.load(task_path + "/manifest.json")
            if self.destination == "__write_back_approved__":
                destination = manifest.write_back_approved_path
            elif self.destination == "__write_back_denied__":
                destination = manifest.write_back_denied_path

            remote_path = (
                client_config.sync_folder
                + "/"
                + manifest.result_datasite
                + "/"
                + destination
                + "/"
                + os.path.basename(task_path)
            )
            return os.path.abspath(remote_path)
        return os.path.abspath(f"{task_path}/../../{self.destination}")

    def run(self, client_config, state, task_path):
        try:
            self.temp_destination_path = self.destination_path(client_config, task_path)

            if os.path.exists(self.temp_destination_path):
                print(f"> Overwriting destination: {self.temp_destination_path}")
                shutil.rmtree(self.temp_destination_path)
                # copy you dont want the directory
                # os.makedirs(self.temp_destination_path, exist_ok=True)

            shutil.copytree(task_path, self.temp_destination_path)
        except Exception as e:
            print(f"Error: {e}")
        return state

    def is_complete(self, client_config, state, task_path) -> bool:
        if os.path.exists(self.temp_destination_path):
            return True
        return False


@dataclass
class CurrentTaskState(Jsonable):
    step: str
    task: str
    state: str
    last_modified: float

    def __eq__(self, other):
        if isinstance(other, CurrentTaskState):
            return (
                self.step == other.step
                and self.task == other.task
                and self.state == other.state
                and self.last_modified == other.last_modified
            )
        return False

    @classmethod
    def pending(cls, task: str, step: str) -> Self:
        return CurrentTaskState(
            step=step,
            task=task,
            state="pending",
            last_modified=datetime.now().timestamp(),
        )

    def to_error(self) -> Self:
        return self.change_state(state="error")

    def change_state(self, state) -> Self:
        self.state = state
        self.last_modified = datetime.now().timestamp()
        return self

    def advance(self) -> Self:
        to_state = None
        if self.state == "pending":
            to_state = "running"
        elif self.state == "running":
            to_state = "complete"
        elif self.state == "error":
            return self
        elif self.state == "complete":
            return self
        else:
            raise Exception(f"Unknown state: {self.state}")
        print(f"> Advancing: {self.task} from {self.state} -> {to_state}")
        return self.change_state(state=to_state)

    def ensure(self, path: str) -> bool:
        try:
            prev_state_file = CurrentTaskState.load(path)
            if self == prev_state_file:
                # no need to write
                return True
        except Exception:
            pass
        return self.save(path)


@dataclass
class PipelineStep(Jsonable):
    timeout_secs: int = 60 * 60 * 24 * 7  # 7 days
    pending: list[PipelineAction] | None = None
    running: list[PipelineAction] | None = None
    complete: list[PipelineAction] | None = None
    error: list[PipelineAction] | None = None


def get_state_file(state_file, task, step):
    try:
        state = CurrentTaskState.load(state_file)
        if state.step == step:
            return state
    except Exception:
        pass

    # overwrite with a new step pending
    state = CurrentTaskState.pending(step=step, task=task)
    state.save(state_file)
    return state


@dataclass
class PipelineRule(Jsonable):
    dirname: str
    permission: SyftPermission
    step: PipelineStep | None


@dataclass
class Pipeline(Jsonable):
    rules: dict[str, PipelineRule]
    path: str

    @classmethod
    def make_job_pipeline(cls, client_config) -> Self:
        write_back_approved_path = (
            client_config.datasite_path + "/" + "results/2_approved"
        )
        os.makedirs(write_back_approved_path, exist_ok=True)
        public_write = SyftPermission.mine_with_public_write(client_config.email)
        public_write.ensure(perm_file_path(write_back_approved_path))
        write_back_denied_path = client_config.datasite_path + "/" + "results/3_denied"
        os.makedirs(write_back_denied_path, exist_ok=True)
        public_write = SyftPermission.mine_with_public_write(client_config.email)
        public_write.ensure(perm_file_path(write_back_denied_path))

        path = client_config.datasite_path + "/" + "jobs/inbox"
        os.makedirs(path, exist_ok=True)
        mine_no_permission = SyftPermission.mine_no_permission(client_config.email)
        mine_no_permission.terminal = True  # prevent overriding in lower levels

        public_read = SyftPermission.mine_with_public_read(client_config.email)

        public_write = SyftPermission.mine_with_public_write(client_config.email)

        incoming_email = PipelineActionEmailToDatasite(
            subject="You Recieved a Task", email_template="incoming"
        )
        review_email = PipelineActionEmailToAuthor(
            subject="Your Task is in Review", email_template="review"
        )

        verify_email = PipelineActionEmailToDatasite(
            subject="Task Complete, Please check private results",
            email_template="verify",
        )

        error_email = PipelineActionEmailToDatasite(
            subject="Task Error, Please check", email_template="error"
        )

        denied_email = PipelineActionEmailToAuthor(
            subject="Your Task was Denied", email_template="denied"
        )

        released_email = PipelineActionEmailToAuthor(
            subject="Task Complete, The private results have been released to you",
            email_template="released",
        )

        incoming_rule = PipelineRule(
            dirname="0_incoming",
            permission=public_write,
            step=PipelineStep(
                running=[incoming_email],
            ),
        )

        review_rule = PipelineRule(
            dirname="1_review",
            permission=public_read,
            step=PipelineStep(
                running=[review_email],
            ),
        )

        queue_rule = PipelineRule(
            dirname="2_queue",
            permission=mine_no_permission,
            step=PipelineStep(
                running=[PipelineActionRun()],
                complete=[PipelineActionMove(destination="3_verify")],
            ),
        )

        verify_rule = PipelineRule(
            dirname="3_verify",
            permission=mine_no_permission,
            step=PipelineStep(
                running=[verify_email],
            ),
        )

        release_rule = PipelineRule(
            dirname="4_release",
            permission=mine_no_permission,
            step=PipelineStep(
                running=[
                    PipelineActionCopy(
                        destination="__write_back_approved__", datasite="__author__"
                    ),
                    released_email,
                    PipelineActionMove(destination="8_done"),
                ],
            ),
        )

        rejected_rule = PipelineRule(
            dirname="5_rejected",
            permission=mine_no_permission,
            step=PipelineStep(
                running=[
                    PipelineActionCopy(
                        destination="__write_back_denied__", datasite="__author__"
                    ),
                    denied_email,
                    PipelineActionMove(destination="7_trash"),
                ],
            ),
        )

        error_rule = PipelineRule(
            dirname="6_error",
            permission=mine_no_permission,
            step=PipelineStep(
                running=[error_email],
            ),
        )

        trash_rule = PipelineRule(
            dirname="7_trash",
            permission=mine_no_permission,
            step=PipelineStep(
                # running=[PipelineActionDelete()],
                running=[],
            ),
        )

        done_rule = PipelineRule(
            dirname="8_done",
            permission=mine_no_permission,
            step=None,
        )

        state_rule = PipelineRule(
            dirname="state", permission=mine_no_permission, step=None
        )

        rules = {
            "0_incoming": incoming_rule,
            "1_review": review_rule,
            "2_queue": queue_rule,
            "3_verify": verify_rule,
            "4_release": release_rule,
            "5_rejected": rejected_rule,
            "6_error": error_rule,
            "7_trash": trash_rule,
            "8_done": done_rule,
            "state": state_rule,
        }

        pipeline = Pipeline(rules=rules, path=path)
        return pipeline

    def create_permission_files(self):
        for step, rule in self.rules.items():
            if rule.permission:
                step_path = self.path + "/" + step
                perm_file = perm_file_path(step_path)
                rule.permission.ensure(perm_file)

    def progress_pipeline(self, client_config):
        states = ["pending", "running", "complete", "error"]
        create_dirs(self, self.path)
        self.create_permission_files()
        pipeline_dirs = get_top_dirs(self.path)
        if list(self.rules.keys()) != sorted(pipeline_dirs):
            raise Exception(
                f"Pipeline structure: {self.path} doesnt match pipeline: {self}"
            )

        for step, rule in self.rules.items():
            tasks = get_top_dirs(self.path + "/" + step)
            # outer loop makes sure that a single task can progress the entire way if possible
            for task in tasks:
                for state in states:
                    task_path = state_file = self.path + "/" + step + "/" + task
                    state_file = self.path + "/" + "state" + "/" + task + ".syftstate"
                    current_task_state = get_state_file(state_file, task, step)
                    if current_task_state.state != "complete":
                        print(
                            f"> Task {task} {current_task_state.step}:{current_task_state.state}"
                        )
                    if state == current_task_state.state:
                        rule_steps = getattr(rule.step, state, None)
                        if rule_steps is None:
                            current_task_state = current_task_state.advance()
                            current_task_state.ensure(state_file)
                            continue
                        else:
                            for action in rule_steps:
                                print(f"> Task Running: {action}")
                                try:
                                    current_task_state = action.run(
                                        client_config, current_task_state, task_path
                                    )
                                except Exception as e:
                                    print(f"Exception running action: {action} {e}")

                                if action.is_complete(
                                    client_config, current_task_state, task_path
                                ):
                                    current_task_state = current_task_state.advance()
                                    current_task_state.ensure(state_file)
                                    print(
                                        f"> Task {task} {current_task_state.step}:{current_task_state.state}"
                                    )
                    else:
                        pass


def send_email(
    token: str, from_email: str, to_email: str, subject: str, message: str
) -> bool:
    # Send the email
    try:
        if token:
            from postmarker.core import PostmarkClient

            # Create a Postmark client
            client = PostmarkClient(server_token=token)
            response = client.emails.send(
                From="madhava@openmined.org",
                To=to_email,
                Subject=f"Syftbox {subject} from: {from_email}",
                HtmlBody=message,
                TextBody=message,
            )
            print("Email sent successfully:", response)
        else:
            print("!!! Email requires a token!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
    return False
