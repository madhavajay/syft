import asyncio
import os
import platform
import sys
from functools import lru_cache
from pathlib import Path

import httpx
import uvicorn
from loguru import logger
from pid import PidFile, PidFileAlreadyLockedError

from syftbox.client.api import create_api
from syftbox.client.base import SyftClientContext
from syftbox.client.exceptions import SyftBoxAlreadyRunning
from syftbox.client.utils import error_reporting, file_manager, macos
from syftbox.lib.client_config import SyftClientConfig
from syftbox.lib.constants import PERM_FILE
from syftbox.lib.exceptions import SyftBoxException
from syftbox.lib.ignore import create_default_ignore_file
from syftbox.lib.lib import SyftPermission
from syftbox.lib.logger import setup_logger
from syftbox.lib.workspace import SyftWorkspace

SCRIPT_DIR = Path(__file__).parent
ASSETS_FOLDER = SCRIPT_DIR.parent / "assets"
ICON_FOLDER = ASSETS_FOLDER / "icon"


class SyftClient:
    """The SyftBox Client

    This is the main SyftBox client that handles workspace data, server
    communication, and local API services. Only one client instance can run
    for a given workspace directory.

    Warning:
        This class should not be imported directly by sub-systems.
        Use the provided interfaces and context objects instead.

    Raises:
        SyftBoxAlreadyRunning: If another client is already running for the same workspace
        Exception: If the client fails to start due to any reason
    """

    def __init__(self, config: SyftClientConfig, log_level: str = "INFO"):
        self.config = config
        self.log_level = log_level

        self.workspace = SyftWorkspace(self.config.data_dir)
        self.pid = PidFile(pidname="syftbox.pid", piddir=self.workspace.data_dir)
        self.server_client = httpx.Client(
            base_url=str(self.config.server_url),
            follow_redirects=True,
        )
        # self.sync_manager = SyncManager(self.workspace, self.server_client)
        self.__local_server: uvicorn.Server = None

    @property
    def config_path(self) -> Path:
        return self.config.path

    @property
    def is_registered(self) -> bool:
        """Check if the current user is registered with the server"""
        return bool(self.config.token)

    @property
    def datasite(self) -> Path:
        """The datasite directory for the current user"""
        return self.workspace.datasites / self.config.email

    @property
    def public_dir(self) -> Path:
        """The public directory for the current user"""
        return self.datasite / "public"

    @property
    def all_datasites(self) -> list:
        return [d.name for d in self.workspace.datasites.iterdir() if d.is_dir() and "@" in d.name]

    def start(self):
        try:
            self.pid.create()
        except PidFileAlreadyLockedError:
            raise SyftBoxAlreadyRunning(f"Another instance of SyftBox is running on {self.config.data_dir}")

        logger.info("Started SyftBox client")

        # create the workspace directories
        self.workspace.mkdirs()
        # register the email with the server
        self.register_self()
        # init the datasite on local machine
        self.init_datasite()
        # start the sync manager
        # self.sync_manager.start()
        # run the apps
        # self.run_apps()
        # start the local server - blocks main thread
        return self.__run_local_server()

    def open_sync_folder(self):
        file_manager.open_dir(self.workspace.datasites)

    def copy_icons(self):
        self.workspace.mkdirs()
        if platform.system() == "Darwin":
            macos.copy_icon_file(ICON_FOLDER, self.workspace.datasites)

    def shutdown(self):
        logger.info("Shutting down SyftBox client")
        if self.__local_server:
            asyncio.run(self.__local_server.shutdown())
        # self.sync_manager.stop()
        self.pid.close()

    def init_datasite(self):
        if self.datasite.exists():
            return

        # Create workspace/datasites/.syftignore
        create_default_ignore_file(self.workspace.datasites)

        # Create perm file for the datasite
        if not self.datasite.is_dir():
            try:
                logger.info(f"creating datasite at {self.datasite}")
                self.__create_datasite()
            except Exception as e:
                logger.error("Failed to create datasite", e)
                # this is a problematic scenario - probably because you can't setup the basic
                # datasite structure. So, we should probably just exit here.
                raise SyftBoxException(f"Failed to initialize datasite - {e}")

        if not self.public_dir.is_dir():
            try:
                logger.info(f"creating public dir in datasite at {self.public_dir}")
                self.__create_public_folder()
            except Exception as e:
                # not a big deal if we can't create the public folder
                # more likely that the above step fails than this
                logger.error("Failed to create folder with public perms", e)

    def register_self(self):
        """Register the user's email with the SyftBox cache server"""
        if self.is_registered:
            return

        try:
            token = self.__register_email()
            # TODO + FIXME - once we have JWT, we should not store token in config!
            # ideally in OS keychain (using keyring) or
            # in a separate location under self.workspace.plugins
            self.config.token = str(token)
            self.config.save()
            logger.info("Email registration successful")
        except Exception as e:
            logger.error(f"Failed to register {self.config.email} with the server", e)
            raise SyftBoxException(f"Failed to register with the server - {e}")

    @lru_cache(1)
    def as_context(self) -> SyftClientContext:
        """Projects self as a context object"""
        return SyftClientContext(self.config, self.workspace, self.server_client)

    def __run_local_server(self):
        logger.info(f"Starting local server on {self.config.client_url}")
        app = create_api(self.as_context())
        self.__local_server = uvicorn.Server(
            config=uvicorn.Config(
                app=app,
                host=self.config.client_url.host,
                port=self.config.client_url.port,
                log_level=self.log_level.lower(),
            )
        )
        return self.__local_server.run()

    def __create_datasite(self):
        # create the datasite directory and the root perm file
        self.datasite.mkdir(parents=True, exist_ok=True)
        perms = SyftPermission.datasite_default(self.config.email)
        perms.save(str(self.datasite / PERM_FILE))

    def __create_public_folder(self):
        # create a public folder & public perm file
        self.public_dir.mkdir(parents=True, exist_ok=True)
        perms = SyftPermission.mine_with_public_read(self.config.email)
        perms.save(str(self.public_dir / PERM_FILE))

    def __register_email(self) -> str:
        # TODO - this should probably be wrapped in a SyftCacheServer API?
        response = self.server_client.post(
            "/register",
            json={"email": self.config.email},
        )
        response.raise_for_status()
        return response.json().get("token")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


def run_client(
    client_config: SyftClientConfig,
    open_dir: bool = False,
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

    run_migrations(client_config)

    try:
        client = SyftClient(client_config, log_level=log_level)
        open_dir and client.open_sync_folder()
        copy_icons and client.copy_icons()
        client.start()
    except SyftBoxAlreadyRunning as e:
        logger.error(e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down the client")
    except Exception as e:
        logger.error(f"Failed to start the client: {e}")
    finally:
        client.shutdown()


def run_migrations(config: SyftClientConfig):
    # TODO - move datasite workspaces to correct location
    # ws = SyftWorkspace(config.data_dir)
    # old_datasite_path = Path(ws.data_dir, config.email)

    # if old_datasite_path.exists():
    #     ws.mkdirs()
    #     # TODO shutil move things
    return


if __name__ == "__main__":
    email = "test@openmined.org"
    data_dir = Path(f".clients/{email}").resolve()
    conf_path = data_dir / "config.json"
    if SyftClientConfig.exists(conf_path):
        conf = SyftClientConfig.load(conf_path)
    else:
        conf = SyftClientConfig(
            path=conf_path,
            data_dir=data_dir,
            email=email,
            server_url="https://syftboxstage.openmined.org",
            port=8081,
        ).save()
    try:
        client = SyftClient(conf)
        client.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(e)
    finally:
        client.shutdown()
