from pathlib import Path
from typing import Mapping

from syftbox.lib.lib import SyftPermission

DirTree = Mapping[str, "str | DirTree"]


def create_dir_tree(base_path: Path, tree: DirTree) -> None:
    print(f"creating tree at {base_path}, {type(base_path)}")
    for name, content in tree.items():
        local_path = base_path / name

        if isinstance(content, str):
            local_path.write_text(content)
        elif isinstance(content, SyftPermission):
            content.save(path=str(local_path))
        elif isinstance(content, dict):
            local_path.mkdir(parents=True, exist_ok=True)
            create_dir_tree(local_path, content)
