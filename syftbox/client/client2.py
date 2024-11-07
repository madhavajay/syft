import os
import platform
import sys
import time
from pathlib import Path

import httpx
import uvicorn
from loguru import logger
from pid import PidFile, PidFileAlreadyLockedError

from syftbox.client import __version__
from syftbox.client.client import create_application
from syftbox.client.exceptions import SyftBoxAlreadyRunning
from syftbox.client.utils import error_reporting, file_manager, macos
from syftbox.lib.client_config import SyftClientConfig
from syftbox.lib.exceptions import SyftBoxException
from syftbox.lib.lib import SyftPermission
from syftbox.lib.logger import setup_logger
from syftbox.lib.workspace import SyftWorkspace

SCRIPT_DIR = Path(__file__).parent
ASSETS_FOLDER = SCRIPT_DIR.parent / "assets"
ICON_FOLDER = ASSETS_FOLDER / "icon"


class SyftClient:
    """Syftbox Client

    Contains all the components of a syftbox client.
    Only one instance can run for a given workspace.
    This should not be used by apps.
    """

    def __init__(self, config: SyftClientConfig, log_level: str = "INFO"):
        self.config = config
        self.log_level = log_level

        self.workspace = SyftWorkspace(self.config.data_dir)
        self.pid = PidFile(pidname="syftbox.pid", piddir=self.workspace.data_dir)
        self.server_client = httpx.Client(
            base_url=self.config.server_url,
            follow_redirects=True,
        )
        self.__local_server: uvicorn.Server = None

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

    def start(self):
        try:
            self.pid.create()
        except PidFileAlreadyLockedError as e:
            raise SyftBoxAlreadyRunning(f"There's another Syftbox client running on {self.config.data_dir}") from e

        logger.info(f"> Starting SyftBox Client: {__version__} Python {platform.python_version()}")

        self.workspace.mkdirs()
        self.__run_local_server()

    def __run_local_server(self):
        logger.info(f"> Starting local server on {self.config.client_url}")
        app = create_application()
        self.__local_server = uvicorn.Server(
            config=uvicorn.Config(
                app=app,
                host=self.config.client_url.host,
                port=self.config.client_url.port,
                log_level=self.log_level.lower(),
                timeout_graceful_shutdown=0,
            )
        )
        self.__local_server.run()

        if not self.__local_server.started:
            raise SyftBoxException("Failed to start the local server")

    def open_sync_folder(self):
        file_manager.open_dir(self.workspace.datasites)

    def copy_icons(self):
        self.workspace.mkdirs()
        if platform.system() == "Darwin":
            macos.copy_icon_file(ICON_FOLDER, self.workspace.datasites)

    def shutdown(self):
        if self.__local_server:
            self.__local_server.shutdown()
        self.pid.close()

    def init_datasite(self):
        if not SyftPermission.exists(self.datasite):
            SyftPermission.private(self.datasite, owner=self.config.email).save()

        if not SyftPermission.exists(self.public_dir):
            SyftPermission.readwrite(self.public_dir, owner=self.config.email).save()
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


def run_client(
    client_config: SyftClientConfig,
    open_dir: bool,
    log_level: str = "INFO",
    verbose: bool = False,
):
    """Run the SyftBox client"""

    log_level = "DEBUG" if verbose else log_level
    setup_logger(log_level)

    error_config = error_reporting.make_error_report(client_config)
    logger.info(f"Client metadata: {error_config.model_dump_json(indent=2)}")

    # a flag to disable icons
    # GitHub CI needs to zip sync dir in tests and fails when it encounters Icon\r files
    disable_icons = str(os.getenv("SYFTBOX_DISABLE_ICONS")).lower() in ("true", "1")
    if disable_icons:
        logger.info("Directory icons are disabled")
    copy_icons = not disable_icons

    try:
        client = SyftClient(client_config, log_level=log_level)
        open_dir and client.open_sync_folder()
        copy_icons and client.copy_icons()
        client.start()
    except SyftBoxAlreadyRunning as e:
        logger.error(e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Shutting down the client")
    except Exception as e:
        logger.error(f"Failed to start the client: {e}")
    finally:
        client.shutdown()


if __name__ == "__main__":
    conf = SyftClientConfig(
        data_dir=Path(".clients/test@openmined.org").resolve(),
        email="test@openmined.org",
        client_url="http://localhost:8000",
        path="./data/config.json",
    )
    conf.save()
    client = SyftClient(conf)
    client.start()
    client.init_datasite()
    time.sleep(30)
    client.shutdown()
