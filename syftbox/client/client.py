import atexit
import contextlib
import importlib
import os
import platform
import subprocess
import sys
import time
import types
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import uvicorn
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel

from syftbox import __version__
from syftbox.client.logger import setup_logger
from syftbox.client.plugins.sync.manager import SyncManager
from syftbox.client.utils import macos
from syftbox.client.utils.error_reporting import make_error_report
from syftbox.lib import ClientConfig, SharedState

current_dir = Path(__file__).parent
# Initialize FastAPI app and scheduler

templates = Jinja2Templates(directory=str(current_dir / "templates"))


PLUGINS_DIR = current_dir / "plugins"
sys.path.insert(0, os.path.dirname(PLUGINS_DIR))


ASSETS_FOLDER = current_dir.parent / "assets"
ICON_FOLDER = ASSETS_FOLDER / "icon"

WATCHDOG_IGNORE = ["apps"]


@dataclass
class Plugin:
    name: str
    module: types.ModuleType
    schedule: int
    description: str


def process_folder_input(user_input, default_path):
    if not user_input:
        return default_path
    if "/" not in user_input:
        # User only provided a folder name, use it with the default parent path
        parent_path = os.path.dirname(default_path)
        return os.path.join(parent_path, user_input)
    return os.path.expanduser(user_input)


def initialize_shared_state(client_config: ClientConfig) -> SharedState:
    shared_state = SharedState(client_config=client_config)
    return shared_state


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
                        module=module,
                        schedule=schedule,
                        description=description,
                    )
                    loaded_plugins[plugin_name] = plugin
                except Exception as e:
                    logger.info(e)

    return loaded_plugins


# API Models
class PluginRequest(BaseModel):
    plugin_name: str


class SharedStateRequest(BaseModel):
    key: str
    value: str


class DatasiteRequest(BaseModel):
    name: str


# Function to be scheduled
def run_plugin(plugin_name, *args, **kwargs):
    try:
        module = app.state.loaded_plugins[plugin_name].module
        module.run(app.state.shared_state, *args, **kwargs)
    except Exception as e:
        logger.exception(e)


def start_plugin(app: FastAPI, plugin_name: str):
    if "sync" in plugin_name:
        return

    if plugin_name not in app.state.loaded_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_name} is not loaded",
        )

    if plugin_name in app.state.running_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_name} is already running",
        )

    try:
        plugin = app.state.loaded_plugins[plugin_name]

        existing_job = app.state.scheduler.get_job(plugin_name)
        if existing_job is None:
            job = app.state.scheduler.add_job(
                func=run_plugin,
                trigger="interval",
                seconds=plugin.schedule / 1000,
                id=plugin_name,
                args=[plugin_name],
            )
            app.state.running_plugins[plugin_name] = {
                "job": job,
                "start_time": time.time(),
                "schedule": plugin.schedule,
            }
            return {"message": f"Plugin {plugin_name} started successfully"}
        else:
            logger.info(f"Job {existing_job}, already added")
            return {"message": f"Plugin {plugin_name} already started"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start plugin {plugin_name}: {e!s}",
        )


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


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/", response_class=HTMLResponse)
async def plugin_manager(request: Request):
    # Pass the request to the template to allow FastAPI to render it
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/client_email")
def get_client_email():
    try:
        email = app.state.shared_state.client_config.email
        return JSONResponse(content={"email": email})
    except AttributeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error accessing client email: {e!s}",
        )


@app.get("/state")
def get_shared_state():
    return JSONResponse(content=app.state.shared_state.data)


@app.get("/datasites")
def list_datasites():
    datasites = app.state.shared_state.get("my_datasites", [])
    # Use jsonable_encoder to encode the datasites object
    return JSONResponse(content={"datasites": jsonable_encoder(datasites)})


# FastAPI Routes
@app.get("/plugins")
def list_plugins():
    plugins = [
        {
            "name": plugin_name,
            "default_schedule": plugin.schedule,
            "is_running": plugin_name in app.state.running_plugins,
            "description": plugin.description,
        }
        for plugin_name, plugin in app.state.loaded_plugins.items()
    ]
    return {"plugins": plugins}


@app.post("/launch")
def launch_plugin(plugin_request: PluginRequest, request: Request):
    return start_plugin(request.app, plugin_request.plugin_name)


@app.get("/running")
def list_running_plugins():
    running = {
        name: {
            "is_running": data["job"].next_run_time is not None,
            "run_time": time.time() - data["start_time"],
            "schedule": data["schedule"],
        }
        for name, data in app.state.running_plugins.items()
    }
    return {"running_plugins": running}


@app.post("/kill")
def kill_plugin(request: PluginRequest):
    plugin_name = request.plugin_name

    if plugin_name not in app.state.running_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_name} is not running",
        )

    try:
        app.state.scheduler.remove_job(plugin_name)
        plugin_module = app.state.loaded_plugins[plugin_name].module
        if hasattr(plugin_module, "stop"):
            plugin_module.stop()
        del app.state.running_plugins[plugin_name]
        return {"message": f"Plugin {plugin_name} stopped successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop plugin {plugin_name}: {e!s}",
        )


@app.post("/file_operation")
async def file_operation(
    operation: str = Body(...),
    file_path: str = Body(...),
    content: str = Body(None),
):
    full_path = Path(app.state.shared_state.client_config.sync_folder) / file_path

    # Ensure the path is within the SyftBox directory
    if not full_path.resolve().is_relative_to(
        Path(app.state.shared_state.client_config.sync_folder),
    ):
        raise HTTPException(
            status_code=403,
            detail="Access to files outside SyftBox directory is not allowed",
        )

    if operation == "read":
        if not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(full_path)

    if operation in ["write", "append"]:
        if content is None:
            raise HTTPException(
                status_code=400,
                detail="Content is required for write or append operation",
            )

        # Ensure the directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            mode = "w" if operation == "write" else "a"
            with open(full_path, mode) as f:
                f.write(content)
            return JSONResponse(content={"message": f"File {operation}ed successfully"})
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to {operation} file: {e!s}",
            )

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid operation. Use 'read', 'write', or 'append'",
        )


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
    app.state.config = client_config

    # Run the FastAPI app
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=client_config.port,
        log_level=log_level.lower(),
    )
