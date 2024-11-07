import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..lib import ClientConfig
from .install import InstallResult, install


@dataclass
class InstalledApps:
    apps_dir: Path
    apps: List[Path]


def install_app(config: ClientConfig, repository: str, branch: str = "main") -> InstallResult:
    return install(config, repository, branch)


def list_app(config: ClientConfig) -> InstalledApps:
    apps_dir = Path(config.sync_folder, "apps")
    apps = []
    if apps_dir.exists() and apps_dir.is_dir():
        apps = sorted([app for app in apps_dir.iterdir() if app.is_dir()])
    return InstalledApps(apps_dir, apps)


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
