import argparse
import os
import platform
import time
from pathlib import Path
from typing import Optional

import uvicorn
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from syftbox.client.fsevents import (
    AnyFileSystemEventHandler,
    FileSystemEvent,
    FSWatchdog,
)
from syftbox.client.plugin import PluginManager, PluginResult, PluginStatus
from syftbox.client.utils import macos
from syftbox.lib import ClientConfig, SharedState, validate_email

CURRENT_DIR = Path(__file__).parent

DEFAULT_SYNC_FOLDER = os.path.expanduser("~/Desktop/SyftBox")
DEFAULT_PORT = 8082
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.syftbox/client_config.json")

ASSETS_FOLDER = CURRENT_DIR.parent / "assets"
ICON_FOLDER = ASSETS_FOLDER / "icon"

WATCHDOG_IGNORE = ["apps"]

templates = Jinja2Templates(directory=CURRENT_DIR / "templates")


def load_or_create_config(args) -> ClientConfig:
    syft_config_dir = os.path.abspath(os.path.expanduser("~/.syftbox"))
    os.makedirs(syft_config_dir, exist_ok=True)

    client_config = None
    try:
        client_config = ClientConfig.load(args.config_path)
    except Exception:
        pass

    if client_config is None and args.config_path:
        config_path = os.path.abspath(os.path.expanduser(args.config_path))
        client_config = ClientConfig(config_path=config_path)

    if client_config is None:
        # config_path = get_user_input("Path to config file?", DEFAULT_CONFIG_PATH)
        config_path = os.path.abspath(os.path.expanduser(config_path))
        client_config = ClientConfig(config_path=config_path)

    if args.sync_folder:
        sync_folder = os.path.abspath(os.path.expanduser(args.sync_folder))
        client_config.sync_folder = sync_folder

    if client_config.sync_folder is None:
        sync_folder = get_user_input(
            "Where do you want to Sync SyftBox to?",
            DEFAULT_SYNC_FOLDER,
        )
        sync_folder = os.path.abspath(os.path.expanduser(sync_folder))
        client_config.sync_folder = sync_folder

    if args.server:
        client_config.server_url = args.server

    if not os.path.exists(client_config.sync_folder):
        os.makedirs(client_config.sync_folder, exist_ok=True)

    if platform.system() == "Darwin":
        macos.copy_icon_file(ICON_FOLDER, client_config.sync_folder)

    if args.email:
        client_config.email = args.email

    if client_config.email is None:
        email = get_user_input("What is your email address? ")
        if not validate_email(email):
            raise Exception(f"Invalid email: {email}")
        client_config.email = email

    if args.port:
        client_config.port = args.port

    if client_config.port is None:
        port = int(get_user_input("Enter the port to use", DEFAULT_PORT))
        client_config.port = port

    email_token = os.environ.get("EMAIL_TOKEN", None)
    if email_token:
        client_config.email_token = email_token

    client_config.save(args.config_path)
    return client_config


def get_user_input(prompt, default: Optional[str] = None):
    if default:
        prompt = f"{prompt} (default: {default}): "
    user_input = input(prompt).strip()
    return user_input if user_input else default


def process_folder_input(user_input, default_path):
    if not user_input:
        return default_path
    if "/" not in user_input:
        # User only provided a folder name, use it with the default parent path
        parent_path = os.path.dirname(default_path)
        return os.path.join(parent_path, user_input)
    return os.path.expanduser(user_input)


def generate_key_pair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem, public_pem


def is_valid_datasite_name(name):
    return name.isalnum() or all(c.isalnum() or c in ("-", "_") for c in name)


# API Models
class PluginRequest(BaseModel):
    plugin_name: str


class SharedStateRequest(BaseModel):
    key: str
    value: str


class DatasiteRequest(BaseModel):
    name: str


# Parsing arguments and initializing shared state
def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the web application with plugins.",
    )
    parser.add_argument(
        "--config_path", type=str, default=DEFAULT_CONFIG_PATH, help="config path"
    )
    parser.add_argument("--sync_folder", type=str, help="sync folder path")
    parser.add_argument("--email", type=str, help="email")
    parser.add_argument("--port", type=int, default=8080, help="Port number")
    parser.add_argument(
        "--server",
        type=str,
        default="http://20.168.10.234:8080",
        help="Server",
    )
    return parser.parse_args()


def start_plugin_manager(job_file: Path, shared_state: SharedState) -> PluginManager:
    # Clear the lock file on the first run if it exists
    if job_file.exists():
        job_file.unlink()
        print(f"> Cleared existing job file: {job_file}")

    # Start the scheduler
    scheduler = BackgroundScheduler(
        jobstores=dict(default=SQLAlchemyJobStore(url=f"sqlite:///{job_file}"))
    )

    plugin_manager = PluginManager(
        shared_state=shared_state,
        scheduler=scheduler,
    )
    plugin_manager.load()
    results = plugin_manager.schedule_many(["init", "create_datasite", "sync", "apps"])
    for result in results:
        if result.status != PluginStatus.SUCCESS:
            print("Failed to schedule plugin:", result.__dict__)

    return plugin_manager


def stop_plugin_manager(job_file: Path, plugin_manager: PluginManager):
    plugin_manager.stop()
    # Remove the lock file if it exists
    if job_file.exists():
        job_file.unlink()
        print("> Scheduler stopped and lock file removed.")


def start_watchdog(watch_dir: Path, plugin: PluginManager) -> FSWatchdog:
    def sync_on_event(event: FileSystemEvent):
        plugin.run("sync", event)

    event_handler = AnyFileSystemEventHandler(
        watch_dir,
        callbacks=[
            sync_on_event,
        ],
        ignored=WATCHDOG_IGNORE,
    )
    watchdog = FSWatchdog(watch_dir, event_handler)
    watchdog.start()
    return watchdog


async def lifespan(app: FastAPI):
    # Startup
    print("> Starting Client")
    args = parse_args()
    client_config = load_or_create_config(args)
    job_file = Path(client_config.config_path.replace(".json", ".sql"))

    shared_state = SharedState(client_config=client_config)
    plugins = start_plugin_manager(job_file, shared_state)
    watchdog = start_watchdog(Path(client_config.sync_folder), plugins)

    app.shared_state = shared_state
    app.plugins = plugins
    app.watchdog = watchdog

    yield  # This yields control to run the application

    print("> Shutting down...")
    watchdog.stop()
    plugins.stop()
    job_file.unlink(missing_ok=True)


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=CURRENT_DIR / "static"), name="static")


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
        email = app.shared_state.client_config.email
        return JSONResponse(content={"email": email})
    except AttributeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error accessing client email: {e!s}",
        )


@app.get("/state")
def get_shared_state():
    return JSONResponse(content=app.shared_state.data)


@app.get("/datasites")
def list_datasites():
    datasites = app.shared_state.get("my_datasites", [])
    # Use jsonable_encoder to encode the datasites object
    return JSONResponse(content={"datasites": jsonable_encoder(datasites)})


# FastAPI Routes
@app.get("/plugins")
def list_plugins():
    plugins = [
        {
            "name": plugin_name,
            "default_schedule": plugin.schedule,
            "running": plugin_name in app.plugins.running,
            "description": plugin.description,
        }
        for plugin_name, plugin in app.plugins.loaded.items()
    ]
    return {"plugins": plugins}


@app.post("/launch")
def launch_plugin(request: PluginRequest):
    result: PluginResult = app.plugins.schedule(request.plugin_name)
    if result.status == PluginStatus.SUCCESS:
        return {"plugin": request.plugin_name, "message": result.message}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"{result.message} - {result.data}",
        )


@app.get("/running")
def list_running_plugins():
    running = {
        name: {
            "running": data.job.next_run_time is not None,
            "uptime": time.time() - data.start_time,
            "schedule": data.schedule,
        }
        for name, data in app.plugins.running.items()
    }
    return {"running_plugins": running}


@app.post("/kill")
def kill_plugin(request: PluginRequest):
    result: PluginResult = app.plugins.unschedule(request.plugin_name)
    if result.status == PluginStatus.SUCCESS:
        return {"plugin": request.plugin_name, "message": result.message}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"{result.message} - {result.data}",
        )


@app.post("/file_operation")
async def file_operation(
    operation: str = Body(...),
    file_path: str = Body(...),
    content: str = Body(None),
):
    full_path = Path(app.shared_state.client_config.sync_folder) / file_path

    # Ensure the path is within the SyftBox directory
    if not full_path.resolve().is_relative_to(
        Path(app.shared_state.client_config.sync_folder),
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


def get_syftbox_src_path():
    import importlib.util

    module_name = "syftbox"
    spec = importlib.util.find_spec(module_name)
    return spec.origin


def main() -> None:
    args = parse_args()
    client_config = load_or_create_config(args)

    os.environ["SYFTBOX_DATASITE"] = client_config.email
    os.environ["SYFTBOX_CLIENT_CONFIG_PATH"] = client_config.config_path

    print("Dev Mode: ", os.environ.get("SYFTBOX_DEV"))
    print("Wheel: ", os.environ.get("SYFTBOX_WHEEL"))

    debug = True
    uvicorn.run(
        "syftbox.client.client:app"
        if debug
        else app,  # Use import string in debug mode
        host="0.0.0.0",
        port=client_config.port,
        log_level="debug" if debug else "info",
        reload=debug,  # Enable hot reloading only in debug mode
        reload_dirs="./syftbox",
    )


if __name__ == "__main__":
    main()
