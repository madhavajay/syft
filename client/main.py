import argparse
import importlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import types
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Self, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, jsonify, render_template, request
from flask_apscheduler import APScheduler

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Dictionary to store running plugins and their job IDs
running_plugins = {}

# Dictionary to store loaded plugins
loaded_plugins = {}

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "plugins")
sys.path.insert(0, os.path.dirname(PLUGINS_DIR))

DEFAULT_SYNC_FOLDER = os.path.expanduser("~/Desktop/SyftBox")
DEFAULT_PORT = 8082
DEFAULT_CONFIG_PATH = "./client_config.json"
ICON_FOLDER = os.path.abspath("../assets/icon/")


class Jsonable:
    def to_dict(self) -> dict:
        output = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            output[k] = v
        return output

    def __iter__(self):
        for key, val in self.to_dict().items():
            if key.startswith("_"):
                yield key, val

    def __getitem__(self, key):
        if key.startswith("_"):
            return None
        return self.to_dict()[key]

    @classmethod
    def load(cls, filepath: str) -> Self:
        try:
            with open(filepath) as f:
                data = f.read()
                d = json.loads(data)
                return cls(**d)
        except Exception as e:
            print(f"Unable to load file: {filepath}. {e}")
        return None

    def save(self, filepath: str) -> None:
        d = self.to_dict()
        with open(filepath, "w") as f:
            f.write(json.dumps(d))


@dataclass
class ClientConfig(Jsonable):
    sync_folder: Path
    port: int

    @property
    def db_path(self) -> Path:
        return os.path.join(self.sync_folder, "sync_checkpoints.sqlite")


class SharedState:
    def __init__(self, client_config: ClientConfig):
        self.data = {}
        self.lock = Lock()
        self.client_config = client_config

    @property
    def sync_folder(self) -> str:
        return self.client_config.sync_folder

    def get(self, key, default=None):
        with self.lock:
            if key == "my_datasites":
                return self._get_datasites()
            return self.data.get(key, default)

    def set(self, key, value):
        with self.lock:
            self.data[key] = value

    def _get_datasites(self):
        syft_folder = self.data.get(self.client_config.sync_folder)
        if not syft_folder or not os.path.exists(syft_folder):
            return []

        return [
            folder
            for folder in os.listdir(syft_folder)
            if os.path.isdir(os.path.join(syft_folder, folder))
        ]


@dataclass
class Plugin:
    name: str
    module: types.ModuleType
    schedule: int
    description: str


def find_icon_file(src_folder: str) -> Path:
    src_path = Path(src_folder)

    for file_path in src_path.iterdir():
        if "Icon" in file_path.name and "\r" in file_path.name:
            return file_path
    raise FileNotFoundError("Icon file with a carriage return not found.")


def copy_icon_file(icon_folder: str, dest_folder: str) -> None:
    src_icon_path = find_icon_file(icon_folder)
    if not os.path.isdir(dest_folder):
        raise FileNotFoundError(f"Destination folder '{dest_folder}' does not exist.")

    # shutil wont work with these special icon files
    subprocess.run(["cp", "-p", src_icon_path, dest_folder], check=True)
    subprocess.run(["SetFile", "-a", "C", dest_folder], check=True)


def load_or_create_config(args) -> ClientConfig:
    if os.path.exists(args.config):
        print("Got file, ", args.config)
    client_config = None
    try:
        client_config = ClientConfig.load(args.config)
    except Exception as e:
        print("e", e)

    if client_config is None:
        user_path = get_user_input(
            "Where do you want to Sync SyftBox to?", DEFAULT_SYNC_FOLDER
        )
        user_path = os.path.abspath(os.path.expanduser(user_path))
        port = int(get_user_input("Enter the port to use", DEFAULT_PORT))
        client_config = ClientConfig(sync_folder=user_path, port=port)

    if not os.path.exists(client_config.sync_folder):
        os.makedirs(client_config.sync_folder, exist_ok=True)
        print(f"Creating path: {client_config.sync_folder}")

    copy_icon_file(ICON_FOLDER, client_config.sync_folder)
    # make macos icon

    client_config.save(args.config)

    return client_config


def get_user_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ").strip()
    return user_input if user_input else default


def process_folder_input(user_input, default_path):
    if not user_input:
        return default_path
    if "/" not in user_input:
        # User only provided a folder name, use it with the default parent path
        parent_path = os.path.dirname(default_path)
        return os.path.join(parent_path, user_input)
    return os.path.expanduser(user_input)


def reinitialize_sync_db(client_config):
    if os.path.exists(client_config.db_path):
        try:
            os.remove(client_config.db_path)
            logger.info(
                f"Deleted existing .sync_checkpoints.db at {client_config.db_path}"
            )
        except Exception as e:
            logger.error(f"Failed to delete existing .sync_checkpoints.db: {str(e)}")
            return

    try:
        conn = sqlite3.connect(client_config.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS file_timestamps
                     (relative_path TEXT PRIMARY KEY, timestamp REAL)""")
        conn.commit()
        conn.close()
        logger.info(f"Initialized new .sync_checkpoints.db at {client_config.db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize new .sync_checkpoints.db: {str(e)}")


def initialize_shared_state(client_config: ClientConfig) -> SharedState:
    shared_state = SharedState(client_config=client_config)
    reinitialize_sync_db(client_config)
    return shared_state


def run_plugin(plugin_name):
    try:
        logger.info(f"Running plugin: {plugin_name}")
        module = loaded_plugins[plugin_name].module
        module.run(shared_state)
    except Exception as e:
        logger.exception(f"Error in plugin {plugin_name}: {str(e)}")


def load_plugins(client_config: ClientConfig) -> dict[str, Plugin]:
    loaded_plugins = {}

    if os.path.exists(PLUGINS_DIR) and os.path.isdir(PLUGINS_DIR):
        for item in os.listdir(PLUGINS_DIR):
            if item.endswith(".py") and not item.startswith("__"):
                plugin_name = item[:-3]
                print("got plugin name", plugin_name)
                try:
                    module = importlib.import_module(f"plugins.{plugin_name}")
                    schedule = getattr(
                        module, "DEFAULT_SCHEDULE", 5000
                    )  # Default to 5000ms if not specified
                    description = getattr(
                        module, "DESCRIPTION", "No description available."
                    )
                    plugin = Plugin(
                        name=plugin_name,
                        module=module,
                        schedule=schedule,
                        description=description,
                    )
                    loaded_plugins[plugin_name] = plugin
                    logger.info(f"Plugin {plugin} loaded successfully")
                except Exception as e:
                    logger.exception(f"Failed to load plugin {plugin_name}: {str(e)}")

    return loaded_plugins


def start_plugin(plugin_name):
    if plugin_name not in loaded_plugins:
        return jsonify(error=f"Plugin {plugin_name} is not loaded"), 400

    if plugin_name in running_plugins:
        return jsonify(error=f"Plugin {plugin_name} is already running"), 400

    try:
        plugin = loaded_plugins[plugin_name]
        job = scheduler.add_job(
            func=run_plugin,
            trigger="interval",
            seconds=plugin.schedule / 1000,
            id=plugin_name,
            args=[plugin_name],
        )
        running_plugins[plugin_name] = {
            "job": job,
            "start_time": time.time(),
            "schedule": plugin.schedule,
        }
        logger.info(f"Plugin {plugin_name} started with interval {plugin.schedule}ms")
        return jsonify(message=f"Plugin {plugin_name} started successfully"), 200
    except Exception as e:
        logger.exception(f"Failed to start plugin {plugin_name}")
        return jsonify(error=f"Failed to start plugin {plugin_name}: {str(e)}"), 500


def generate_key_pair() -> Tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
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


@app.route("/plugins", methods=["GET"])
def list_plugins():
    plugins = []
    for plugin_name, plugin in loaded_plugins.items():
        plugins.append(
            {
                "name": plugin_name,
                "default_schedule": plugin.schedule,
                "is_running": plugin_name in running_plugins,
                "description": plugin.description,
            }
        )
    return jsonify(plugins=plugins)


@app.route("/launch", methods=["POST"])
def launch_plugin():
    plugin_name = request.json.get("plugin_name")
    if not plugin_name:
        return jsonify(error="Plugin name is required"), 400

    return start_plugin(plugin_name)


@app.route("/running", methods=["GET"])
def list_running_plugins():
    running = {}
    for name, data in running_plugins.items():
        job = data["job"]
        running[name] = {
            "is_running": job.next_run_time is not None,
            "run_time": time.time() - data["start_time"],
            "schedule": data["schedule"],
        }
    return jsonify(running_plugins=running)


@app.route("/kill", methods=["POST"])
def kill_plugin():
    plugin_name = request.json.get("plugin_name")
    if not plugin_name:
        return jsonify(error="Plugin name is required"), 400

    if plugin_name not in running_plugins:
        return jsonify(error=f"Plugin {plugin_name} is not running"), 400

    try:
        # Stop the scheduler job
        scheduler.remove_job(plugin_name)

        # Call the stop method if it exists
        plugin_module = loaded_plugins[plugin_name].module
        if hasattr(plugin_module, "stop"):
            plugin_module.stop()

        # Remove the plugin from running_plugins
        del running_plugins[plugin_name]

        logger.info(f"Plugin {plugin_name} stopped successfully")
        return jsonify(message=f"Plugin {plugin_name} stopped successfully"), 200
    except Exception as e:
        logger.exception(f"Failed to stop plugin {plugin_name}")
        return jsonify(error=f"Failed to stop plugin {plugin_name}: {str(e)}"), 500


@app.route("/state", methods=["GET"])
def get_shared_state():
    return jsonify(shared_state.data)


@app.route("/state/update", methods=["POST"])
def update_shared_state():
    key = request.json.get("key")
    value = request.json.get("value")
    logger.info(f"Received request to update {key} with value: {value}")
    if key is not None:
        old_value = shared_state.get(key)
        shared_state.set(key, value)
        new_value = shared_state.get(key)
        logger.info(f"Updated {key}: old value '{old_value}', new value '{new_value}'")
        return jsonify(
            message=f"Updated key '{key}' from '{old_value}' to '{new_value}'"
        ), 200
    return jsonify(error="Invalid request"), 400


@app.route("/")
def plugin_manager():
    return render_template("index.html")


@app.route("/datasites", methods=["GET"])
def list_datasites():
    datasites = shared_state.get("my_datasites")
    return jsonify(datasites=datasites)


@app.route("/datasites", methods=["POST"])
def add_datasite():
    name = request.json.get("name")
    if not name:
        return jsonify(error="Datasite name is required"), 400

    if not is_valid_datasite_name(name):
        return jsonify(
            error="Invalid datasite name. Use only alphanumeric characters, hyphens, and underscores."
        ), 400

    syft_folder = shared_state.client_config.sync_folder
    if not syft_folder:
        return jsonify(error="sync_folder is not set in shared state"), 500

    datasite_path = os.path.join(syft_folder, name)
    if os.path.exists(datasite_path):
        return jsonify(error=f"Datasite '{name}' already exists"), 409

    try:
        os.makedirs(datasite_path)
        private_key, public_key = generate_key_pair()

        with open(os.path.join(datasite_path, "private_key.pem"), "wb") as f:
            f.write(private_key)
        with open(os.path.join(datasite_path, "public_key.pem"), "wb") as f:
            f.write(public_key)

        return jsonify(message=f"Datasite '{name}' created successfully"), 201
    except Exception as e:
        logger.exception(f"Failed to create datasite {name}")
        return jsonify(error=f"Failed to create datasite: {str(e)}"), 500


@app.route("/datasites/<name>", methods=["DELETE"])
def remove_datasite(name):
    if not is_valid_datasite_name(name):
        return jsonify(error="Invalid datasite name"), 400

    syft_folder = shared_state.client_config.sync_folder
    if not syft_folder:
        return jsonify(error="syft_folder is not set in shared state"), 500

    datasite_path = os.path.join(syft_folder, name)
    if not os.path.exists(datasite_path):
        return jsonify(error=f"Datasite '{name}' does not exist"), 404

    try:
        shutil.rmtree(datasite_path)
        return jsonify(message=f"Datasite '{name}' removed successfully"), 200
    except Exception as e:
        logger.exception(f"Failed to remove datasite {name}")
        return jsonify(error=f"Failed to remove datasite: {str(e)}"), 500


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the web application with plugins."
    )
    parser.add_argument(
        "config", type=str, default=DEFAULT_CONFIG_PATH, help="config path"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port number")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    client_config = load_or_create_config(args)
    shared_state = initialize_shared_state(client_config)
    loaded_plugins = load_plugins(client_config)
    print("loaded_plugins", loaded_plugins.keys())
    first_plugin = list(loaded_plugins.keys())[0]
    # for plugin_name, plugin in loaded_plugins.items():
    print("first_plugin", first_plugin, type(first_plugin))
    scheduler_thread = threading.Thread(target=start_plugin, args=(first_plugin,))
    scheduler_thread.start()
    print(f"Client Running: http://localhost:{client_config.port}")
    try:
        app.run(host="0.0.0.0", port=client_config.port, debug=True)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler_thread.join()  # Ensure the scheduler thread is properly cleaned up
