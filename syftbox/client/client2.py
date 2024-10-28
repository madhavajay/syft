import time
from pathlib import Path

import httpx
from pid import PidFile, PidFileAlreadyLockedError

from syftbox.client.config import SyftClientConfig
from syftbox.client.exceptions import SyftBoxAlreadyRunning
from syftbox.lib.permissions import SyftPermission
from syftbox.lib.workspace import SyftWorkspace


class SyftClient:
    """Syftbox Client

    Contains all the components of a syftbox client.
    Only one instance can run for a given workspace.
    This should not be used by apps.
    """

    def __init__(self, settings: SyftClientConfig):
        self.config = settings
        self.workspace = SyftWorkspace(self.config.data_dir)
        self.pid = PidFile(pidname="syftbox.pid", piddir=self.workspace.data_dir)
        self.server_client = httpx.Client(
            base_url=self.config.server_url,
            follow_redirects=True,
        )
        # todo bring the following in this
        # loaded_plugins: dict
        # running_plugins: dict
        # scheduler: Any
        # shared_state: SharedState
        # watchdog: Any

    def start(self):
        try:
            self.pid.create()
        except PidFileAlreadyLockedError as e:
            raise SyftBoxAlreadyRunning("There's another Syftbox client running with this config") from e

        self.workspace.mkdirs()

    def shutdown(self):
        self.pid.close()

    @property
    def is_registered(self) -> bool:
        return bool(self.config.token)

    @property
    def config_path(self) -> Path:
        return self.config.path

    @property
    def datasite(self) -> Path:
        return self.workspace.datasites / self.config.email

    @property
    def public_dir(self) -> Path:
        return self.datasite / "public"

    @property
    def all_datasites(self) -> list:
        return [d.name for d in self.workspace.datasites.iterdir() if d.is_dir() and "@" in d.name]

    def init_datasite(self):
        if not SyftPermission.exists(self.datasite):
            SyftPermission.private(self.datasite, owner=self.config.email).save()

        if not SyftPermission.exists(self.public_dir):
            SyftPermission.readwrite(self.public_dir, owner=self.config.email).save()


if __name__ == "__main__":
    conf = SyftClientConfig(
        data_dir=Path("./data").resolve(),
        email="test@openmined.org",
        client_url="http://localhost:8000",
        path="./data/config.json",
    )
    client = SyftClient(conf)
    client.start()
    client.init_datasite()
    time.sleep(30)
    client.shutdown()
