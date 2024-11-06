import atexit
import contextlib
import importlib
import os
import platform
import subprocess
import sys
import types
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import uvicorn
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from syftbox import __version__
from syftbox.client.plugins.sync.manager import SyncManager
from syftbox.client.routers import datasite_router, file_router, plugin_router, state_router
from syftbox.client.utils import macos
from syftbox.client.utils.error_reporting import make_error_report
from syftbox.lib import ClientConfig, SharedState
from syftbox.lib.logger import setup_logger

from .routers.plugin_router import start_plugin

current_dir = Path(__file__).parent
PLUGINS_DIR = current_dir / "plugins"
sys.path.insert(0, os.path.dirname(PLUGINS_DIR))


ASSETS_FOLDER = current_dir.parent / "assets"
ICON_FOLDER = ASSETS_FOLDER / "icon"

WATCHDOG_IGNORE = ["apps"]


# We should later move this to a separate file
@dataclass
class Plugin:
    name: str
    schedule: int
    description: str

    @property
    def module(self) -> types.ModuleType:
        return importlib.import_module(f"plugins.{self.name}")


def load_plugins(client_config: ClientConfig) -> dict[str, Plugin]:
    loaded_plugins = {}
    if os.path.exists(PLUGINS_DIR) and os.path.isdir(PLUGINS_DIR):
        for item in os.listdir(PLUGINS_DIR):
            if item.endswith(".py") and not item.startswith("__") and "sync" not in item:
                plugin_name = item[:-3]
                try:
                    module = importlib.import_module(f"plugins.{plugin_name}")
                    schedule = getattr(
                        module,
                        "DEFAULT_SCHEDULE",
                        5000,
                    )  # Default to 5000ms if not specified
                    description = getattr(
                        module,
                        "DESCRIPTION",
                        "No description available.",
                    )
                    plugin = Plugin(
                        name=plugin_name,
                        schedule=schedule,
                        description=description,
                    )
                    loaded_plugins[plugin_name] = plugin
                except Exception as e:
                    logger.info(e)

    return loaded_plugins


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"> Starting SyftBox Client: {__version__} Python {platform.python_version()}")

    # Load the embedded client configuration or from ENV
    # will throw error on invalid config
    app.state.config = app.state.config or ClientConfig.load()

    if not app.state.config:
        logger.error("Client configuration not found. Exiting...")
        sys.exit(1)

    app.state.shared_state = SharedState(client_config=app.state.config)

    logger.info(f"Connecting to {app.state.config.server_url}")

    # Clear the lock file on the first run if it exists
    job_file = str(app.state.config.config_path).replace(".json", ".sql")
    app.state.job_file = job_file
    if os.path.exists(job_file):
        os.remove(job_file)
        logger.info(f"> Cleared existing job file: {job_file}")

    # Start the scheduler
    jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{job_file}")}
    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start()
    atexit.register(partial(stop_scheduler, app))

    app.state.scheduler = scheduler
    app.state.running_plugins = {}
    app.state.loaded_plugins = load_plugins(app.state.config)
    logger.info(f"> Loaded plugins: {sorted(list(app.state.loaded_plugins.keys()))}")

    logger.info(f"> Starting autorun plugins: {sorted(app.state.config.autorun_plugins)}")
    for plugin in app.state.config.autorun_plugins:
        start_plugin(app, plugin)

    start_syncing(app)

    yield  # This yields control to run the application

    logger.info("> Shutting down...")
    scheduler.shutdown()
    app.state.config.close()


def start_syncing(app: FastAPI):
    manager = SyncManager(app.state.shared_state.client_config)
    manager.start()


def stop_scheduler(app: FastAPI):
    # Remove the lock file if it exists
    if os.path.exists(app.state.job_file):
        os.remove(app.state.job_file)
        logger.info("> Scheduler stopped and lock file removed.")


def create_application() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    # Mount static files
    try:
        app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")
        logger.info("Mounted static files")
    except Exception as e:
        logger.error(f"Failed to mount static files: {e}")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(plugin_router.router, prefix="", tags=["plugins"])
    app.include_router(state_router.router, prefix="/state", tags=["state"])
    app.include_router(datasite_router.router, prefix="/datasites", tags=["datasites"])
    app.include_router(file_router.router, prefix="/file", tags=["file"])

    return app


def open_sync_folder(folder_path):
    """Open the folder specified by `folder_path` in the default file explorer."""
    if not os.path.exists(folder_path):
        return

    logger.info(f"Opening your sync folder: {folder_path}")
    try:
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", folder_path])
        elif platform.system() == "Windows":  # Windows
            subprocess.run(["explorer", folder_path])
        elif platform.system() == "Linux":  # Linux
            subprocess.run(["xdg-open", folder_path])
        else:
            logger.warning(f"Unsupported OS for opening folders: {platform.system()}")
    except Exception as e:
        logger.error(f"Failed to open folder {folder_path}: {e}")


def copy_folder_icon(sync_folder: Path):
    # a flag to disable icons
    # GitHub CI needs to zip sync dir in tests and fails when it encounters Icon\r files
    disable_icons = str(os.getenv("SYFTBOX_DISABLE_ICONS")).lower() in ("true", "1")
    if disable_icons:
        logger.info("Directory icons are disabled")
        return

    if platform.system() == "Darwin":
        macos.copy_icon_file(ICON_FOLDER, sync_folder)


def run_client(
    client_config: ClientConfig,
    open_dir: bool,
    log_level: str = "INFO",
    verbose: bool = False,
):
    """Run the SyftBox client"""

    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(log_level)

    error_config = make_error_report(client_config)
    logger.info(f"Client metadata: {error_config.model_dump_json(indent=2)}")

    # copy folder icon
    copy_folder_icon(client_config.sync_folder)

    # open_sync_folder
    open_dir and open_sync_folder(client_config.sync_folder)

    # set the config in the fastapi's app state
    os.environ["SYFTBOX_CLIENT_CONFIG_PATH"] = str(client_config.config_path)

    app = create_application()
    app.state.config = client_config

    # Run the FastAPI app
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=client_config.port,
        log_level=log_level.lower(),
    )
