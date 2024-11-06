from pathlib import Path

from typing_extensions import Optional, Self

from syftbox.lib.client_config import SyftClientConfig
from syftbox.lib.types import PathLike
from syftbox.lib.workspace import SyftWorkspace

# NOTE: this will likely get refactored as it's own SDK.
# But we need it to maintain compatibility with apps


class Client:
    """
    Client shim for SyftBox Apps

    Minimal set of properties and methods exposed to the apps.
    """

    def __init__(self, conf: SyftClientConfig):
        self.conf = conf
        self.workspace = SyftWorkspace(self.conf.data_dir)

    @property
    def email(self):
        """Legacy property"""
        return self.conf.email

    @property
    def sync_folder(self) -> Path:
        """Legacy property"""
        return self.workspace.datasites

    @property
    def config_path(self) -> Path:
        """Legacy property"""
        return self.config.path

    @property
    def datasite_path(self) -> Path:
        """Legacy property"""
        return self.workspace.datasites / self.conf.email

    @classmethod
    def load(cls, filepath: Optional[PathLike] = None) -> Self:
        """
        Load the client configuration from the given file path or env var or default location
        Raises: ClientConfigException
        """
        return cls(conf=SyftClientConfig.load(filepath))
