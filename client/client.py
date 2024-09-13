import argparse
import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import types
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, jsonify, render_template, request
from flask_apscheduler import APScheduler

from lib import Jsonable


def validate_email(email: str) -> bool:
    # Define a regex pattern for a valid email
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    # Use the match method to check if the email fits the pattern
    if re.match(email_regex, email):
        return True
    else:
        return False


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
ASSETS_FOLDER = os.path.abspath("../assets")
ICON_FOLDER = os.path.abspath(f"{ASSETS_FOLDER}/icon/")


@dataclass
class ClientConfig(Jsonable):
    config_path: Path
    sync_folder: Path | None = None
    port: int | None = None
    email: str | None = None
    token: int | None = None
    server_url: str = "http://localhost:5001"

    def save(self, path: str | None = None) -> None:
        if path is None:
            path = self.config_path
        super().save(path)

    @property
    def datasite_path(self) -> Path:
        return os.path.join(self.sync_folder, self.email)


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


# if you knew the pain of this function
def find_icon_file(src_folder: str) -> Path:
    src_path = Path(src_folder)

    # Function to search for Icon\r file
    def search_icon_file():
        if os.path.exists(src_folder):
            for file_path in src_path.iterdir():
                if "Icon" in file_path.name and "\r" in file_path.name:
                    return file_path
        return None

    # First attempt to find the Icon\r file
    icon_file = search_icon_file()
    if icon_file:
        return icon_file

    # If Icon\r is not found, search for icon.zip and unzip it
    zip_file = Path(os.path.abspath(ASSETS_FOLDER)) / "icon.zip"
    if zip_file.exists():
        try:
            # cant use other zip tools as they don't unpack it correctly
            subprocess.run(
                ["ditto", "-xk", str(zip_file), str(src_path.parent)], check=True
            )

            # Try to find the Icon\r file again after extraction
            icon_file = search_icon_file()
            if icon_file:
                return icon_file
        except subprocess.CalledProcessError:
            raise RuntimeError("Failed to unzip icon.zip using macOS CLI tool.")

    # If still not found, raise an error
    raise FileNotFoundError(
        "Icon file with a carriage return not found, and icon.zip did not contain it."
    )


def copy_icon_file(icon_folder: str, dest_folder: str) -> None:
    src_icon_path = find_icon_file(icon_folder)
    if not os.path.isdir(dest_folder):
        raise FileNotFoundError(f"Destination folder '{dest_folder}' does not exist.")

    # shutil wont work with these special icon files
    subprocess.run(["cp", "-p", src_icon_path, dest_folder], check=True)
    subprocess.run(["SetFile", "-a", "C", dest_folder], check=True)


def load_or_create_config(args) -> ClientConfig:
    client_config = None
    try:
        client_config = ClientConfig.load(args.config_path)
    except Exception:
        pass

    if client_config is None and args.config_path:
        config_path = os.path.abspath(os.path.expanduser(args.config_path))
        client_config = ClientConfig(config_path=config_path)

    if client_config is None:
        config_path = get_user_input("Path to config file?", DEFAULT_CONFIG_PATH)
        config_path = os.path.abspath(os.path.expanduser(config_path))
        client_config = ClientConfig(config_path=config_path)

    if args.sync_folder:
        sync_folder = os.path.abspath(os.path.expanduser(args.sync_folder))
        client_config.sync_folder = sync_folder

    if client_config.sync_folder is None:
        sync_folder = get_user_input(
            "Where do you want to Sync SyftBox to?", DEFAULT_SYNC_FOLDER
        )
        sync_folder = os.path.abspath(os.path.expanduser(sync_folder))
        client_config.sync_folder = sync_folder

    if not os.path.exists(client_config.sync_folder):
        os.makedirs(client_config.sync_folder, exist_ok=True)

    copy_icon_file(ICON_FOLDER, client_config.sync_folder)

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

    client_config.save(args.config_path)
    return client_config


def get_user_input(prompt, default: str | None = None):
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


def initialize_shared_state(client_config: ClientConfig) -> SharedState:
    shared_state = SharedState(client_config=client_config)
    return shared_state


def run_plugin(plugin_name):
    try:
        # logger.info(f"Running plugin: {plugin_name}")
        module = loaded_plugins[plugin_name].module
        module.run(shared_state)
    except Exception:
        pass
        # logger.exception(f"Error in plugin {plugin_name}: {str(e)}")


def load_plugins(client_config: ClientConfig) -> dict[str, Plugin]:
    loaded_plugins = {}

    if os.path.exists(PLUGINS_DIR) and os.path.isdir(PLUGINS_DIR):
        for item in os.listdir(PLUGINS_DIR):
            if item.endswith(".py") and not item.startswith("__"):
                plugin_name = item[:-3]
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
        # logger.info(f"Plugin {plugin_name} started with interval {plugin.schedule}ms")
        return jsonify(message=f"Plugin {plugin_name} started successfully"), 200
    except Exception as e:
        # logger.exception(f"Failed to start plugin {plugin_name}")
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

        # logger.info(f"Plugin {plugin_name} stopped successfully")
        return jsonify(message=f"Plugin {plugin_name} stopped successfully"), 200
    except Exception as e:
        # logger.exception(f"Failed to stop plugin {plugin_name}")
        return jsonify(error=f"Failed to stop plugin {plugin_name}: {str(e)}"), 500


@app.route("/state", methods=["GET"])
def get_shared_state():
    return jsonify(shared_state.data)


@app.route("/state/update", methods=["POST"])
def update_shared_state():
    key = request.json.get("key")
    value = request.json.get("value")
    # logger.info(f"Received request to update {key} with value: {value}")
    if key is not None:
        old_value = shared_state.get(key)
        shared_state.set(key, value)
        new_value = shared_state.get(key)
        # logger.info(f"Updated {key}: old value '{old_value}', new value '{new_value}'")
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
        # logger.exception(f"Failed to create datasite {name}")
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
        # logger.exception(f"Failed to remove datasite {name}")
        return jsonify(error=f"Failed to remove datasite: {str(e)}"), 500


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the web application with plugins."
    )
    parser.add_argument("--config_path", type=str, help="config path")
    parser.add_argument("--sync_folder", type=str, help="sync folder path")
    parser.add_argument("--email", type=str, help="email")
    parser.add_argument("--port", type=int, default=8080, help="Port number")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    client_config = load_or_create_config(args)
    shared_state = initialize_shared_state(client_config)
    loaded_plugins = load_plugins(client_config)
    threads = []
    # autorun_plugins = ["sync", "create_datasite"]
    autorun_plugins = ["init", "nsync", "create_datasite"]
    for plugin_name in autorun_plugins:
        print("got plugin", plugin_name)
        scheduler_thread = threading.Thread(target=start_plugin, args=(plugin_name,))
        scheduler_thread.start()
        threads.append(scheduler_thread)

    print(f"Client Running: http://localhost:{client_config.port}")
    try:
        app.run(host="0.0.0.0", port=client_config.port, debug=True)
    except KeyboardInterrupt:
        pass
    finally:
        for thread in threads:
            thread.join()
