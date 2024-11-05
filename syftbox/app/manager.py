import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from ..lib import ClientConfig
from .install import install


def install_app(config: ClientConfig, repository: str, branch: str = "main") -> Tuple[str, Exception]:
    return install(config, repository, branch)


def list_app(config: ClientConfig) -> dict:
    apps_path = Path(config.sync_folder, "apps")
    apps = []
    if os.path.exists(apps_path):
        files_and_folders = os.listdir(apps_path)
        apps = [app for app in files_and_folders if os.path.isdir(apps_path / app)]
    return {
        "apps_path": apps_path,
        "apps": apps,
    }


def uninstall_app(app_name: str, config: ClientConfig) -> Optional[Path]:
    app_dir = Path(config.sync_folder, "apps", app_name)
    # first check for symlink
    if app_dir.exists() and app_dir.is_symlink():
        app_dir.unlink()
    elif app_dir.exists() and app_dir.is_dir():
        shutil.rmtree(app_dir)
    else:
        app_dir = None
    return app_dir


def update_app(config: ClientConfig) -> None:
    pass
