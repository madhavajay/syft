import os
import shutil
from collections import namedtuple
from pathlib import Path
from typing import Optional, Tuple

from ..lib import ClientConfig
from .install import install

config_path = os.environ.get("SYFTBOX_CLIENT_CONFIG_PATH", None)


def install_app(client_config: ClientConfig, repository: str, branch: str = "main") -> Tuple[str, Exception]:
    return install(client_config, repository, branch)


def list_app(client_config: ClientConfig) -> dict:
    apps_path = Path(client_config.sync_folder, "apps")
    apps = []
    if os.path.exists(apps_path):
        files_and_folders = os.listdir(apps_path)
        apps = [app for app in files_and_folders if os.path.isdir(apps_path / app)]
    return {
        "apps_path": apps_path,
        "apps": apps,
    }


def uninstall_app(app_name: str, client_config: ClientConfig) -> Optional[Path]:
    app_dir = Path(client_config.sync_folder, "apps", app_name)
    if app_dir.exists() and app_dir.is_dir():
        shutil.rmtree(app_dir)
    elif app_dir.exists() and app_dir.is_symlink():
        app_dir.unlink()
    else:
        app_dir = None
    return app_dir


def update_app(client_config: ClientConfig) -> None:
    pass


def upgrade_app(client_config: ClientConfig) -> None:
    pass


Commands = namedtuple("Commands", ["description", "execute"])


def make_commands() -> dict[str, Commands]:
    return {
        "list": Commands("List all currently installed apps in your syftbox.", list_app),
        "install": Commands("Install a new app in your syftbox.", install),
        "uninstall": Commands("Uninstall a certain app.", uninstall_app),
        "update": Commands("Check for app updates.", update_app),
        "upgrade": Commands("Upgrade an app.", upgrade_app),
    }
